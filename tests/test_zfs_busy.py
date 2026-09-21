import subprocess

import pytest

import zfs_busy
from replication import snapshots


class DummyNotifier:
    def __init__(self):
        self.messages = []

    def notify(self, message):
        self.messages.append(message)


BUSY_ERR = "cannot create snapshot 'tank/newbackups@t-1': dataset is busy"


def _busy_error(cmd):
    return subprocess.CalledProcessError(1, cmd, output="", stderr=BUSY_ERR)


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(snapshots.time, "sleep", lambda s: slept.append(s))
    return slept


@pytest.fixture
def notifier(monkeypatch):
    fake = DummyNotifier()
    monkeypatch.setattr(snapshots, "notifier", fake)
    return fake


def test_detects_busy_wording():
    assert zfs_busy.is_dataset_busy(BUSY_ERR)
    assert zfs_busy.is_dataset_busy("cannot destroy 'tank/x': pool or dataset is busy")
    assert not zfs_busy.is_dataset_busy("cannot open 'tank/x': dataset does not exist")
    assert not zfs_busy.is_dataset_busy("")
    assert not zfs_busy.is_dataset_busy(None)


def test_wait_schedule_fits_the_budget():
    assert zfs_busy.busy_wait_schedule() == [3, 6, 9, 12, 15]
    assert sum(zfs_busy.busy_wait_schedule()) <= zfs_busy.BUSY_WAIT_BUDGET_SECONDS
    assert zfs_busy.busy_wait_schedule(budget=10) == [3, 6]
    assert zfs_busy.busy_wait_schedule(budget=2) == []


def test_wait_messages_do_not_read_as_task_retries():
    notice = zfs_busy.busy_wait_notice("tank/newbackups", 3, 3)
    assert "not a task retry" in notice
    assert "attempt" not in notice.lower()
    assert "retrying" not in notice.lower()
    assert "tank/newbackups" in zfs_busy.busy_giveup_notice("tank/newbackups")


def test_merge_streams_puts_stderr_first():
    assert zfs_busy.merge_streams("out", "err") == "err\nout"
    assert zfs_busy.merge_streams("", "err") == "err"
    assert zfs_busy.merge_streams(None, None) == ""


def test_local_snapshot_retries_until_dataset_frees_up(monkeypatch, no_sleep, notifier):
    calls = []

    def fake_run_logged(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) < 3:
            raise _busy_error(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(snapshots, "run_logged", fake_run_logged)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda fs, **kw: 10 ** 12)
    monkeypatch.setattr(snapshots, "apply_snapshot_tags", lambda *a, **kw: None)

    snap = snapshots.create_snapshot_local("tank/newbackups", False, "testlong")

    assert snap.startswith("tank/newbackups@testlong-")
    assert len(calls) == 3
    assert no_sleep == [3, 6]
    assert any("busy dataset" in m for m in notifier.messages)


def test_local_snapshot_gives_up_after_the_wait_budget(monkeypatch, no_sleep, notifier):
    calls = []

    def always_busy(cmd, **kwargs):
        calls.append(cmd)
        raise _busy_error(cmd)

    monkeypatch.setattr(snapshots, "run_logged", always_busy)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda fs, **kw: 10 ** 12)

    with pytest.raises(subprocess.CalledProcessError):
        snapshots.create_snapshot_local("tank/newbackups", False, "testlong")

    assert len(calls) == len(zfs_busy.busy_wait_schedule()) + 1
    assert no_sleep == [3, 6, 9, 12, 15]
    assert sum(no_sleep) == zfs_busy.BUSY_WAIT_BUDGET_SECONDS


def test_local_snapshot_does_not_retry_other_errors(monkeypatch, no_sleep, notifier):
    calls = []

    def fails(cmd, **kwargs):
        calls.append(cmd)
        raise subprocess.CalledProcessError(1, cmd, output="", stderr="out of space")

    monkeypatch.setattr(snapshots, "run_logged", fails)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda fs, **kw: 10 ** 12)

    with pytest.raises(subprocess.CalledProcessError):
        snapshots.create_snapshot_local("tank/newbackups", False, "testlong")

    assert len(calls) == 1
    assert no_sleep == []


def test_local_snapshot_still_treats_existing_snapshot_as_success(monkeypatch, no_sleep, notifier):
    def exists(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, output="", stderr="snapshot already exists")

    monkeypatch.setattr(snapshots, "run_logged", exists)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda fs, **kw: 10 ** 12)

    with pytest.raises(SystemExit) as exc:
        snapshots.create_snapshot_local("tank/newbackups", False, "testlong")

    assert exc.value.code == 0


def test_remote_snapshot_retries_until_dataset_frees_up(monkeypatch, no_sleep, notifier):
    results = [
        subprocess.CompletedProcess([], 1, "", BUSY_ERR),
        subprocess.CompletedProcess([], 1, "", BUSY_ERR),
        subprocess.CompletedProcess([], 0, "", ""),
    ]
    calls = []

    def fake_ssh(user, host, port, cmd, **kwargs):
        calls.append(cmd)
        return results[len(calls) - 1]

    monkeypatch.setattr(snapshots, "ssh_run_args", fake_ssh)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda fs, **kw: 10 ** 12)
    monkeypatch.setattr(snapshots, "apply_snapshot_tags", lambda *a, **kw: None)

    snap = snapshots.create_snapshot_remote(
        "tank/newbackups", False, "testlong", None, "root", "10.0.0.1", "22"
    )

    assert snap.startswith("tank/newbackups@testlong-")
    assert len(calls) == 3
    assert no_sleep == [3, 6]


def test_remote_snapshot_stops_retrying_on_a_different_error(monkeypatch, no_sleep, notifier):
    results = [
        subprocess.CompletedProcess([], 1, "", BUSY_ERR),
        subprocess.CompletedProcess([], 1, "", "permission denied"),
    ]
    calls = []

    def fake_ssh(user, host, port, cmd, **kwargs):
        calls.append(cmd)
        return results[len(calls) - 1]

    monkeypatch.setattr(snapshots, "ssh_run_args", fake_ssh)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda fs, **kw: 10 ** 12)

    with pytest.raises(subprocess.CalledProcessError):
        snapshots.create_snapshot_remote(
            "tank/newbackups", False, "testlong", None, "root", "10.0.0.1", "22"
        )

    assert len(calls) == 2
    assert no_sleep == [3]
