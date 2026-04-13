#!/usr/bin/env python3
import subprocess
import sys
import datetime as dt
import json
import os
import re
from typing import List, Optional, Tuple

from notify import get_notifier

notifier = get_notifier()

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
        print(f"Failed to send D-Bus notification: {e}")

def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

def create_snapshot(filesystem: str, is_recursive: bool, task_name: str, custom_name: Optional[str], tier_tag: str = "") -> str:
    if not filesystem:
        print("ERROR: filesystem is empty", file=sys.stderr)
        sys.exit(1)

    ts = dt.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    snapname = f"{filesystem}@{(custom_name + '-' if custom_name else '')}{task_name}{tier_tag}-{ts}"

    cmd = ["zfs", "snapshot"]
    if is_recursive:
        cmd.append("-r")
    cmd.append(snapname)

    notifier.notify(f"STATUS=Creating snapshot {snapname}…")
    try:
        res = run(cmd)
        print(f"Created snapshot: {snapname}")
        notifier.notify(f"STATUS=Snapshot created: {snapname} 20% complete")
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() if e.stderr else "zfs snapshot failed"
        notifier.notify(f"STATUS=Snapshot creation failed: {msg}")
        print(f"ERROR: zfs snapshot failed: {msg}", file=sys.stderr)
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

def _is_autosnap_task_snapshot(snap_name: str, task_name: str, custom_name: str = "", tier_idx=None) -> bool:
    """Check if a snapshot belongs to this task, optionally scoped to a tier."""
    if "@" not in snap_name:
        return False
    suf = snap_name.split("@", 1)[1]
    tn = (task_name or "").strip()
    cn = (custom_name or "").strip()
    if not tn:
        return False

    if tier_idx is not None:
        tier_prefix = f"{tn}-t{tier_idx}-"
        if suf.startswith(tier_prefix):
            return True
        if cn:
            cn_tier_prefix = f"{cn}-{tn}-t{tier_idx}-"
            if suf.startswith(cn_tier_prefix):
                return True
        return False

    # Legacy/single-tier
    if suf.startswith(f"{tn}-"):
        return True
    if cn and suf.startswith(f"{cn}-{tn}-"):
        return True
    return False


def prune_snapshots_by_retention(filesystem: str, task_name: str, retention_time: int, retention_unit: str, exclude_snap: str, tier_idx=None, custom_name: str = "") -> None:
    if retention_time <= 0 or not retention_unit:
        print("Retention not configured; skipping prune.")
        notifier.notify("STATUS=Snapshot created; pruning not configured.")
        return

    unit_seconds = {
        "minutes": 60,
        "hours":   60 * 60,
        "days":    24 * 60 * 60,
        "weeks":   7 * 24 * 60 * 60,
        "months":  30 * 24 * 60 * 60,
        "years":   365 * 24 * 60 * 60,
    }.get(retention_unit)

    if not unit_seconds:
        print(f"WARNING: Unknown retention unit '{retention_unit}'; skipping prune.")
        notifier.notify(f"STATUS=Snapshot created; unknown retention unit '{retention_unit}', skipping prune.")
        return

    cutoff = int(dt.datetime.now().timestamp()) - (retention_time * unit_seconds)
    snaps = get_local_snapshots(filesystem)

    candidates = []
    for s in snaps:
        if s.name == exclude_snap:
            continue

        # Use tier-scoped matching when tier_idx is set
        belongs = _is_autosnap_task_snapshot(s.name, task_name, custom_name, tier_idx=tier_idx)

        # Fallback: check ZFS property tag
        if not belongs and tier_idx is None:
            belongs = (s.task_tag == task_name)

        if not belongs and tier_idx is None and ENABLE_LEGACY_FALLBACK:
            m = LEGACY_NAME_RE.search(s.name)
            if m and m.group('task') == task_name:
                belongs = True

        if not belongs:
            continue
        
        if s.creation_epoch <= cutoff:
            candidates.append(s)
    
    if not candidates:
        print("No snapshots to prune.")
        notifier.notify("STATUS=Snapshot created; no old snapshots to prune.")
        return

    candidates.sort(key=lambda s: s.creation_epoch)

    pruned = 0
    total = len(candidates)
    base = 20  # snapshot phase
    notifier.notify(f"STATUS=Pruning {total} old snapshot(s)… {base}% complete")
    for idx, s in enumerate(candidates, start=1):
        try:
            run(["zfs", "destroy", s.name])
            pruned += 1
            print(f"Deleted snapshot: {s.name}")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: failed to delete {s.name}: {e.stderr.strip()}", file=sys.stderr)
            continue

        pct = int(idx * 100 / total)
        notifier.notify(f"STATUS=Pruning {total} old snapshot(s)… {pct}% complete")

    msg = f"Pruned {pruned} snapshot(s) older than {retention_time} {retention_unit}."
    print(msg)
    notifier.notify(f"STATUS={msg}")

def load_schedule_json(path: str):
    """Load the schedule JSON file. Returns the parsed dict or None."""
    if not path:
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not read schedule JSON at {path}: {e}")
        return None


def _field_matches_value(pattern: str, current: int) -> bool:
    """Check if a systemd calendar field pattern matches a value."""
    pattern = str(pattern).strip()
    if pattern == "*":
        return True
    if ".." in pattern:
        parts = pattern.split("..")
        try:
            a, b = int(parts[0]), int(parts[1])
            return a <= current <= b
        except (ValueError, IndexError):
            return False
    if "/" in pattern:
        parts = pattern.split("/")
        try:
            start, step = int(parts[0]), int(parts[1])
            if step <= 0:
                return False
            return current >= start and (current - start) % step == 0
        except (ValueError, IndexError):
            return False
    if "," in pattern:
        try:
            values = [int(v.strip()) for v in pattern.split(",")]
            return current in values
        except ValueError:
            return False
    # Single value — exact match
    try:
        return current == int(pattern)
    except ValueError:
        return False


def _interval_matches_time(interval: dict, now) -> bool:
    """Check if a schedule interval matches the current time."""
    for field in ("minute", "hour", "day", "month", "year"):
        val = interval.get(field, {}).get("value", "*")
        if not _field_matches_value(val, getattr(now, field)):
            return False
    dow = interval.get("dayOfWeek", [])
    if dow:
        dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        current_dow = dow_names[now.weekday()]
        normalized_dow = [str(d).strip()[:3].title() for d in dow]
        if current_dow not in normalized_dow:
            return False
    return True


def _count_specificity(interval: dict) -> int:
    count = 0
    for field in ("minute", "hour", "day", "month", "year"):
        val = str(interval.get(field, {}).get("value", "*")).strip()
        if val != "*":
            count += 1
    if interval.get("dayOfWeek", []):
        count += 1
    return count


def match_current_tier(intervals: list, now) -> int:
    """Return index of best-matching interval for current time. Falls back to 0."""
    matched = []
    for idx, interval in enumerate(intervals):
        if _interval_matches_time(interval, now):
            matched.append((idx, _count_specificity(interval)))
    if not matched:
        return 0
    # Most specific wins; on tie, prefer the lower index (more general / higher-priority)
    matched.sort(key=lambda x: (x[1], -x[0]), reverse=True)
    return matched[0][0]


def main():
    filesystem = os.environ.get("autoSnapConfig_filesystem_dataset", "").strip()
    is_recursive = os.environ.get("autoSnapConfig_recursive_flag", "false").strip().lower() == "true"
    custom_name = os.environ.get("autoSnapConfig_customName", "").strip() or None
    task_name = os.environ.get("taskName", "").strip()

    # Task-level (default) retention from env
    rt_raw = os.environ.get("autoSnapConfig_snapshotRetention_retentionTime", "0").strip()
    ru = os.environ.get("autoSnapConfig_snapshotRetention_retentionUnit", "").strip()
    try:
        rt = int(rt_raw)
    except ValueError:
        rt = 0

    # Multi-interval tier support: override retention from schedule JSON if available
    schedule_json_path = os.environ.get("scheduleJsonPath", "")
    schedule_data = load_schedule_json(schedule_json_path)

    if schedule_data and isinstance(schedule_data.get("intervals"), list):
        intervals = schedule_data["intervals"]
        has_per_interval_retention = any(
            isinstance(iv.get("retention"), dict) for iv in intervals
        )
        tier_tag = ""   # empty = legacy snapshot naming
        tier_idx = None # None = legacy pruning (all task snapshots)

        if has_per_interval_retention and len(intervals) > 1:
            now = dt.datetime.now()
            tier_idx = match_current_tier(intervals, now)
            tier_tag = f"-t{tier_idx}"
            print(f"Multi-tier: matched tier {tier_idx} of {len(intervals)}")

            matched_iv = intervals[tier_idx]
            iv_ret = matched_iv.get("retention", {}) or {}
            # AutoSnap only has one location — check source first, then destination
            snap_ret = iv_ret.get("source", {}) or iv_ret.get("destination", {}) or {}
            if snap_ret.get("retentionTime", 0) > 0:
                rt = snap_ret["retentionTime"]
                ru = snap_ret.get("retentionUnit", ru)
        elif has_per_interval_retention and len(intervals) == 1:
            # Single interval with per-interval retention
            iv_ret = intervals[0].get("retention", {}) or {}
            snap_ret = iv_ret.get("source", {}) or iv_ret.get("destination", {}) or {}
            if snap_ret.get("retentionTime", 0) > 0:
                rt = snap_ret["retentionTime"]
                ru = snap_ret.get("retentionUnit", ru)

    notifier.notify("STATUS=Starting snapshot task…")
    notifier.notify("READY=1")
    notifier.notify("STATUS=Running snapshot task…")

    created = create_snapshot(filesystem, is_recursive, task_name, custom_name, tier_tag=tier_tag)
    prune_snapshots_by_retention(filesystem, task_name, rt, ru, created, tier_idx=tier_idx, custom_name=custom_name or "")

    # Clean up legacy (pre-tier) untagged snapshots when multi-tier is active.
    # Uses the longest retention window across all tiers so we don't prune
    # snapshots that a longer-retention tier would still want to keep.
    if tier_idx is not None and schedule_data and isinstance(schedule_data.get("intervals"), list):
        _unit_secs = {
            "minutes": 60, "hours": 3600, "days": 86400,
            "weeks": 604800, "months": 2592000, "years": 31536000,
        }
        max_secs = 0
        max_time = 0
        max_unit = ""
        for iv in schedule_data["intervals"]:
            iv_ret = (iv.get("retention") or {})
            snap_ret = iv_ret.get("source") or iv_ret.get("destination") or {}
            t = snap_ret.get("retentionTime", 0) or 0
            u = snap_ret.get("retentionUnit", "")
            s = int(t) * _unit_secs.get(u, 0)
            if s > max_secs:
                max_secs = s
                max_time = t
                max_unit = u
        if max_secs > 0:
            prune_snapshots_by_retention(filesystem, task_name, max_time, max_unit, created, tier_idx=None, custom_name=custom_name or "")

    notifier.notify("STATUS=Snapshot task completed.")

if __name__ == "__main__":
    main()

