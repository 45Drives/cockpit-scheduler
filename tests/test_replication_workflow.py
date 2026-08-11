import io
from types import SimpleNamespace

import pytest

from replication import main as replication_main
from replication import workflow
from replication.models import ReplicationRun, Snapshot


def snap(name, guid, epoch):
    return Snapshot(name, guid, None, creation_epoch=epoch, order_key=epoch)


def test_initialize_run_parses_environment_and_tier_retention(monkeypatch):
    env = {
        "taskName": "job-a",
        "zfsRepConfig_direction": "PUSH",
        "zfsRepConfig_sendOptions_recursive_flag": "true",
        "zfsRepConfig_sendOptions_customName_flag": "yes",
        "zfsRepConfig_sendOptions_customName": "daily",
        "zfsRepConfig_sendOptions_raw_flag": "1",
        "zfsRepConfig_sendOptions_compressed_flag": "on",
        "zfsRepConfig_sendOptions_includeIntermediateSnapshots": "false",
        "zfsRepConfig_sendOptions_transferMethod": "netcat",
        "zfsRepConfig_destDataset_port": "31337",
        "zfsRepConfig_destDataset_sshPort": "2222",
        "zfsRepConfig_sendOptions_mbufferSize": "0",
        "zfsRepConfig_sendOptions_mbufferUnit": "bad",
        "zfsRepConfig_sourceDataset_pool": "tank",
        "zfsRepConfig_sourceDataset_dataset": "tank/source",
        "zfsRepConfig_destDataset_pool": "backup",
        "zfsRepConfig_destDataset_dataset": "target",
    }
    for key in list(workflow.os.environ):
        if key.startswith("zfsRepConfig_") or key in ("taskName", "scheduleJsonPath"):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(workflow, "_apply_tcp_tuning", lambda: None)
    monkeypatch.setattr(workflow.os, "remove", lambda path: None)
    monkeypatch.setattr(workflow.os.path, "isfile", lambda path: False)
    monkeypatch.setattr(
        workflow,
        "load_schedule_json",
        lambda path: {
            "intervals": [
                {"retention": {"source": {"retentionTime": 1, "retentionUnit": "days"}}},
                {"retention": {"source": {"retentionTime": 7, "retentionUnit": "days"}, "destination": {"retentionTime": 14, "retentionUnit": "days"}}},
            ]
        },
    )
    monkeypatch.setattr(workflow, "match_current_tier", lambda intervals, now: 1)
    ctx = ReplicationRun()
    workflow._initialize_run(ctx)
    assert (ctx.sourceFilesystem, ctx.destFilesystem) == ("tank/source", "backup/target")
    assert (ctx.direction, ctx.transferMethod) == ("push", "netcat")
    assert (ctx.sshPort, ctx.dataPort) == ("2222", "31337")
    assert (ctx.mBufferSize, ctx.mBufferUnit) == ("1", "G")
    assert ctx.includeIntermediateSnapshots is False
    assert ctx.tier_idx == 1
    assert (ctx.sourceRetentionTime, ctx.destinationRetentionTime) == (7, 14)


def test_initialize_rejects_empty_source(monkeypatch):
    for key in list(workflow.os.environ):
        if key.startswith("zfsRepConfig_") or key in ("taskName", "scheduleJsonPath"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("zfsRepConfig_destDataset_pool", "backup")
    monkeypatch.setattr(workflow, "_apply_tcp_tuning", lambda: None)
    monkeypatch.setattr(workflow, "load_schedule_json", lambda path: None)
    with pytest.raises(RuntimeError, match="Source dataset is empty"):
        workflow._initialize_run(ReplicationRun())


def test_plan_new_destination_uses_full_send_without_force():
    ctx = ReplicationRun()
    ctx.destinationSnapshots = None
    workflow._plan_send(ctx)
    assert ctx.incrementalSnapName == ""
    assert ctx.forceOverwrite is False


def test_plan_existing_empty_destination_requires_explicit_overwrite():
    ctx = ReplicationRun()
    ctx.destinationSnapshots = []
    ctx.useExistingDest = True
    with pytest.raises(SystemExit) as exc:
        workflow._plan_send(ctx)
    assert exc.value.code == 2
    ctx.allowOverwrite = True
    workflow._plan_send(ctx)
    assert ctx.forceOverwrite is True


def test_plan_selects_newest_common_snapshot_and_detects_written_data(monkeypatch):
    ctx = ReplicationRun()
    ctx.sourceFilesystem = "tank/source"
    ctx.destFilesystem = "backup/target"
    ctx.allowOverwrite = True
    ctx.sourceSnapshots = [snap("tank/source@s1", "g1", 1), snap("tank/source@s2", "g2", 2)]
    ctx.destinationSnapshots = [snap("backup/target@s1", "g1", 1), snap("backup/target@s2", "g2", 2)]
    monkeypatch.setattr(workflow, "get_written_since_snapshot", lambda *args, **kwargs: 4096)
    workflow._plan_send(ctx)
    assert ctx.incrementalSnapName == "tank/source@s2"
    assert ctx.forceOverwrite is True


def test_plan_refuses_destination_ahead_without_overwrite():
    ctx = ReplicationRun()
    ctx.sourceSnapshots = [snap("tank/source@s1", "g1", 1)]
    ctx.destinationSnapshots = [snap("backup/target@s1", "g1", 1), snap("backup/target@foreign", "g9", 2)]
    with pytest.raises(SystemExit) as exc:
        workflow._plan_send(ctx)
    assert exc.value.code == 2


def test_create_and_transfer_push_reports_post_processing(monkeypatch, capsys):
    ctx = ReplicationRun()
    ctx.direction = "push"
    ctx.sourceFilesystem = "tank/source"
    ctx.destFilesystem = "backup/target"
    ctx.incrementalSnapName = "tank/source@s0"
    ctx.remoteHost = "host"
    ctx.remoteUser = "root"
    ctx.sshPort = "2222"
    calls = []
    monkeypatch.setattr(workflow, "create_snapshot_local", lambda *args, **kwargs: "tank/source@s1")
    monkeypatch.setattr(workflow, "snapshot_exists_on_destination", lambda *args, **kwargs: (False, "backup/target@s1"))
    monkeypatch.setattr(workflow, "send_snapshot_push", lambda *args, **kwargs: calls.append((args, kwargs)))
    workflow._create_and_transfer_snapshot(ctx)
    assert calls[0][0][:3] == ("tank/source@s1", "backup/target", "tank/source@s0")
    assert "Snapshot transfer completed" in capsys.readouterr().out


def test_resume_interrupted_receive_success_stops_normal_workflow(monkeypatch):
    ctx = ReplicationRun()
    ctx.direction = "push"
    ctx.destFilesystem = "backup/target"
    ctx.remoteHost = "host"
    monkeypatch.setattr(workflow, "get_receive_resume_token", lambda *args, **kwargs: "token")
    monkeypatch.setattr(workflow, "resume_receive_push", lambda *args, **kwargs: (True, ""))
    monkeypatch.setattr(workflow, "send_houston_notification", lambda payload: None)
    assert workflow._resume_interrupted_receive(ctx) is True


def test_resume_overwrite_requirement_is_refused_without_permission(monkeypatch):
    ctx = ReplicationRun()
    ctx.direction = "push"
    ctx.destFilesystem = "backup/target"
    monkeypatch.setattr(workflow, "get_receive_resume_token", lambda *args, **kwargs: "token")
    monkeypatch.setattr(workflow, "resume_receive_push", lambda *args, **kwargs: (False, "destination exists; must specify -F"))
    monkeypatch.setattr(workflow, "send_houston_notification", lambda payload: None)
    with pytest.raises(SystemExit) as exc:
        workflow._resume_interrupted_receive(ctx)
    assert exc.value.code == 2


def test_main_routes_unexpected_exception_to_failure_handler(monkeypatch):
    seen = []
    monkeypatch.setattr(replication_main, "run_replication", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(replication_main, "handle_failure", lambda ctx, error: seen.append((ctx, error)))
    replication_main.main()
    assert len(seen) == 1
    assert isinstance(seen[0][1], RuntimeError)


def test_apply_retention_skips_two_phase_progress_when_both_disabled(monkeypatch):
    ctx = ReplicationRun()
    ctx.taskName = "task-a"
    ctx.sourceFilesystem = "tank/source"
    ctx.destFilesystem = "tank/dest"
    ctx.sourceRetentionTime = 0
    ctx.sourceRetentionUnit = ""
    ctx.destinationRetentionTime = 0
    ctx.destinationRetentionUnit = ""
    ctx.schedule_data = None
    ctx.tier_idx = None

    prune_calls = []
    monkeypatch.setattr(workflow, "prune_snapshots_by_retention", lambda *args, **kwargs: prune_calls.append((args, kwargs)) or 0)
    monkeypatch.setattr(workflow, "_clear_pending_full_send", lambda task_name: None)
    monkeypatch.setattr(workflow, "open", lambda *args, **kwargs: io.StringIO(), raising=False)

    messages = []
    monkeypatch.setattr(workflow.notifier, "notify", lambda message: messages.append(message))

    workflow._apply_retention(ctx)

    assert ctx.current_pct == 100
    assert prune_calls == []
    assert any("Retention not configured on source or destination. Skipping pruning. 100% complete" in m for m in messages)
    assert messages[-1] == "STATUS=ZFS replication task completed. 100% complete"

