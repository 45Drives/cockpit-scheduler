import io
import os
import subprocess
import tempfile

import pytest

from conftest import RecordingNotifier
from replication import process


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"size\t1048576\n", 1048576),
        (b"full\ttank/a@s1\t100\nincremental\ttank/a@s1\ttank/a@s2\t25\n", 125),
        (b"warning only\n", None),
        (b"full\tbad\n", None),
    ],
)
def test_parse_send_size_output(raw, expected):
    assert process._parse_send_size_output(raw) == expected


def test_estimate_send_size_adds_dry_run_flag(monkeypatch):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return type("Result", (), {"returncode": 0, "stdout": b"size 4096\n", "stderr": b""})()

    monkeypatch.setattr(process, "run_logged", fake_run)
    assert process.estimate_send_size(["zfs", "send", "tank/data@s1"]) == 4096
    assert seen[0] == ["zfs", "send", "-nP", "tank/data@s1"]
    assert process.estimate_send_size(["echo", "nope"]) is None


def test_stream_copy_preserves_bytes_and_reports_zero_to_one_hundred(monkeypatch):
    recorder = RecordingNotifier()
    monkeypatch.setattr(process, "notifier", recorder)
    payload = b"replication-data" * 8192
    with tempfile.TemporaryFile() as src, tempfile.TemporaryFile() as dst:
        src.write(payload)
        src.seek(0)
        sent, broken = process.stream_with_progress_stall(src, dst, len(payload), min_interval=0, stall_timeout=0)
        dst.seek(0)
        assert dst.read() == payload
    assert sent == len(payload)
    assert broken is False
    assert recorder.messages[0].endswith("0.0% complete")
    assert recorder.messages[-1].endswith("100.0% complete")
    percentages = [float(message.split("… ", 1)[1].split("%", 1)[0]) for message in recorder.messages]
    assert percentages == sorted(percentages)
    assert all(0 <= value <= 100 for value in percentages)


def test_stream_copy_reports_broken_downstream(monkeypatch, capsys):
    monkeypatch.setattr(process, "notifier", RecordingNotifier())
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    with tempfile.TemporaryFile() as src, os.fdopen(write_fd, "wb", buffering=0) as dst:
        src.write(b"x" * 32)
        src.seek(0)
        sent, broken = process.stream_with_progress_stall(src, dst, 32, min_interval=0, stall_timeout=0)
    assert sent == 0
    assert broken is True
    assert "pipe broken" in capsys.readouterr().out


def test_progress_holds_at_99_9_when_estimate_is_too_small(monkeypatch):
    recorder = RecordingNotifier()
    monkeypatch.setattr(process, "notifier", recorder)
    with tempfile.TemporaryFile() as src, tempfile.TemporaryFile() as dst:
        src.write(b"x" * 100)
        src.seek(0)
        process.stream_with_progress_stall(src, dst, 10, min_interval=0, stall_timeout=0)
    assert any("99.9% complete" in message for message in recorder.messages)
    assert recorder.messages[-1].endswith("100.0% complete")


def test_progress_emits_liveness_notice_when_percent_is_static(monkeypatch):
    recorder = RecordingNotifier()
    monkeypatch.setattr(process, "notifier", recorder)

    class StepClock:
        def __init__(self):
            self.value = 0.0

        def __call__(self):
            self.value += 20.0
            return self.value

    monkeypatch.setattr(process.time, "time", StepClock())

    payload = b"x" * (1024 * 1024 * 5)
    with tempfile.TemporaryFile() as src, tempfile.TemporaryFile() as dst:
        src.write(payload)
        src.seek(0)
        process.stream_with_progress_stall(src, dst, 10**12, min_interval=0, stall_timeout=0)

    assert any("still active; replaying many small snapshot deltas" in message for message in recorder.messages)


def test_progress_liveness_notice_includes_optional_progress_note(monkeypatch):
    recorder = RecordingNotifier()
    monkeypatch.setattr(process, "notifier", recorder)

    class StepClock:
        def __init__(self):
            self.value = 0.0

        def __call__(self):
            self.value += 20.0
            return self.value

    monkeypatch.setattr(process.time, "time", StepClock())

    payload = b"x" * (1024 * 1024 * 5)
    with tempfile.TemporaryFile() as src, tempfile.TemporaryFile() as dst:
        src.write(payload)
        src.seek(0)
        process.stream_with_progress_stall(
            src,
            dst,
            10**12,
            min_interval=0,
            stall_timeout=0,
            progress_note_getter=lambda: "; snapshots replayed 12/34",
        )

    assert any("snapshots replayed 12/34" in message for message in recorder.messages)


def test_progress_liveness_notice_mentions_receive_finalization_near_99_9(monkeypatch):
    recorder = RecordingNotifier()
    monkeypatch.setattr(process, "notifier", recorder)

    class StepClock:
        def __init__(self):
            self.value = 0.0

        def __call__(self):
            self.value += 20.0
            return self.value

    monkeypatch.setattr(process.time, "time", StepClock())
    monkeypatch.setenv("ZFS_REP_CHUNK_SIZE", "5")

    # Deliberately overrun estimate in many small chunks so percent caps at 99.9
    # and liveness notice is emitted while transfer remains active.
    payload = b"x" * 1000
    with tempfile.TemporaryFile() as src, tempfile.TemporaryFile() as dst:
        src.write(payload)
        src.seek(0)
        process.stream_with_progress_stall(
            src,
            dst,
            10,
            min_interval=0,
            stall_timeout=0,
        )

    assert any("near stream completion, waiting for receive-side finalization" in message for message in recorder.messages)


def test_finalize_wait_emits_heartbeat_then_completes(monkeypatch):
    recorder = RecordingNotifier()
    monkeypatch.setattr(process, "notifier", recorder)

    class Proc:
        args = ["zfs", "recv"]
        pid = 42

        def __init__(self):
            self.calls = 0

        def wait(self, timeout):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(self.args, timeout)
            return 0

    clock = iter([0.0, 0.0, 1.1, 1.1])
    monkeypatch.setattr(process.time, "time", lambda: next(clock))
    assert process._wait_with_finalize_heartbeat(Proc(), "remote zfs recv", 10, heartbeat_interval=1) == 0
    assert any("waiting on remote zfs recv" in message for message in recorder.messages)


@pytest.mark.parametrize(
    "value,expected",
    [(0, "0 B"), (1024, "1.0 KiB"), (1024**2, "1.0 MiB"), (1024**3, "1.0 GiB"), (1024**4, "1.0 TiB"), ("bad", "bad")],
)
def test_format_bytes(value, expected):
    assert process.format_bytes(value) == expected


def test_kill_procs_is_best_effort():
    calls = []

    class Proc:
        def kill(self):
            calls.append("kill")

        def wait(self, timeout):
            calls.append(("wait", timeout))

    process._kill_procs(None, Proc())
    assert calls == ["kill", ("wait", 10)]

