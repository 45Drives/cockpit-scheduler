import datetime
import subprocess
from types import SimpleNamespace

import pytest

from conftest import RecordingNotifier
from replication import retention, snapshots
from replication.constants import TASK_PROP, TIER_PROP
from replication.models import Snapshot


def result(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def snap(name, guid="g", age_days=0, task_tag=None, tier_tag=None):
    created = datetime.datetime(2026, 8, 4) - datetime.timedelta(days=age_days)
    value = Snapshot(name, guid, created, creation_epoch=int(created.timestamp()))
    value.task_tag = task_tag
    value.tier_tag = tier_tag
    return value


def test_snapshot_line_parsing_and_dataset_helpers():
    parsed = snapshots.parse_snapshot_line("tank/data@s1\tguid 1\t1700000000\t123")
    assert parsed.name == "tank/data@s1"
    assert parsed.guid == "guid 1"
    assert parsed.creation_epoch == 1700000000
    assert parsed.order_key == 123
    assert snapshots.parse_snapshot_line("bad") is None
    assert snapshots.snapshot_suffix("tank/data@s1") == "s1"
    assert snapshots.dataset_of_snapshot("tank/data@s1") == "tank/data"


def test_task_snapshot_matching_does_not_claim_other_tasks():
    assert snapshots.is_task_snapshot("tank/data@backup-2026-08-04", "backup")
    assert snapshots.is_task_snapshot("tank/data@pretty-t2-2026-08-04", "backup", "pretty")
    assert snapshots.is_task_snapshot("tank/data@pretty-backup-2026-08-04", "backup", "pretty")
    assert not snapshots.is_task_snapshot("tank/data@backup2-2026-08-04", "backup")
    assert not snapshots.is_task_snapshot("tank/data@anything", "")


def test_local_inventory_parses_properties_and_ignores_bad_rows(monkeypatch):
    replies = iter(
        [
            result(stdout="tank/data@s1\tg1\t1700000000\t10\nbad row\n"),
            result(stdout=f"tank/data@s1\t{TASK_PROP}\tjob-a\n"),
            result(stdout=f"tank/data@s1\t{TIER_PROP}\tt2\n"),
        ]
    )
    monkeypatch.setattr(snapshots, "run_logged", lambda *args, **kwargs: next(replies))
    values = snapshots.get_local_snapshots("tank/data")
    assert len(values) == 1
    assert values[0].task_tag == "job-a"
    assert values[0].tier_tag == "t2"


def test_local_inventory_distinguishes_missing_dataset_from_command_failure(monkeypatch):
    monkeypatch.setattr(snapshots, "run_logged", lambda *args, **kwargs: result(1, stderr="cannot open 'tank/missing': dataset does not exist"))
    assert snapshots.get_local_snapshots("tank/missing") is None
    monkeypatch.setattr(snapshots, "run_logged", lambda *args, **kwargs: result(1, stderr="I/O error"))
    with pytest.raises(subprocess.CalledProcessError):
        snapshots.get_local_snapshots("tank/data")


def test_property_helpers_accept_numbers_and_reject_dash(monkeypatch):
    replies = iter([result(stdout="1234\n"), result(stdout="-\n"), result(stdout="bad\n")])
    monkeypatch.setattr(snapshots.subprocess, "run", lambda *args, **kwargs: next(replies))
    assert snapshots.get_written_since_snapshot("tank/data", "tank/data@s1") == 1234
    assert snapshots.get_available_bytes("tank/data") is None
    assert snapshots.get_available_bytes("tank/data") is None


def test_create_local_snapshot_builds_recursive_name_and_tags(monkeypatch):
    calls = []

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 4, 15, 16, 17)

    monkeypatch.setattr(snapshots.datetime, "datetime", FixedDateTime)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda *args, **kwargs: 1024)
    monkeypatch.setattr(snapshots, "run_logged", lambda cmd, **kwargs: calls.append(cmd) or result())
    name = snapshots.create_snapshot_local("tank/data", True, "job-a", custom_name="daily", tier_idx=2)
    assert name == "tank/data@daily-t2-2026-08-04_15.16.17"
    assert calls == [
        ["zfs", "snapshot", "-r", name],
        ["zfs", "set", f"{TASK_PROP}=job-a", name],
        ["zfs", "set", f"{TIER_PROP}=t2", name],
    ]


def test_snapshot_creation_refuses_no_available_space(monkeypatch):
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda *args, **kwargs: 0)
    with pytest.raises(SystemExit) as exc:
        snapshots.create_snapshot_local("tank/data", False, "job-a")
    assert exc.value.code == 1


def test_tag_received_snapshot_uses_remote_transport(monkeypatch):
    calls = []
    monkeypatch.setattr(snapshots, "ssh_run_args", lambda *args, **kwargs: calls.append((args, kwargs)) or result())
    snapshots.tag_received_snapshots("backup/data", "s1", "job-a", tier_idx=3, remote_user="root", remote_host="host", remote_port="2222")
    commands = [entry[0][3] for entry in calls]
    assert commands == [
        ["zfs", "set", f"{TASK_PROP}=job-a", "backup/data@s1"],
        ["zfs", "set", f"{TIER_PROP}=t3", "backup/data@s1"],
    ]


def test_snapshot_exists_checks_exact_destination_name(monkeypatch):
    monkeypatch.setattr(snapshots, "get_local_snapshots", lambda fs: [snap("backup/data@s1"), snap("backup/child@s1")])
    assert snapshots.snapshot_exists_on_destination("backup/data", "s1") == (True, "backup/data@s1")
    assert snapshots.snapshot_exists_on_destination("backup/data", "s2") == (False, "backup/data@s2")


def test_retention_deletes_only_old_owned_matching_tier_and_preserves_excluded(monkeypatch):
    values = [
        snap("tank/data@job-a-old", age_days=10, task_tag="job-a", tier_tag="t1"),
        snap("tank/data@job-a-current", age_days=10, task_tag="job-a", tier_tag="t1"),
        snap("tank/data@job-a-young", age_days=1, task_tag="job-a", tier_tag="t1"),
        snap("tank/data@job-b-old", age_days=10, task_tag="job-b", tier_tag="t1"),
        snap("tank/data@job-a-other-tier", age_days=10, task_tag="job-a", tier_tag="t2"),
    ]

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 4)

    deleted = []
    recorder = RecordingNotifier()
    monkeypatch.setattr(retention.datetime, "datetime", FixedDateTime)
    monkeypatch.setattr(retention, "get_local_snapshots", lambda fs: values)
    monkeypatch.setattr(retention, "safe_destroy_local", lambda name: deleted.append(name) or True)
    monkeypatch.setattr(retention, "notifier", recorder)
    final = retention.prune_snapshots_by_retention(
        "tank/data", "job-a", 5, "days", "tank/data@job-a-current", progress_base=10, progress_span=40, tier_idx=1
    )
    assert deleted == ["tank/data@job-a-old"]
    assert final == 50
    assert recorder.messages[-1].endswith("50% complete")


def test_retention_does_not_name_match_snapshot_tagged_to_another_task(monkeypatch):
    old = snap("tank/data@job-a-2026-01-01", age_days=100, task_tag="job-b")
    deleted = []
    monkeypatch.setattr(retention, "get_local_snapshots", lambda fs: [old])
    monkeypatch.setattr(retention, "safe_destroy_local", lambda name: deleted.append(name) or True)
    assert retention.prune_snapshots_by_retention("tank/data", "job-a", 1, "days", "") == 100
    assert deleted == []


def test_safe_destroy_skips_held_snapshot(monkeypatch):
    called = []
    monkeypatch.setattr(retention, "_snapshot_has_holds_local", lambda name: True)
    monkeypatch.setattr(retention.subprocess, "run", lambda *args, **kwargs: called.append(args))
    assert retention.safe_destroy_local("tank/data@s1") is False
    assert called == []


def test_bulk_destroy_counts_missing_as_already_cleared(monkeypatch):
    replies = iter([result(), result(1, stderr="snapshot does not exist"), result(1, stderr="permission denied")])
    monkeypatch.setattr(retention.subprocess, "run", lambda *args, **kwargs: next(replies))
    destroyed, failed = retention.destroy_snapshots_with_progress([snap("d@s1"), snap("d@s2"), snap("d@s3")], "d")
    assert (destroyed, failed) == (2, 1)

