#!/usr/bin/env python3
import subprocess
import sys
import datetime as dt
import json
import os
import re
from typing import List, Optional, Tuple

TASK_PROP = "com.45drives:task"
LEGACY_NAME_RE = re.compile(r'@(?:[^@]+-)?(?P<task>[^@]+)-\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}$')
ENABLE_LEGACY_FALLBACK = True

class Snapshot:
    def __init__(self, name: str, guid: str, creation_epoch: int, task_tag: Optional[str]):
        self.name = name
        self.guid = guid
        self.creation_epoch = creation_epoch
        self.task_tag = task_tag

def send_dbus_notification(payload, debug_log="/tmp/snapshot_debug.log"):
    try:
        dbus_script = "/opt/45drives/houston/houston-notify"
        subprocess.run([
            "python3",
            dbus_script,
            json.dumps(payload)
        ], stdout=open(debug_log, "a"), stderr=subprocess.STDOUT)
    except Exception as e:
        print(f"⚠️ Failed to send D-Bus notification: {e}")

def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

def create_snapshot(filesystem: str, is_recursive: bool, task_name: str, custom_name: Optional[str]) -> str:
    if not filesystem:
        print("ERROR: filesystem is empty", file=sys.stderr)
        sys.exit(1)

    ts = dt.datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
    snapname = f"{filesystem}@{(custom_name + '-' if custom_name else '')}{task_name}-{ts}"

    cmd = ["zfs", "snapshot"]
    if is_recursive:
        cmd.append("-r")
    cmd.append(snapname)

    try:
        res = run(cmd)
        print(f"Created snapshot: {snapname}")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: zfs snapshot failed: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    # Tag snapshot with our task property so we can safely identify it later
    try:
        run(["zfs", "set", f"{TASK_PROP}={task_name}", snapname])
    except subprocess.CalledProcessError as e:
        # Non-fatal, but warn so pruning by tag may skip this one
        print(f"WARNING: failed to tag snapshot {snapname}: {e.stderr.strip()}", file=sys.stderr)

    return snapname

def get_local_snapshots(filesystem: str) -> List[Snapshot]:
    """
    Use epoch for creation to avoid locale parsing.
    We also fetch our user property to filter reliably.
    """
    snaps: List[Snapshot] = []
    # names + GUIDs
    try:
        # -p makes numeric properties plain; list doesn't make creation epoch, so get via zfs get
        names = run(["zfs", "list", "-H", "-t", "snapshot", "-r", "-o", "name,guid", filesystem]).stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: zfs list failed: {e.stderr.strip()}", file=sys.stderr)
        return snaps

    if not names:
        return snaps

    # Build name->guid
    pairs: List[Tuple[str, str]] = []
    for line in names:
        parts = line.split("\t")
        if len(parts) == 2:
            pairs.append((parts[0], parts[1]))

    # Batch get creation as epoch (-p) and our tag property
    # Note: zfs get can accept multiple properties
    props_out = run(["zfs", "get", "-H", "-p", "-r", "-o", "name,property,value", "creation", filesystem]).stdout.splitlines()
    tag_out  = run(["zfs", "get", "-H", "-r", "-o", "name,property,value", TASK_PROP, filesystem]).stdout.splitlines()

    creation_map = {}
    for line in props_out:
        try:
            name, prop, value = line.split("\t")
            if prop == "creation":
                # value is epoch seconds with -p
                creation_map[name] = int(value)
        except ValueError:
            continue

    tag_map = {}
    for line in tag_out:
        try:
            name, prop, value = line.split("\t")
            if prop == TASK_PROP and value != "-":
                tag_map[name] = value
        except ValueError:
            continue

    for name, guid in pairs:
        ce = creation_map.get(name)
        if ce is None:
            # fall back if missing
            ce = int(dt.datetime.now().timestamp())
        snaps.append(Snapshot(name, guid, ce, tag_map.get(name)))

    return snaps

def prune_snapshots_by_retention(filesystem: str, task_name: str, retention_time: int, retention_unit: str, exclude_snap: str) -> None:
    if retention_time <= 0 or not retention_unit:
        print("Retention not configured; skipping prune.")
        return

    unit_seconds = {
        "minutes": 60,
        "hours":   60 * 60,
        "days":    24 * 60 * 60,
        "weeks":   7 * 24 * 60 * 60,
        # simple approximations; switch to relativedelta if you need calendar-accurate months/years
        "months":  30 * 24 * 60 * 60,
        "years":   365 * 24 * 60 * 60,
    }.get(retention_unit)

    if not unit_seconds:
        print(f"WARNING: Unknown retention unit '{retention_unit}'; skipping prune.")
        return

    cutoff = int(dt.datetime.now().timestamp()) - (retention_time * unit_seconds)
    snaps = get_local_snapshots(filesystem)

    candidates = []
    for s in snaps:
        # Only prune snapshots we created (by tag), exclude the one we just created
        if s.name == exclude_snap:
            continue

        belongs = (s.task_tag == task_name)

        # If not tagged (older deployments) fall back to legacy name match:
        if not belongs and ENABLE_LEGACY_FALLBACK:
            m = LEGACY_NAME_RE.search(s.name)
            if m and m.group('task') == task_name:
                belongs = True

        if not belongs:
            continue
        
        if s.creation_epoch <= cutoff:
            candidates.append(s)
		
    if not candidates:
        print("No snapshots to prune.")
        return

    # Delete oldest first (optional)
    candidates.sort(key=lambda s: s.creation_epoch)

    pruned = 0
    for s in candidates:
        try:
            run(["zfs", "destroy", s.name])
            pruned += 1
            print(f"Deleted snapshot: {s.name}")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: failed to delete {s.name}: {e.stderr.strip()}", file=sys.stderr)
            # continue rather than exit; you can flip this if you prefer to fail the unit
            continue

    print(f"Pruned {pruned} snapshot(s) older than {retention_time} {retention_unit}.")

def main():
    filesystem = os.environ.get("autoSnapConfig_filesystem_dataset", "").strip()
    is_recursive = os.environ.get("autoSnapConfig_recursive_flag", "false").strip().lower() == "true"
    custom_name = os.environ.get("autoSnapConfig_customName", "").strip() or None
    task_name = os.environ.get("taskName", "").strip()

    # Parse retention safely
    rt_raw = os.environ.get("autoSnapConfig_snapshotRetention_retentionTime", "0").strip()
    ru = os.environ.get("autoSnapConfig_snapshotRetention_retentionUnit", "").strip()
    try:
        rt = int(rt_raw)
    except ValueError:
        rt = 0

    created = create_snapshot(filesystem, is_recursive, task_name, custom_name)
    prune_snapshots_by_retention(filesystem, task_name, rt, ru, created)

if __name__ == "__main__":
    main()
