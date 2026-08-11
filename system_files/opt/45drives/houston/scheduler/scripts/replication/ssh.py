"""SSH command construction and execution."""

import os
import re
import shlex
import subprocess
import time

from .logging_utils import _fmt_cmd, _truncate, dbg

SSH_BASE_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "Compression=no",
]

_SSH_CIPHER = os.environ.get("ZFS_REP_SSH_CIPHER", "").strip()
if _SSH_CIPHER:
    SSH_BASE_OPTS.extend(["-o", f"Ciphers={_SSH_CIPHER}"])
    dbg(f"SSH cipher override: {_SSH_CIPHER}")

def ssh_base_args(user, host, port):
    """Build a base SSH argv list (for Popen). Used by netcat listener setup."""
    args = ["ssh"] + SSH_BASE_OPTS
    if str(port) != "22":
        args.extend(["-p", str(port)])
    args.append(f"{user}@{host}")
    return args


_REMOTE_COMMAND_CACHE = {}


def remote_has_command(user, host, port, command_name, timeout=10):
    """Return True when command_name exists on the remote host via SSH."""
    if not user or not host or not command_name:
        return False

    key = (str(user), str(host), str(port), str(command_name))
    if key in _REMOTE_COMMAND_CACHE:
        return _REMOTE_COMMAND_CACHE[key]

    check = f"command -v {shlex.quote(str(command_name))} >/dev/null 2>&1"
    try:
        p = ssh_run_args(
            user,
            host,
            port,
            ["sh", "-lc", check],
            capture_output=False,
            check=False,
            timeout=timeout,
        )
        ok = p.returncode == 0
    except Exception:
        ok = False

    _REMOTE_COMMAND_CACHE[key] = ok
    return ok


def ssh_run_args(user, host, port, args, *, capture_output=True, check=False, text=False, timeout=None):
    ssh_cmd = ["ssh"] + SSH_BASE_OPTS
    if str(port) != "22":
        ssh_cmd += ["-p", str(port)]
    ssh_cmd.append(f"{user}@{host}")

    remote_cmd = " ".join(shlex.quote(str(a)) for a in args)
    ssh_cmd.append(remote_cmd)

    dbg(f"RUN ssh: {_fmt_cmd(ssh_cmd)}")
    start = time.time()
    p = subprocess.run(
        ssh_cmd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        universal_newlines=text,
        check=False,
        timeout=timeout,
    )
    dur = time.time() - start

    out = p.stdout if capture_output else ""
    err = p.stderr if capture_output else ""
    if isinstance(out, bytes):
        out = out.decode(errors="replace")
    if isinstance(err, bytes):
        err = err.decode(errors="replace")

    dbg(f"RC ssh={p.returncode} dur={dur:.2f}s stdout:\n{_truncate(out)}")
    dbg(f"RC ssh={p.returncode} dur={dur:.2f}s stderr:\n{_truncate(err)}")

    if check and p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, ssh_cmd, output=p.stdout, stderr=p.stderr)
    return p


def ssh_popen_args(user, host, port, args, *, stdin=None, stdout=None, stderr=None, universal_newlines=False):
    ssh_cmd = ["ssh"] + SSH_BASE_OPTS
    if str(port) != "22":
        ssh_cmd += ["-p", str(port)]
    ssh_cmd.append(f"{user}@{host}")

    remote_cmd = " ".join(shlex.quote(str(a)) for a in args)
    ssh_cmd.append(remote_cmd)

    dbg(f"POPEN ssh: {_fmt_cmd(ssh_cmd)}")
    p = subprocess.Popen(
        ssh_cmd,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        universal_newlines=universal_newlines,
    )
    dbg(f"POPEN ssh pid={p.pid}")
    return p


def estimate_send_size_remote(remote_user, remote_host, remote_port, send_cmd):
    """Estimate total send size by running a dry-run via SSH.

    Uses Popen to stream output line-by-line, avoiding unbounded memory
    usage for large recursive sends with many child datasets.
    """
    try:
        cmd = list(send_cmd)
        if len(cmd) < 2 or cmd[0] != "zfs" or cmd[1] != "send":
            return None
        cmd.insert(2, "-nP")

        ssh_cmd = ["ssh"] + SSH_BASE_OPTS
        if str(remote_port) != "22":
            ssh_cmd += ["-p", str(remote_port)]
        ssh_cmd.append(f"{remote_user}@{remote_host}")
        ssh_cmd.append(" ".join(shlex.quote(str(a)) for a in cmd))

        dbg(f"RUN ssh (estimate): {_fmt_cmd(ssh_cmd)}")
        start = time.time()
        p = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        total = 0
        found_size_line = False
        found_summary = False

        # Read stdout line-by-line to avoid buffering hundreds of MB
        for raw_line in p.stdout:
            line = raw_line.decode(errors="replace").strip()
            if not line:
                continue
            # Prefer explicit "size" summary line (non-recursive sends)
            if not found_summary and "size" in line.lower():
                m = re.search(r"\bsize\b\s*=?\s*(\d+)", line, re.IGNORECASE)
                if m:
                    total = int(m.group(1))
                    found_summary = True
                    continue
            # Sum per-stream sizes for recursive sends
            if line.startswith("full") or line.startswith("incremental"):
                parts = line.split("\t")
                if parts:
                    try:
                        total += int(parts[-1])
                        found_size_line = True
                    except (ValueError, IndexError):
                        pass

        p.wait()
        dur = time.time() - start
        dbg(f"RC ssh (estimate)={p.returncode} dur={dur:.2f}s total_bytes={total}")

        if p.returncode != 0:
            return None
        if found_summary:
            return total
        return total if found_size_line and total > 0 else None
    except Exception:
        return None
