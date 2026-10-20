"""Exhaustive checks for the replication task's Extra ZFS Arguments.

Three layers, all without ZFS:
  1. The form (scheduler/src/models/ZfsExtraArgs.ts) and the run-time gate
     (replication/planner.py) agree on every generated input, so the UI can never save a
     task that the backend would refuse, and nothing the backend refuses is savable.
  2. For every accepted input under every combination of task settings, the zfs send and
     zfs recv commands are well formed: no flag twice, managed flags exactly as the task
     settings dictate, dataset/snapshot names last, and remote shell strings round-trip.
  3. Every new-stream receive in the transfer modules goes through the shared builder,
     so no transport can silently drop or duplicate the extras.

The live counterpart (real zfs, every transport) is
`tests/live-replication-harness.sh scenario-extra-args-matrix`.
"""

import functools
import itertools
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import SCRIPTS_DIR
from replication import workflow
from replication.models import ReplicationRun
from replication.planner import (
    EXTRA_RECV_ARGS_ENV,
    EXTRA_RECV_FLAGS,
    EXTRA_SEND_ARGS_ENV,
    EXTRA_SEND_FLAGS,
    ExtraArgsError,
    build_zfs_recv_args,
    build_zfs_send_args,
    canonical_send_flags,
    check_extra_args_against_task,
    parse_extra_zfs_args,
    zfs_recv_shell,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PARITY_SCRIPT = REPO_ROOT / "tests" / "extra-args-parity.mjs"
TS_MODULE = REPO_ROOT / "scheduler" / "src" / "models" / "ZfsExtraArgs.ts"

# Valid and invalid building blocks; corpora are every sequence of up to three of them.
SEND_TOKENS = [
    "-p", "--props", "-b", "-h", "--holds",
    "-e", "--embed", "-L", "--large-block", "-c", "--compressed",
    "-pb", "-ph", "-Lce", "-ec", "-pp", "-ee",
    # managed or unsupported
    "-R", "-w", "-I", "-i", "-t", "-n", "-v", "-pR", "--raw", "--props=yes", "--",
    # positional
    "tank/data@snap",
]
RECV_TOKENS = [
    "-u", "-h", "-uh", "-hu", "-uu",
    "-o atime=off", "-o atime=on", "-oatime=off", "-o compression=gzip",
    "-o com.example:note=a", "-o recordsize=1M", "-o mountpoint=/mnt/x",
    "-x atime", "-x mountpoint", "-xmountpoint", "-x com.example:note",
    "-uo atime=off", "-ux mountpoint",
    # malformed values
    "-o", "-x", "-o atime", "-x atime=off", "-o =v", "-x =v", "-o -u",
    # reserved properties
    "-o origin=tank/x@s", "-x origin", "-o encryption=on", "-x keylocation", "-o keyformat=raw",
    "-x pbkdf2iters", "-o com.45drives_scheduler:task_name=x",
    "-x com.45drives_scheduler:scheduler_interval_tier",
    # managed or naming-changing flags
    "-F", "-s", "-d", "-e", "-A", "-n", "-v", "-M", "-c", "--props",
    # positional
    "tank/target",
]
# The form only accepts this charset; the backend also has to survive anything a hand-edited env file holds.
HOSTILE_TEXTS = [
    "-u;", "-u; rm -rf /", "-u | cat", "-u && reboot", "-o a=$(id)", "-o a=`id`",
    "-o 'note=a b'", '-o "note=a"', "-u\n-h", "-u\t-h", "-o note=a\\ b", "-u #comment",
    "-o 'unterminated", "-u >/tmp/x", "-o note=a*b", "-x ~",
]

TASK_MATRIX = list(itertools.product(
    [False, True],                 # recursive
    ["plain", "compressed", "raw"],
    [None, True, False],           # include intermediates
    [False, True],                 # incremental
))
# (recursive, raw, compressed) as the form can save them: raw and compressed are mutually exclusive.
TASK_FLAGS = [(rec, raw, comp) for rec in (False, True) for raw, comp in ((False, False), (False, True), (True, False))]


def _sequences(tokens, max_len=3):
    for n in range(max_len + 1):
        for combo in itertools.product(tokens, repeat=n):
            yield " ".join(combo)


SEND_CORPUS = sorted(set(_sequences(SEND_TOKENS)))
RECV_CORPUS = sorted(set(_sequences(RECV_TOKENS)))


def backend_problem(field, text, recursive=False, raw=False, compressed=False):
    try:
        if field == "send":
            args = parse_extra_zfs_args(text, EXTRA_SEND_FLAGS)
            check_extra_args_against_task(args, recursive=recursive, raw=raw, compressed=compressed)
        else:
            parse_extra_zfs_args(text, EXTRA_RECV_FLAGS)
    except ExtraArgsError as e:
        return str(e)
    return None


@functools.lru_cache(maxsize=None)
def valid_send_texts(recursive, raw=False, compressed=False):
    return [t for t in SEND_CORPUS if backend_problem("send", t, recursive, raw, compressed) is None]


@functools.lru_cache(maxsize=None)
def valid_recv_texts():
    return [t for t in RECV_CORPUS if backend_problem("recv", t) is None]


# ---------------------------------------------------------------------------
# 1. Form <-> backend parity
# ---------------------------------------------------------------------------

def _node_can_strip_types():
    node = shutil.which("node")
    if not node:
        return False
    out = subprocess.run([node, "-e", "process.stdout.write(process.versions.node)"], capture_output=True, text=True)
    try:
        major, minor = (int(x) for x in out.stdout.split(".")[:2])
    except ValueError:
        return False
    return (major, minor) >= (22, 6)


def _form_verdicts(cases):
    args = ["node"]
    major = int(subprocess.run(["node", "-e", "process.stdout.write(process.versions.node.split('.')[0])"],
                               capture_output=True, text=True).stdout or 0)
    if major < 23:
        args.append("--experimental-strip-types")
    proc = subprocess.run(
        args + [str(PARITY_SCRIPT)],
        input=json.dumps(cases), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


needs_form = pytest.mark.skipif(
    not (_node_can_strip_types() and TS_MODULE.is_file()),
    reason="needs node >= 22.6 and the scheduler/ source tree",
)


@needs_form
def test_form_and_backend_agree_on_every_generated_input():
    cases = (
        [{"field": "send", "text": t, "recursive": r, "raw": w, "compressed": c}
         for t in SEND_CORPUS for r, w, c in TASK_FLAGS]
        + [{"field": "recv", "text": t, "recursive": False, "raw": False, "compressed": False} for t in RECV_CORPUS]
    )
    verdicts = _form_verdicts(cases)
    mismatches = []
    for case, form in zip(cases, verdicts):
        backend = backend_problem(case["field"], case["text"], case["recursive"], case["raw"], case["compressed"])
        if (form is None) != (backend is None):
            mismatches.append(f"{case} form={form!r} backend={backend!r}")
    assert not mismatches, f"{len(mismatches)} disagreements, first: " + "\n".join(mismatches[:20])


@needs_form
def test_form_never_accepts_what_the_backend_refuses_on_hostile_input():
    cases = (
        [{"field": "send", "text": t, "recursive": False} for t in HOSTILE_TEXTS]
        + [{"field": "recv", "text": t, "recursive": False} for t in HOSTILE_TEXTS]
    )
    for case, form in zip(cases, _form_verdicts(cases)):
        assert form is not None, f"form accepted {case['text']!r} for {case['field']}"


def test_corpora_exercise_both_outcomes():
    """Guards against a corpus that silently stops covering one side."""
    for field, corpus in (("send", SEND_CORPUS), ("recv", RECV_CORPUS)):
        verdicts = [backend_problem(field, t) for t in corpus]
        assert sum(v is None for v in verdicts) > 50
        assert sum(v is not None for v in verdicts) > 1000


# ---------------------------------------------------------------------------
# 2. Command shape under every task setting
# ---------------------------------------------------------------------------

_SEND_LETTERS = {"R", "L", "c", "w", "e", "p", "b", "h"}
_LONG_TO_SHORT = {
    "--props": "p", "--backup": "b", "--holds": "h",
    "--embed": "e", "--large-block": "L", "--compressed": "c",
}


def _send_option_letters(args):
    """Every single-letter option in a send argv up to the incremental flag, clusters expanded."""
    letters = []
    for a in args[2:]:
        if a in ("-i", "-I"):
            break
        if a in _LONG_TO_SHORT:
            letters.append(_LONG_TO_SHORT[a])
        elif a.startswith("-") and not a.startswith("--"):
            letters.extend(a[1:])
        else:
            break
    return letters


@pytest.mark.parametrize("recursive, mode, include, incremental", TASK_MATRIX)
def test_send_command_is_well_formed_for_every_valid_input(monkeypatch, recursive, mode, include, incremental):
    compressed, raw = mode == "compressed", mode == "raw"
    base = "tank/data@old" if incremental else ""
    for text in valid_send_texts(recursive, raw, compressed):
        monkeypatch.setenv(EXTRA_SEND_ARGS_ENV, text)
        args = build_zfs_send_args("tank/data@new", base, recursive=recursive, compressed=compressed, raw=raw,
                                   include_intermediates=include)
        extras = {f.lstrip("-") for f in canonical_send_flags(parse_extra_zfs_args(text, EXTRA_SEND_FLAGS))}
        ctx = f"text={text!r} recursive={recursive} mode={mode} include={include} incremental={incremental}: {args}"

        assert args[:2] == ["zfs", "send"], ctx
        assert args[-1] == "tank/data@new", ctx
        if incremental:
            assert args[-3] in ("-i", "-I") and args[-2] == base, ctx
            expected_flag = ("-I" if recursive else "-i") if include is None else ("-I" if include else "-i")
            assert args[-3] == expected_flag, ctx
        else:
            assert "-i" not in args and "-I" not in args, ctx

        letters = _send_option_letters(args)
        present = set(letters)
        assert len(letters) == len(present), f"duplicate flag: {ctx}"
        assert present <= _SEND_LETTERS, ctx
        assert ("R" in present) == recursive, ctx
        assert ("w" in present) == raw, ctx
        if compressed:
            assert {"L", "c"} <= present, ctx
        if raw:
            assert not present & {"L", "c", "e"}, f"-w already implies these: {ctx}"
        if recursive:
            assert "p" not in present, f"-R already sends properties: {ctx}"
        # Every letter is either the task's own or one the user asked for.
        task_letters = ({"R"} if recursive else set()) | ({"L", "c"} if compressed else set()) | ({"w"} if raw else set())
        assert present == task_letters | extras, ctx

        # estimate_send_size inserts -nP after "zfs send"; it must not collide with anything.
        assert "n" not in present and "P" not in present, ctx


@pytest.mark.parametrize("force", [False, True])
def test_recv_command_is_well_formed_for_every_valid_input(monkeypatch, force):
    for text in valid_recv_texts():
        monkeypatch.setenv(EXTRA_RECV_ARGS_ENV, text)
        argv = build_zfs_recv_args("backup/target", force)
        extras = parse_extra_zfs_args(text, EXTRA_RECV_FLAGS)
        ctx = f"text={text!r} force={force}: {argv}"

        assert argv[:3] == ["zfs", "recv", "-s"], ctx
        assert argv[-1] == "backup/target", ctx
        assert argv[3:-1] == (["-F"] if force else []) + extras, ctx
        assert argv.count("-F") == (1 if force else 0) and argv.count("-s") == 1, ctx

        props = [extras[i + 1].partition("=")[0] for i, a in enumerate(extras) if a in ("-o", "-x")]
        assert len(props) == len(set(props)), f"property repeated: {ctx}"
        flags = [a for i, a in enumerate(extras) if a.startswith("-") and (i == 0 or extras[i - 1] not in ("-o", "-x"))]
        bare = [a for a in flags if a not in ("-o", "-x")]
        assert len(bare) == len(set(bare)), f"flag repeated: {ctx}"

        # Remote transports hand this string to a shell; it has to parse back to the same argv.
        assert shlex.split(zfs_recv_shell("backup/target", force)) == argv, ctx


def test_recv_shell_survives_hostile_values_that_reach_the_backend(monkeypatch):
    for text in HOSTILE_TEXTS:
        if backend_problem("recv", text) is not None:
            continue
        monkeypatch.setenv(EXTRA_RECV_ARGS_ENV, text)
        argv = build_zfs_recv_args("backup/target", True)
        assert shlex.split(zfs_recv_shell("backup/target", True)) == argv, text


# ---------------------------------------------------------------------------
# 3. Run-time gate and transport wiring
# ---------------------------------------------------------------------------

def _init_env(monkeypatch, **extra):
    for key in list(workflow.os.environ):
        if key.startswith("zfsRepConfig_") or key in ("taskName", "scheduleJsonPath"):
            monkeypatch.delenv(key, raising=False)
    env = {
        "zfsRepConfig_sourceDataset_pool": "tank",
        "zfsRepConfig_sourceDataset_dataset": "tank/source",
        "zfsRepConfig_destDataset_pool": "backup",
        "zfsRepConfig_destDataset_dataset": "target",
    }
    env.update(extra)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(workflow, "_apply_tcp_tuning", lambda: None)
    monkeypatch.setattr(workflow, "load_schedule_json", lambda path: None)
    monkeypatch.setattr(workflow.os, "remove", lambda path: None)
    monkeypatch.setattr(workflow.os.path, "isfile", lambda path: False)


def _spread(items, n=400):
    return items[::max(1, len(items) // n)]


@pytest.mark.parametrize("recursive, raw, compressed", TASK_FLAGS)
def test_task_start_refuses_every_invalid_send_input(monkeypatch, recursive, raw, compressed):
    for text in _spread([t for t in SEND_CORPUS if backend_problem("send", t, recursive, raw, compressed)]):
        _init_env(monkeypatch, **{
            EXTRA_SEND_ARGS_ENV: text,
            "zfsRepConfig_sendOptions_recursive_flag": "true" if recursive else "false",
            "zfsRepConfig_sendOptions_raw_flag": "true" if raw else "false",
            "zfsRepConfig_sendOptions_compressed_flag": "true" if compressed else "false",
        })
        with pytest.raises(SystemExit) as exc:
            workflow._initialize_run(ReplicationRun())
        assert exc.value.code == 2, text


def test_task_start_refuses_every_invalid_recv_input(monkeypatch):
    for text in _spread([t for t in RECV_CORPUS if backend_problem("recv", t)]):
        _init_env(monkeypatch, **{EXTRA_RECV_ARGS_ENV: text})
        with pytest.raises(SystemExit) as exc:
            workflow._initialize_run(ReplicationRun())
        assert exc.value.code == 2, text


def test_task_start_accepts_valid_input(monkeypatch):
    _init_env(monkeypatch, **{
        EXTRA_SEND_ARGS_ENV: "-p -h",
        EXTRA_RECV_ARGS_ENV: "-o atime=off -x mountpoint -u",
    })
    workflow._initialize_run(ReplicationRun())


@pytest.mark.parametrize("send, recursive, raw, refused", [
    ("-h", False, True, True),
    ("--holds", False, True, True),
    ("-bh", False, True, True),
    ("-ph", False, True, False),
    ("-h", True, True, False),
    ("-h", False, False, False),
])
def test_raw_holds_need_properties(send, recursive, raw, refused):
    """Live matrix: raw, non-recursive `zfs send -h` without -p is rejected by zfs."""
    problem = backend_problem("send", send, recursive, raw)
    assert (problem is not None) == refused, problem


@pytest.mark.parametrize("send, raw, compressed, refused", [
    ("-e", False, True, False),          # Send Compressed + -e == the old -Lce
    ("-e", False, False, False),
    ("-c", False, False, False),         # compression without large blocks
    ("-Lc", False, False, False),
    ("-L", False, True, True),
    ("--compressed", False, True, True),
    ("-e", True, False, True),           # -w already implies -L -c -e
    ("-L", True, False, True),
    ("-c", True, False, True),
])
def test_send_flags_only_add_what_the_toggles_do_not(send, raw, compressed, refused):
    problem = backend_problem("send", send, False, raw, compressed)
    assert (problem is not None) == refused, problem


class _Proc:
    def __init__(self, rc, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


def _encryption_ctx(monkeypatch, send, existing):
    """existing maps dataset -> encryption values `zfs get -r` would print; anything else is missing."""
    calls = []

    def fake_dest_run(ctx, args, timeout=30):
        calls.append(args)
        values = existing.get(args[-1])
        return _Proc(1) if values is None else _Proc(0, "\n".join(values))

    monkeypatch.setenv(EXTRA_SEND_ARGS_ENV, send)
    monkeypatch.setattr(workflow, "_dest_run", fake_dest_run)
    ctx = ReplicationRun()
    ctx.destFilesystem = "backup/enc/target"
    return ctx, calls


@pytest.mark.parametrize("existing, code", [
    ({"backup/enc/target": ["aes-256-gcm", "aes-256-gcm"]}, 2),
    ({"backup/enc/target": ["off", "aes-256-gcm"]}, 2),          # an encrypted child counts
    ({"backup/enc": ["aes-256-gcm"]}, 2),                         # new dataset inherits its parent's
    ({"backup": ["aes-256-gcm"]}, 2),
    ({}, 1),                                                      # unreadable: transient, retry
])
def test_embed_is_refused_before_sending_into_an_encrypted_destination(monkeypatch, existing, code):
    ctx, _ = _encryption_ctx(monkeypatch, "-e", existing)
    with pytest.raises(SystemExit) as exc:
        workflow._refuse_embed_into_encrypted_destination(ctx)
    assert exc.value.code == code


@pytest.mark.parametrize("existing", [
    {"backup/enc/target": ["off", "off", "-"]},
    {"backup/enc": ["off"]},
])
def test_embed_is_allowed_into_an_unencrypted_destination(monkeypatch, existing):
    ctx, calls = _encryption_ctx(monkeypatch, "-pe", existing)
    workflow._refuse_embed_into_encrypted_destination(ctx)
    # Only the destination itself is read recursively; a parent's siblings must not count.
    assert all("-r" not in c for c in calls[1:])


def test_encryption_is_not_checked_without_embed(monkeypatch):
    ctx, calls = _encryption_ctx(monkeypatch, "-p", {"backup/enc/target": ["aes-256-gcm"]})
    workflow._refuse_embed_into_encrypted_destination(ctx)
    assert calls == []


def test_new_stream_receives_only_come_from_the_shared_builder():
    """A hand-built `zfs recv` in a transfer module would skip the extras (or the -F rule)."""
    pattern = re.compile(r'\[\s*"zfs"\s*,\s*"(recv|receive)"|zfs recv -s')
    for name in ("push.py", "pull.py"):
        source = (SCRIPTS_DIR / "replication" / "transfers" / name).read_text()
        hits = [line.strip() for line in source.splitlines() if pattern.search(line)]
        assert not hits, f"{name} builds zfs recv by hand: {hits}"


def test_new_stream_sends_only_come_from_the_shared_builder():
    pattern = re.compile(r'\[\s*"zfs"\s*,\s*"send"')
    for name in ("push.py", "pull.py"):
        source = (SCRIPTS_DIR / "replication" / "transfers" / name).read_text()
        assert not [l for l in source.splitlines() if pattern.search(l)], name
    workflow_src = (SCRIPTS_DIR / "replication" / "workflow.py").read_text()
    assert not pattern.search(workflow_src)
