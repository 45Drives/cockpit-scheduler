import copy
import importlib.util
import io
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "zfs-replication-consolidate.py"
SPEC = importlib.util.spec_from_file_location("zfs_replication_consolidate", SCRIPT)
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


def snapshot(name, guid, txg):
    return {"name": name, "guid": guid, "txg": txg}


def dataset(*snapshots):
    return {"type": "filesystem", "origin": "-", "encryption": "off", "token": "-", "snapshots": list(snapshots)}


@pytest.fixture
def config():
    return {
        "source_root": "source", "destination_root": "backup/tree", "snapshot": "migration-to-recursive",
        "ssh": "backup-test", "port": 22, "identity": None,
    }


class MemoryTransport:
    def __init__(self):
        self.source = {
            "source": dataset(snapshot("source@root-old", "1", 10)),
            "source/child": dataset(snapshot("source/child@child-old", "2", 11)),
        }
        self.destination = {
            "backup/tree": dataset(snapshot("backup/tree@root-old", "1", 20)),
            "backup/tree/child": dataset(snapshot("backup/tree/child@child-old", "2", 21)),
        }
        self.writes = 0
        self.transfers = []

    def inventory(self, root, remote=False):
        data = self.destination if remote else self.source
        return copy.deepcopy({name: value for name, value in data.items() if name == root or name.startswith(root + "/")})

    def written(self, dataset_name, snapshot_name):
        return self.writes

    def query(self, args, remote=False):
        assert args[:3] == ["zfs", "send", "-nPv"]
        return "size\t100"

    def transfer(self, base, target, destination):
        self.transfers.append((base, target, destination))
        source_name = target.split("@", 1)[0]
        new_source = next(item for item in self.source[source_name]["snapshots"] if item["name"] == target)
        self.destination[destination]["snapshots"].append(
            snapshot(destination + "@migration-to-recursive", new_source["guid"], 50)
        )

    def add_migration(self):
        for index, (name, value) in enumerate(self.source.items()):
            value["snapshots"].append(snapshot(name + "@migration-to-recursive", str(100 + index), 30))


def test_plan_uses_independent_guid_matched_bases(config):
    transport = MemoryTransport()
    plan = migration.build_plan(transport, config)
    assert not plan["blockers"]
    assert {row["base_source"] for row in plan["datasets"]} == {"source@root-old", "source/child@child-old"}
    assert transport.transfers == []


@pytest.mark.parametrize("problem", ["missing-root-base", "guid", "writes", "encrypted", "clone", "pending", "missing-child", "extra-child"])
def test_plan_blocks_unsafe_states(config, problem):
    transport = MemoryTransport()
    root = transport.destination["backup/tree"]
    if problem == "missing-root-base":
        root["snapshots"] = []
    elif problem == "guid":
        root["snapshots"][0]["guid"] = "999"
    elif problem == "writes":
        transport.writes = 1
    elif problem == "encrypted":
        root["encryption"] = "aes-256-gcm"
    elif problem == "clone":
        root["origin"] = "backup/other@old"
    elif problem == "pending":
        root["token"] = "unfinished"
    elif problem == "missing-child":
        del transport.destination["backup/tree/child"]
    else:
        transport.destination["backup/tree/extra"] = dataset()
    assert migration.build_plan(transport, config)["blockers"]
    assert transport.transfers == []


def test_requires_complete_recursive_migration_set(config):
    transport = MemoryTransport()
    transport.add_migration()
    transport.source["source/child"]["snapshots"][-1]["txg"] = 31
    assert migration.build_plan(transport, config, True)["blockers"]


def test_apply_verifies_and_restart_skips_completed_transfers(config):
    transport = MemoryTransport()
    approved = migration.build_plan(transport, config)
    transport.add_migration()
    log = io.StringIO()
    migration.apply_plan(transport, approved, log)
    assert len(transport.transfers) == 2
    assert log.getvalue().count('"status": "VERIFIED"') == 2
    migration.apply_plan(transport, approved, log)
    assert len(transport.transfers) == 2
    assert log.getvalue().count('"status": "SKIPPED"') == 2


def test_apply_blocks_entire_batch_before_any_transfer(config):
    transport = MemoryTransport()
    approved = migration.build_plan(transport, config)
    transport.add_migration()
    transport.destination["backup/tree/child"]["token"] = "partial"
    with pytest.raises(migration.MigrationError, match="Preflight blocked"):
        migration.apply_plan(transport, approved, io.StringIO())
    assert transport.transfers == []


def test_changed_base_is_not_silently_accepted(config):
    transport = MemoryTransport()
    approved = migration.build_plan(transport, config)
    transport.add_migration()
    transport.source["source/child"]["snapshots"].insert(1, snapshot("source/child@other", "3", 12))
    transport.destination["backup/tree/child"]["snapshots"].append(snapshot("backup/tree/child@other", "3", 22))
    with pytest.raises(migration.MigrationError, match="Starting snapshot changed"):
        migration.apply_plan(transport, approved, io.StringIO())
    assert transport.transfers == []


def test_transfer_failure_stops_batch_and_logs_failure(config):
    transport = MemoryTransport()
    approved = migration.build_plan(transport, config)
    transport.add_migration()
    def fail(base, target, destination):
        raise migration.MigrationError("receive failed")
    transport.transfer = fail
    log = io.StringIO()
    with pytest.raises(migration.MigrationError, match="receive failed"):
        migration.apply_plan(transport, approved, log)
    assert '"status": "FAILED"' in log.getvalue()


def test_ssh_arguments_are_quoted_and_noninteractive(config):
    transport = migration.Transport(config)
    command = transport.command(["zfs", "get", "written@snap", "backup/tree"], True)
    assert "BatchMode=yes" in command
    assert "StrictHostKeyChecking=yes" in command
    assert command[-1] == "zfs get written@snap backup/tree"
    config["ssh"] = "-oProxyCommand=unexpected"
    with pytest.raises(migration.MigrationError):
        migration.Transport(config)