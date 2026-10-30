import datetime
import importlib.util
import subprocess
import sys
from types import SimpleNamespace

import pytest

from conftest import RecordingNotifier, SCRIPTS_DIR
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


@pytest.fixture
def autosnap(monkeypatch):
    spec = importlib.util.spec_from_file_location("autosnap_script", SCRIPTS_DIR / "autosnap-script.py")
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as streams:
        streams.setattr(sys, "stdout", sys.stdout)
        streams.setattr(sys, "stderr", sys.stderr)
        spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DEBUG_ENABLED", False)
    monkeypatch.setattr(module, "notifier", RecordingNotifier())
    return module


@pytest.fixture
def fixed_snapshot_time(monkeypatch):
    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 4, 15, 16, 17)

    monkeypatch.setattr(datetime, "datetime", FixedDateTime)


@pytest.mark.parametrize("custom_name,tier_idx,prefix", [(None, None, "job-a"), ("daily", 2, "daily-t2")])
@pytest.mark.parametrize("creator", ["autosnap", "local", "remote"])
def test_all_snapshot_generators_use_dotted_timestamps(
    monkeypatch, autosnap, fixed_snapshot_time, creator, custom_name, tier_idx, prefix
):
    calls = []
    monkeypatch.setattr(autosnap, "run", lambda cmd, **kwargs: calls.append(cmd) or result())
    monkeypatch.setattr(snapshots, "run_logged", lambda cmd, **kwargs: calls.append(cmd) or result())
    monkeypatch.setattr(snapshots, "ssh_run_args", lambda user, host, port, cmd, **kwargs: calls.append(cmd) or result())
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda *args, **kwargs: 1024)
    if creator == "autosnap":
        name = autosnap.create_snapshot("tank/data", False, "job-a", custom_name, tier_idx=tier_idx)
    elif creator == "local":
        name = snapshots.create_snapshot_local("tank/data", False, "job-a", custom_name, tier_idx=tier_idx)
    else:
        name = snapshots.create_snapshot_remote(
            "tank/data", False, "job-a", custom_name, "user", "host", "22", tier_idx=tier_idx
        )
    assert name == f"tank/data@{prefix}-2026.08.04-15.16.17"
    assert calls[0] == ["zfs", "snapshot", name]
    assert ["zfs", "set", f"{TASK_PROP}=job-a", name] in calls
    if tier_idx is not None:
        assert ["zfs", "set", f"{TIER_PROP}=t{tier_idx}", name] in calls


@pytest.mark.parametrize("timestamp", ["2026-08-04_01.02.03", "2026.08.04-01.02.03"])
@pytest.mark.parametrize("prefix", ["job-a", "job-a-t2", "daily", "daily-t2", "daily-job-a"])
def test_autosnap_recognizes_both_timestamp_formats(autosnap, timestamp, prefix):
    assert autosnap._is_autosnap_task_snapshot(f"tank/data@{prefix}-{timestamp}", "job-a", "daily")


@pytest.mark.parametrize("name", [
    "tank/data@daily-offsite-2026.08.04-01.02.03",
    "tank/data@daily-offsite-t2-2026-08-04_01.02.03",
    "tank/data@daily-2-2026.08.04-01.02.03",
    "tank/data@dailyx-2026.08.04-01.02.03",
    "tank/data@daily-manual",
])
def test_name_fallback_does_not_claim_sibling_prefix_tasks(autosnap, name):
    assert not autosnap._is_autosnap_task_snapshot(name, "daily")
    assert not snapshots.is_task_snapshot(name, "daily")


@pytest.mark.parametrize("engine", ["autosnap", "local", "remote"])
def test_retention_handles_mixed_formats_without_claiming_foreign_snapshots(
    monkeypatch, autosnap, fixed_snapshot_time, engine
):
    names = [
        "tank/data@job-a-2026-01-01_00.00.00",
        "tank/data@job-a-2026.01.02-00.00.00",
        "tank/data@daily-t2-2026-01-03_00.00.00",
        "tank/data@daily-t2-2026.01.04-00.00.00",
        "tank/data@job-a-2026.01.05-00.00.00",
        "tank/data@foreign-2026.01.06-00.00.00",
        "tank/data@job-a-2026.08.04-15.16.17",
    ]
    values = [snap(name, age_days=100) for name in names]
    values[4].task_tag = "other-task"
    values[5].task_tag = "job-a"
    values[6].creation = datetime.datetime.now()
    values[6].creation_epoch = int(values[6].creation.timestamp())
    excluded = names[3]
    deleted = []
    if engine == "autosnap":
        inventory = [
            autosnap.Snapshot(value.name, value.guid, value.creation_epoch, value.task_tag, value.tier_tag)
            for value in values
        ]
        monkeypatch.setattr(autosnap, "get_local_snapshots", lambda fs: inventory)
        monkeypatch.setattr(autosnap, "safe_destroy", lambda name: deleted.append(name) or True)
        autosnap.prune_snapshots_by_retention("tank/data", "job-a", 5, "days", excluded, custom_name="daily")
    else:
        monkeypatch.setattr(retention, "get_local_snapshots", lambda fs: values)
        monkeypatch.setattr(retention, "get_remote_snapshots", lambda *args: values)
        monkeypatch.setattr(retention, "safe_destroy_batch", lambda names, *args: deleted.extend(names) or set(names))
        retention.prune_snapshots_by_retention(
            "tank/data", "job-a", 5, "days", excluded, custom_name="daily",
            remote_user="user", remote_host="host" if engine == "remote" else None,
        )
    assert set(deleted) == {names[0], names[1], names[2], names[5]}


def test_snapshot_line_parsing_and_dataset_helpers():
    parsed = snapshots.parse_snapshot_line("tank/data@s1\tguid 1\t1700000000\t123")
    assert parsed.name == "tank/data@s1"
    assert parsed.guid == "guid 1"
    assert parsed.creation_epoch == 1700000000
    assert parsed.order_key == 123
    assert snapshots.parse_snapshot_line("bad") is None
    assert snapshots.snapshot_suffix("tank/data@s1") == "s1"
    assert snapshots.dataset_of_snapshot("tank/data@s1") == "tank/data"


@pytest.mark.parametrize("timestamp", ["2026-08-04", "2026-08-04_01.02.03", "2026.08.04-01.02.03"])
def test_task_snapshot_matching_does_not_claim_other_tasks(timestamp):
    assert snapshots.is_task_snapshot(f"tank/data@backup-{timestamp}", "backup")
    assert snapshots.is_task_snapshot(f"tank/data@pretty-t2-{timestamp}", "backup", "pretty")
    assert snapshots.is_task_snapshot(f"tank/data@pretty-backup-{timestamp}", "backup", "pretty")
    assert not snapshots.is_task_snapshot(f"tank/data@backup2-{timestamp}", "backup")
    assert not snapshots.is_task_snapshot("tank/data@anything", "")


@pytest.mark.parametrize("timestamp", ["2026-08-04_01.02.03", "2026.08.04-01.02.03"])
def test_task_snapshot_matching_does_not_claim_sibling_task_sharing_a_prefix(timestamp):
    assert snapshots.is_task_snapshot(f"tank/data@backup-t1-{timestamp}", "backup")
    assert snapshots.is_task_snapshot(f"tank/data@backup-daily-{timestamp}", "backup-daily")
    assert not snapshots.is_task_snapshot(f"tank/data@backup-daily-{timestamp}", "backup")
    assert not snapshots.is_task_snapshot(f"tank/data@backup-daily-t1-{timestamp}", "backup")


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


def test_create_local_snapshot_builds_recursive_name_and_tags_whole_tree(monkeypatch):
    calls = []
    suffix = "daily-t2-2026.08.04-15.16.17"
    listing = "\n".join([
        f"tank/data@{suffix}",
        f"tank/data/samba@{suffix}",
        f"tank/data/media@{suffix}",
        "tank/data@unrelated-2026-01-01_00.00.00",
    ])

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 4, 15, 16, 17)

    def fake_run_logged(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["zfs", "list"]:
            return result(stdout=listing)
        return result()

    monkeypatch.setattr(snapshots.datetime, "datetime", FixedDateTime)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda *args, **kwargs: 1024)
    monkeypatch.setattr(snapshots, "run_logged", fake_run_logged)
    name = snapshots.create_snapshot_local("tank/data", True, "job-a", custom_name="daily", tier_idx=2)
    assert name == f"tank/data@{suffix}"

    targets = [f"tank/data@{suffix}", f"tank/data/samba@{suffix}", f"tank/data/media@{suffix}"]
    assert calls == [
        ["zfs", "snapshot", "-r", name],
        ["zfs", "list", "-H", "-o", "name", "-t", "snapshot", "-r", "tank/data"],
        ["zfs", "set", f"{TASK_PROP}=job-a"] + targets,
        ["zfs", "set", f"{TIER_PROP}=t2"] + targets,
    ]


def test_non_recursive_snapshot_tags_only_its_own_snapshot(monkeypatch):
    calls = []

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 4, 15, 16, 17)

    monkeypatch.setattr(snapshots.datetime, "datetime", FixedDateTime)
    monkeypatch.setattr(snapshots, "get_available_bytes", lambda *args, **kwargs: 1024)
    monkeypatch.setattr(snapshots, "run_logged", lambda cmd, **kwargs: calls.append(cmd) or result())
    name = snapshots.create_snapshot_local("tank/data", False, "job-a")
    assert calls == [
        ["zfs", "snapshot", name],
        ["zfs", "set", f"{TASK_PROP}=job-a", name],
    ]


def test_tag_received_snapshots_tags_every_received_dataset(monkeypatch):
    calls = []
    suffix = "job-a-2026-08-04_15.16.17"
    listing = "\n".join([
        f"backup/data@{suffix}",
        f"backup/data/samba@{suffix}",
    ])

    def fake_run_logged(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["zfs", "list"]:
            return result(stdout=listing)
        return result()

    monkeypatch.setattr(snapshots, "run_logged", fake_run_logged)
    snapshots.tag_received_snapshots("backup/data", suffix, "job-a", tier_idx=1, recursive=True)

    targets = [f"backup/data@{suffix}", f"backup/data/samba@{suffix}"]
    assert calls == [
        ["zfs", "list", "-H", "-o", "name", "-t", "snapshot", "-r", "backup/data"],
        ["zfs", "set", f"{TASK_PROP}=job-a"] + targets,
        ["zfs", "set", f"{TIER_PROP}=t1"] + targets,
    ]


def test_tagging_falls_back_to_root_when_listing_fails(monkeypatch):
    calls = []

    def fake_run_logged(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["zfs", "list"]:
            return result(returncode=1, stderr="cannot open")
        return result()

    monkeypatch.setattr(snapshots, "run_logged", fake_run_logged)
    snapshots.tag_received_snapshots("backup/data", "job-a-2026-08-04_15.16.17", "job-a", recursive=True)
    assert calls[-1] == ["zfs", "set", f"{TASK_PROP}=job-a", "backup/data@job-a-2026-08-04_15.16.17"]


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
    monkeypatch.setattr(retention, "safe_destroy_batch", lambda names, *args: deleted.extend(names) or set(names))
    monkeypatch.setattr(retention, "notifier", recorder)
    final = retention.prune_snapshots_by_retention(
        "tank/data", "job-a", 5, "days", "tank/data@job-a-current", progress_base=10, progress_span=40, tier_idx=1
    )
    assert deleted == ["tank/data@job-a-old"]
    assert final == 50
    assert recorder.messages[-1].endswith("50% complete")


def test_retention_child_snapshots_inherit_root_task_and_tier_tags(monkeypatch):
    values = [
        snap("tank/data@job-a-t0-old", age_days=10, task_tag="job-a", tier_tag="t0"),
        snap("tank/data/samba@job-a-t0-old", age_days=10),
        snap("tank/data@job-a-t1-old", age_days=10, task_tag="job-a", tier_tag="t1"),
        snap("tank/data/samba@job-a-t1-old", age_days=10),
    ]
    deleted = []
    monkeypatch.setattr(retention, "get_local_snapshots", lambda fs: values)
    monkeypatch.setattr(retention, "safe_destroy_batch", lambda names, *args: deleted.extend(names) or set(names))
    retention.prune_snapshots_by_retention("tank/data", "job-a", 5, "days", "", tier_idx=1)
    assert deleted == ["tank/data@job-a-t1-old", "tank/data/samba@job-a-t1-old"]


def test_retention_does_not_name_match_snapshot_tagged_to_another_task(monkeypatch):
    old = snap("tank/data@job-a-2026-01-01", age_days=100, task_tag="job-b")
    deleted = []
    monkeypatch.setattr(retention, "get_local_snapshots", lambda fs: [old])
    monkeypatch.setattr(retention, "safe_destroy_batch", lambda names, *args: deleted.extend(names) or set(names))
    assert retention.prune_snapshots_by_retention("tank/data", "job-a", 1, "days", "") == 100
    assert deleted == []


class FakeZfs:
    """Stands in for local `zfs` and remote ssh calls, recording each argv."""

    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])

    def reply(self, cmd):
        self.calls.append(cmd)
        return self.replies.pop(0) if self.replies else result()

    def install(self, monkeypatch):
        monkeypatch.setattr(retention.subprocess, "run", lambda cmd, **kwargs: self.reply(cmd))
        monkeypatch.setattr(retention, "ssh_run_args", lambda user, host, port, cmd, **kwargs: self.reply(cmd))
        return self


def test_destroy_batches_group_by_dataset_and_cap_size():
    names = [f"tank/a@s{i}" for i in range(250)] + ["tank/a/child@s1", "tank/a@late"]
    batches = list(retention.destroy_batches(names))
    assert [len(b) for b in batches] == [100, 100, 51, 1]
    assert batches[2][-1] == "tank/a@late"
    assert batches[3] == ["tank/a/child@s1"]


@pytest.mark.parametrize("remote", [False, True])
def test_full_send_wipe_destroys_in_batches(monkeypatch, remote):
    fake = FakeZfs().install(monkeypatch)
    snaps = [snap(f"tank/backup@s{i}") for i in range(150)] + [snap("tank/backup/child@c1")]
    kwargs = {"remote_user": "root", "remote_host": "10.0.0.1"} if remote else {}
    assert retention.destroy_snapshots_with_progress(snaps, "tank/backup", **kwargs) == 151
    assert len(fake.calls) == 3
    assert fake.calls[0][:3] == ["zfs", "destroy", "-R"]
    assert fake.calls[0][3] == "tank/backup@" + ",".join(f"s{i}" for i in range(100))
    assert fake.calls[2] == ["zfs", "destroy", "-R", "tank/backup/child@c1"]


def test_full_send_wipe_stops_and_raises_when_snapshots_remain(monkeypatch):
    fake = FakeZfs([
        result(),
        result(255, stderr="ssh: connect to host 10.0.0.1 port 22: Connection reset by peer"),
        result(0, stdout="tank/backup@s150\n"),
    ]).install(monkeypatch)
    snaps = [snap(f"tank/backup@s{i}") for i in range(300)]
    with pytest.raises(retention.SnapshotDestroyError) as excinfo:
        retention.destroy_snapshots_with_progress(snaps, "tank/backup", remote_user="root", remote_host="10.0.0.1")
    assert "Connection reset by peer" in str(excinfo.value)
    assert "100/300" in str(excinfo.value)
    assert excinfo.value.held is False
    # The third batch is never attempted once the second one fails.
    assert [call[:2] for call in fake.calls[2:]] == [["zfs", "list"], ["zfs", "holds"]]


def test_full_send_wipe_skips_child_snapshots_removed_with_parent(monkeypatch):
    fake = FakeZfs().install(monkeypatch)
    snaps = [snap("tank/backup@s1"), snap("tank/backup@s2"),
             snap("tank/backup/child@s1"), snap("tank/backup/child@s2"), snap("tank/backup/child@only")]
    assert retention.destroy_snapshots_with_progress(snaps, "tank/backup") == 5
    assert fake.calls == [
        ["zfs", "destroy", "-R", "tank/backup@s1,s2"],
        ["zfs", "destroy", "-R", "tank/backup/child@only"],
    ]


def test_full_send_wipe_failure_counts_children_removed_with_parent(monkeypatch):
    FakeZfs([
        result(),
        result(255, stderr="Connection reset by peer"),
        result(0, stdout="tank/backup@s150\n"),
    ]).install(monkeypatch)
    snaps = [snap(f"{ds}@s{i}") for ds in ("tank/backup", "tank/backup/child") for i in range(200)]
    with pytest.raises(retention.SnapshotDestroyError) as excinfo:
        retention.destroy_snapshots_with_progress(snaps, "tank/backup", remote_user="u", remote_host="h")
    # The first root batch also took s0..s99 off the child dataset.
    assert "Stopped after destroying 200/400" in str(excinfo.value)


def test_full_send_wipe_names_user_holds_instead_of_busy(monkeypatch):
    FakeZfs([
        result(1, stderr="cannot destroy snapshot tank/backup@s2: dataset is busy"),
        result(0, stdout="tank/backup@s1\ntank/backup@s2\n"),
        result(0, stdout="tank/backup@s2\tkeep-me\tThu Oct 29 2026\n"),
    ]).install(monkeypatch)
    with pytest.raises(retention.SnapshotDestroyError) as excinfo:
        retention.destroy_snapshots_with_progress([snap("tank/backup@s1"), snap("tank/backup@s2")], "tank/backup")
    message = str(excinfo.value)
    assert excinfo.value.held is True
    assert "user holds (e.g. tank/backup@s2, hold tag: keep-me)" in message
    assert "zfs release" in message
    assert "dataset is busy" not in message


def test_full_send_wipe_raises_when_remaining_cannot_be_listed(monkeypatch):
    FakeZfs([result(255, stderr="Connection reset by peer"), result(255, stderr="Connection reset by peer")]).install(monkeypatch)
    with pytest.raises(retention.SnapshotDestroyError):
        retention.destroy_snapshots_with_progress([snap("d@s1")], "d", remote_user="u", remote_host="h")


def test_full_send_wipe_treats_already_missing_snapshots_as_cleared(monkeypatch):
    FakeZfs([result(1, stderr="could not find any snapshots to destroy"), result(0, stdout="d@other\n")]).install(monkeypatch)
    assert retention.destroy_snapshots_with_progress([snap("d@s1"), snap("d@s2")], "d") == 2


def test_safe_destroy_batch_skips_held_snapshots(monkeypatch):
    fake = FakeZfs([result(0, stdout="tank/data@s2\tkeep\tThu Jan 1 2026\n")]).install(monkeypatch)
    gone = retention.safe_destroy_batch(["tank/data@s1", "tank/data@s2", "tank/data@s3"])
    assert gone == {"tank/data@s1", "tank/data@s3"}
    assert fake.calls == [
        ["zfs", "holds", "-H", "tank/data@s1", "tank/data@s2", "tank/data@s3"],
        ["zfs", "destroy", "tank/data@s1,s3"],
    ]


def test_safe_destroy_batch_falls_back_to_single_destroys_on_batch_failure(monkeypatch):
    fake = FakeZfs([
        result(),
        result(1, stderr="cannot destroy snapshot tank/data@s2: snapshot has dependent clones"),
        result(0, stdout="tank/data@s1\ntank/data@s2\ntank/data@s3\n"),
        result(),
        result(1, stderr="snapshot has dependent clones"),
        result(),
    ]).install(monkeypatch)
    gone = retention.safe_destroy_batch(["tank/data@s1", "tank/data@s2", "tank/data@s3"],
                                        "root", "10.0.0.1", "22")
    assert gone == {"tank/data@s1", "tank/data@s3"}
    assert fake.calls[3:] == [
        ["zfs", "destroy", "tank/data@s1"],
        ["zfs", "destroy", "tank/data@s2"],
        ["zfs", "destroy", "tank/data@s3"],
    ]


def test_prune_destroys_in_batches_and_counts_skipped(monkeypatch):
    values = [snap(f"tank/data@job-a-{i}", age_days=10, task_tag="job-a") for i in range(120)]
    batches = []

    def fake_batch(names, *args):
        batches.append(list(names))
        return set(names[1:])

    monkeypatch.setattr(retention, "get_remote_snapshots", lambda *args: values)
    monkeypatch.setattr(retention, "safe_destroy_batch", fake_batch)
    recorder = RecordingNotifier()
    monkeypatch.setattr(retention, "notifier", recorder)
    retention.prune_snapshots_by_retention("tank/data", "job-a", 1, "days", "",
                                           remote_user="root", remote_host="10.0.0.1")
    assert [len(b) for b in batches] == [100, 20]
    assert "Pruned 118 snapshots" in recorder.messages[-1]
    assert "Skipped 2" in recorder.messages[-1]
