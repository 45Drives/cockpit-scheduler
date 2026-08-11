import datetime
import io
import sys
from pathlib import Path


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "system_files"
    / "opt"
    / "45drives"
    / "houston"
    / "scheduler"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))

from replication.config import as_bool, clamp_mbuffer, clamp_mbuffer_block, get_dest_ports, join_zfs_path
from replication import workflow as replication_workflow
from replication.models import ReplicationRun
from replication.planner import build_zfs_send_args
from replication.schedules import match_current_tier
from replication.snapshots import parse_snapshot_line


def test_join_zfs_path_handles_ui_dataset_forms():
    assert join_zfs_path("tank", "data") == "tank/data"
    assert join_zfs_path("tank", "tank/data") == "tank/data"
    assert join_zfs_path("tank", "tank") == "tank"
    assert join_zfs_path("", "tank/data") == "tank/data"


def test_boolean_and_destination_port_parsing(monkeypatch):
    assert as_bool("yes") is True
    assert as_bool("off", default=True) is False
    assert as_bool(None, default=True) is True

    monkeypatch.setenv("zfsRepConfig_destDataset_port", "9000")
    monkeypatch.setenv("zfsRepConfig_destDataset_sshPort", "2222")
    assert get_dest_ports("netcat") == ("2222", "9000")
    assert get_dest_ports("ssh") == ("2222", "9000")
    assert get_dest_ports("mbuffer") == ("2222", "9000")


def test_mbuffer_values_are_normalized():
    assert clamp_mbuffer("8", "m") == ("8", "M")
    assert clamp_mbuffer("0", "invalid") == ("1", "G")
    assert clamp_mbuffer_block("0", "invalid") == ("256", "k")


def test_send_planner_preserves_incremental_flags():
    assert build_zfs_send_args(
        "tank/data@new",
        "tank/data@old",
        recursive=True,
        compressed=True,
        raw=True,
        include_intermediates=True,
    ) == [
        "zfs",
        "send",
        "-R",
        "-Lce",
        "-w",
        "-I",
        "tank/data@old",
        "tank/data@new",
    ]


def test_snapshot_parser_prefers_txg_for_ordering():
    snap = parse_snapshot_line("tank/data@s1\tguid-1\t1700000000\t12345")
    assert snap.name == "tank/data@s1"
    assert snap.guid == "guid-1"
    assert snap.creation_epoch == 1700000000
    assert snap.order_key == 12345


def test_schedule_tier_selects_most_specific_match():
    intervals = [
        {"minute": {"value": "0"}, "hour": {"value": "*"}},
        {"minute": {"value": "0"}, "hour": {"value": "2"}},
    ]
    now = datetime.datetime(2026, 8, 4, 2, 0)
    assert match_current_tier(intervals, now) == 1


def test_orchestrator_runs_phases_in_order(monkeypatch):
    calls = []
    phases = [
        "_initialize_run",
        "_load_snapshot_inventory",
        "_announce_dry_run",
        "_plan_send",
        "_report_dry_run",
        "_create_and_transfer_snapshot",
        "_tag_received_snapshot",
        "_apply_retention",
    ]
    for phase in phases:
        monkeypatch.setattr(
            replication_workflow,
            phase,
            lambda ctx, phase=phase: calls.append(phase),
        )
    monkeypatch.setattr(
        replication_workflow,
        "_recover_pending_full_send",
        lambda ctx: calls.append("_recover_pending_full_send") or False,
    )
    monkeypatch.setattr(
        replication_workflow,
        "_resume_interrupted_receive",
        lambda ctx: calls.append("_resume_interrupted_receive") or False,
    )

    replication_workflow.run_replication(ReplicationRun())

    assert calls == [
        "_initialize_run",
        "_load_snapshot_inventory",
        "_recover_pending_full_send",
        "_resume_interrupted_receive",
        "_announce_dry_run",
        "_plan_send",
        "_report_dry_run",
        "_create_and_transfer_snapshot",
        "_tag_received_snapshot",
        "_apply_retention",
    ]


def test_completed_recovery_stops_remaining_phases(monkeypatch):
    calls = []
    monkeypatch.setattr(replication_workflow, "_initialize_run", lambda ctx: calls.append("initialize"))
    monkeypatch.setattr(replication_workflow, "_load_snapshot_inventory", lambda ctx: calls.append("inventory"))
    monkeypatch.setattr(replication_workflow, "_recover_pending_full_send", lambda ctx: True)
    monkeypatch.setattr(
        replication_workflow,
        "_resume_interrupted_receive",
        lambda ctx: calls.append("unexpected"),
    )

    replication_workflow.run_replication(ReplicationRun())

    assert calls == ["initialize", "inventory"]


def test_pending_snapshot_recovery_calls_snapshot_suffix_function(monkeypatch):
    ctx = ReplicationRun()
    ctx.taskName = "test-task"
    ctx.sourceFilesystem = "source/data"
    ctx.destFilesystem = "dest/data"
    monkeypatch.setattr(
        replication_workflow,
        "_read_pending_full_send",
        lambda task: {
            "snapshot": "source/data@snap-1",
            "destFilesystem": "dest/data",
            "sourceFilesystem": "source/data",
            "direction": "push",
        },
    )
    monkeypatch.setattr(
        replication_workflow,
        "snapshot_exists_on_destination",
        lambda *args, **kwargs: (True, "dest/data@snap-1"),
    )
    monkeypatch.setattr(replication_workflow, "_clear_pending_full_send", lambda task: None)

    assert replication_workflow._recover_pending_full_send(ctx) is False
    assert ctx.pending_state is None


def test_successful_retention_phase_prints_explicit_completion(monkeypatch, capsys):
    ctx = ReplicationRun()
    ctx.taskName = "test-task"
    ctx.sourceFilesystem = "source/data"
    ctx.destFilesystem = "destination/data"
    monkeypatch.setattr(
        replication_workflow,
        "prune_snapshots_by_retention",
        lambda *args, **kwargs: kwargs["progress_base"] + kwargs["progress_span"],
    )
    monkeypatch.setattr(replication_workflow, "_clear_pending_full_send", lambda task: None)
    monkeypatch.setattr(replication_workflow, "open", lambda *args, **kwargs: io.StringIO(), raising=False)

    replication_workflow._apply_retention(ctx)

    assert "ZFS replication task completed successfully: source/data -> destination/data" in capsys.readouterr().out
