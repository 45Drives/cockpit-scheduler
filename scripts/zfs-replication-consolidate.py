#!/usr/bin/env python3
"""Plan and run non-destructive, unencrypted ZFS replication consolidation."""

import argparse
import datetime
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


DATASET_PATTERN = r"[A-Za-z][A-Za-z0-9_.:-]*(?:/[A-Za-z0-9_.:-]+)*"
SNAPSHOT_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_.:-]*"


class MigrationError(Exception):
    pass


def validate_config(config):
    for key in ("source_root", "destination_root"):
        if not isinstance(config.get(key), str) or not re.fullmatch(DATASET_PATTERN, config[key]):
            raise MigrationError(f"Invalid {key}; use an actual ZFS dataset path.")
    if not isinstance(config.get("snapshot"), str) or not re.fullmatch(SNAPSHOT_PATTERN, config["snapshot"]):
        raise MigrationError("Invalid migration snapshot suffix.")
    if not isinstance(config.get("ssh"), str) or not re.fullmatch(
        r"(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9][A-Za-z0-9.:-]*", config["ssh"]
    ):
        raise MigrationError("Invalid SSH destination; use an SSH alias or user@host.")
    if type(config.get("port")) is not int or not 1 <= config["port"] <= 65535:
        raise MigrationError("SSH port must be between 1 and 65535.")
    if config.get("identity") is not None and not isinstance(config["identity"], str):
        raise MigrationError("Invalid SSH identity path.")


class Transport:
    def __init__(self, config):
        validate_config(config)
        self.config = config

    def command(self, args, remote=False):
        if not remote:
            return args
        command = [
            "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=15", "-p", str(self.config["port"]),
        ]
        if self.config.get("identity"):
            command += ["-i", str(Path(self.config["identity"]).expanduser())]
        return command + [self.config["ssh"], " ".join(shlex.quote(arg) for arg in args)]

    def query(self, args, remote=False):
        result = subprocess.run(
            self.command(args, remote), capture_output=True, text=True, timeout=120,
        )
        if result.returncode:
            raise MigrationError(result.stderr.strip() or f"Command failed: {args}")
        return result.stdout.strip()

    def inventory(self, root, remote=False):
        datasets = {}
        output = self.query([
            "zfs", "list", "-H", "-p", "-r", "-t", "filesystem,volume",
            "-o", "name,type,origin,encryption,receive_resume_token", root,
        ], remote)
        for line in output.splitlines():
            name, kind, origin, encryption, token = line.split("\t")
            datasets[name] = {
                "type": kind, "origin": origin, "encryption": encryption,
                "token": token, "snapshots": [],
            }
        if root not in datasets:
            raise MigrationError(f"Root dataset not found: {root}")
        output = self.query([
            "zfs", "list", "-H", "-p", "-r", "-t", "snapshot",
            "-o", "name,guid,createtxg", root,
        ], remote)
        for line in output.splitlines():
            name, guid, txg = line.split("\t")
            dataset = name.split("@", 1)[0]
            if dataset not in datasets:
                raise MigrationError(f"Snapshot dataset is absent from inventory: {name}")
            datasets[dataset]["snapshots"].append({"name": name, "guid": guid, "txg": int(txg)})
        for dataset in datasets.values():
            dataset["snapshots"].sort(key=lambda snapshot: snapshot["txg"])
        return datasets

    def written(self, dataset, snapshot):
        suffix = snapshot.split("@", 1)[1]
        value = self.query(["zfs", "get", "-H", "-p", "-o", "value", f"written@{suffix}", dataset], True)
        if not value.isdigit():
            raise MigrationError(f"Cannot verify backup writes: {dataset}")
        return int(value)

    def transfer(self, base, target, destination):
        sender = subprocess.Popen(["zfs", "send", "-i", base, target], stdout=subprocess.PIPE)
        receiver = None
        try:
            receiver = subprocess.Popen(
                self.command(["zfs", "receive", "-s", "-u", destination], True),
                stdin=sender.stdout,
            )
            sender.stdout.close()
            receive_status = receiver.wait()
            if receive_status and sender.poll() is None:
                sender.terminate()
            send_status = sender.wait()
            if send_status or receive_status:
                raise MigrationError(
                    f"Transfer failed (send={send_status}, receive={receive_status}). "
                    "Review partial receive state before restarting."
                )
        finally:
            if sender.stdout:
                sender.stdout.close()
            for process in (receiver, sender):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()


def inspect_row(transport, config, source_name, source, destination_name, destination):
    row = {
        "source": source_name, "destination": destination_name, "status": "BLOCKED",
        "base_source": None, "base_destination": None, "base_guid": None,
        "migration_guid": None, "reason": "",
    }
    if destination is None:
        row["reason"] = "Backup dataset missing; full seed requires separate approval."
        return row
    for label, dataset in (("Source", source), ("Backup", destination)):
        if dataset["encryption"] != "off" or dataset["origin"] != "-" or dataset["token"] != "-":
            row["reason"] = f"{label} has encryption, a clone origin, or a pending receive."
            return row
    if source["type"] != destination["type"]:
        row["reason"] = "Source and backup dataset types differ."
        return row
    target = f"{source_name}@{config['snapshot']}"
    new_source = next((snapshot for snapshot in source["snapshots"] if snapshot["name"] == target), None)
    row["migration_guid"] = new_source["guid"] if new_source else None
    destination_target = f"{destination_name}@{config['snapshot']}"
    new_destination = next(
        (snapshot for snapshot in destination["snapshots"] if snapshot["name"] == destination_target), None,
    )
    if not destination["snapshots"]:
        row["reason"] = "No backup snapshots; root/parent/full seed needs separate approval."
        return row
    latest = destination["snapshots"][-1]
    if new_destination:
        if not new_source or new_destination["guid"] != new_source["guid"] or latest != new_destination:
            row["reason"] = "Migration snapshot mismatched or not the latest backup snapshot."
            return row
        if transport.written(destination_name, latest["name"]):
            row["reason"] = "Backup modified after the migration snapshot."
            return row
        row["status"] = "COMPLETE"
        return row
    base = next((snapshot for snapshot in source["snapshots"] if snapshot["guid"] == latest["guid"]), None)
    if not base:
        row["reason"] = "Latest backup snapshot is not shared with the source."
        return row
    if new_source and base["txg"] >= new_source["txg"]:
        row["reason"] = "Starting snapshot is not older than the migration snapshot."
        return row
    if transport.written(destination_name, latest["name"]):
        row["reason"] = "Backup modified after the starting snapshot."
        return row
    row.update(status="READY", base_source=base["name"], base_destination=latest["name"], base_guid=base["guid"])
    return row


def build_plan(transport, config, require_snapshot=False):
    source = transport.inventory(config["source_root"])
    destination = transport.inventory(config["destination_root"], True)
    rows = []
    mapped = set()
    migration_txgs = set()
    for name, dataset in sorted(source.items()):
        relative = name[len(config["source_root"]):]
        mapped_name = config["destination_root"] + relative
        mapped.add(mapped_name)
        row = inspect_row(transport, config, name, dataset, mapped_name, destination.get(mapped_name))
        target = next(
            (snapshot for snapshot in dataset["snapshots"] if snapshot["name"] == f"{name}@{config['snapshot']}"), None,
        )
        if target:
            migration_txgs.add(target["txg"])
        elif require_snapshot:
            row.update(status="BLOCKED", reason="Source migration snapshot missing.")
        rows.append(row)
    blockers = [f"{row['source']}: {row['reason']}" for row in rows if row["status"] == "BLOCKED"]
    extras = sorted(set(destination) - mapped)
    if extras:
        blockers.append("Backup-only datasets require review: " + ", ".join(extras))
    target_count = sum(row["migration_guid"] is not None for row in rows)
    if target_count and (target_count != len(rows) or len(migration_txgs) != 1):
        blockers.append("Migration snapshots are not one complete recursive snapshot set.")
    return {"version": 1, "config": config, "datasets": rows, "blockers": blockers}


def check_approved(approved, current):
    if approved.get("version") != 1 or approved.get("blockers"):
        raise MigrationError("Plan is unsupported or has blockers; resolve them and generate a new plan.")
    if current["blockers"]:
        raise MigrationError("Preflight blocked:\n" + "\n".join(current["blockers"]))
    old_rows = {row["source"]: row for row in approved["datasets"]}
    new_rows = {row["source"]: row for row in current["datasets"]}
    if set(old_rows) != set(new_rows):
        raise MigrationError("Dataset hierarchy changed; generate and review a new plan.")
    for name, row in new_rows.items():
        old = old_rows[name]
        if old["destination"] != row["destination"]:
            raise MigrationError(f"Destination mapping changed: {name}")
        if old.get("migration_guid") and old["migration_guid"] != row["migration_guid"]:
            raise MigrationError(f"Migration snapshot identity changed: {name}")
        if row["status"] != "COMPLETE":
            if old["status"] != "READY" or any(
                old.get(key) != row.get(key) for key in ("base_source", "base_destination", "base_guid")
            ):
                raise MigrationError(f"Starting snapshot changed: {name}; review a new plan.")


def write_event(log, row, status, message=""):
    event = {
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": row["source"], "destination": row["destination"],
        "status": status, "message": message,
    }
    log.write(json.dumps(event) + "\n")
    log.flush()
    print(f"{status}: {row['source']} -> {row['destination']} {message}", flush=True)


def apply_plan(transport, approved, log):
    config = approved["config"]
    current = build_plan(transport, config, require_snapshot=True)
    check_approved(approved, current)
    pinned = current
    for row in current["datasets"]:
        try:
            source = transport.inventory(row["source"])[row["source"]]
            destination = transport.inventory(row["destination"], True)[row["destination"]]
            fresh = inspect_row(transport, config, row["source"], source, row["destination"], destination)
            check_approved(
                {"version": 1, "datasets": [row], "blockers": []},
                {"datasets": [fresh], "blockers": [fresh["reason"]] if fresh["status"] == "BLOCKED" else []},
            )
            if fresh["status"] == "COMPLETE":
                write_event(log, row, "SKIPPED", "Matching migration snapshot already verified.")
                continue
            target = f"{row['source']}@{config['snapshot']}"
            estimate = transport.query(["zfs", "send", "-nPv", "-i", row["base_source"], target])
            write_event(log, row, "STARTED", estimate)
            transport.transfer(row["base_source"], target, row["destination"])
            destination = transport.inventory(row["destination"], True)[row["destination"]]
            verified = inspect_row(transport, config, row["source"], source, row["destination"], destination)
            if verified["status"] != "COMPLETE":
                raise MigrationError("Post-transfer verification failed: " + verified["reason"])
            write_event(log, row, "VERIFIED")
        except (MigrationError, OSError, subprocess.SubprocessError, KeyboardInterrupt) as error:
            write_event(log, row, "FAILED", str(error))
            raise
    final = build_plan(transport, config, require_snapshot=True)
    check_approved(pinned, final)
    if any(row["status"] != "COMPLETE" for row in final["datasets"]):
        raise MigrationError("Final hierarchy verification found incomplete transfers.")
    print("All migration snapshots verified. Test the recursive scheduler task before enabling its schedule.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    plan_parser = subparsers.add_parser("plan", help="Read-only inspection; write a JSON review plan.")
    plan_parser.add_argument("--source-root", required=True)
    plan_parser.add_argument("--destination-root", required=True)
    plan_parser.add_argument("--ssh", required=True)
    plan_parser.add_argument("--port", type=int, default=22)
    plan_parser.add_argument("--identity")
    plan_parser.add_argument("--snapshot", default="migration-to-recursive")
    plan_parser.add_argument("--output", required=True)
    for mode in ("apply", "verify"):
        command_parser = subparsers.add_parser(mode)
        command_parser.add_argument("--plan", required=True)
        if mode == "apply":
            command_parser.add_argument("--confirm", action="store_true", help="Approve the reviewed plan and start transfers.")
            command_parser.add_argument("--log", help="JSON-lines log; defaults to PLAN.log.jsonl.")
    args = parser.parse_args()
    try:
        if args.mode == "plan":
            config = {key: getattr(args, key) for key in ("source_root", "destination_root", "ssh", "port", "identity", "snapshot")}
            transport = Transport(config)
            plan = build_plan(transport, config)
            for row in plan["datasets"]:
                if row["status"] == "READY" and row["migration_guid"]:
                    target = f"{row['source']}@{config['snapshot']}"
                    row["estimate"] = transport.query(["zfs", "send", "-nPv", "-i", row["base_source"], target])
                print(f"{row['status']}: {row['source']} -> {row['destination']} {row['reason']}")
            with Path(args.output).open("x", encoding="utf-8") as output:
                json.dump(plan, output, indent=2)
                output.write("\n")
            print(f"Review plan: {args.output}")
            for blocker in plan["blockers"]:
                print("BLOCKER: " + blocker)
            if not any(row["migration_guid"] for row in plan["datasets"]):
                print("Migration snapshot not yet created; estimates require a new plan after snapshot creation.")
            return 2 if plan["blockers"] else 0
        approved = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        transport = Transport(approved["config"])
        if args.mode == "verify":
            current = build_plan(transport, approved["config"], require_snapshot=True)
            check_approved(approved, current)
            if any(row["status"] != "COMPLETE" for row in current["datasets"]):
                raise MigrationError("Some datasets still need their migration transfer.")
            print("All migration snapshots match; backup datasets are unchanged and have no pending receives.")
        else:
            if not args.confirm:
                raise MigrationError("Review the JSON plan first, then pass --confirm to start transfers.")
            with Path(args.log or args.plan + ".log.jsonl").open("a", encoding="utf-8") as log:
                apply_plan(transport, approved, log)
        return 0
    except (MigrationError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("STOPPED: Interrupted; inspect partial receive state before restarting.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())