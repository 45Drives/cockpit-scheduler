#!/usr/bin/env python3
import subprocess
import sys
import datetime as dt
import json
import os
import re
import time
import traceback
from typing import List, Optional, Tuple

from notify import get_notifier


class SafeStream:
    """Wrap stdout/stderr so broken pipes don't crash the script."""
    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        try:
            return self._stream.write(data)
        except Exception:
            return 0

    def flush(self):
        try:
            return self._stream.flush()
        except Exception:
            return None

    def isatty(self):
        try:
            return self._stream.isatty()
        except Exception:
            return False

    def fileno(self):
        try:
            return self._stream.fileno()
        except Exception:
            return -1

    def __getattr__(self, name):
        return getattr(self._stream, name)


sys.stdout = SafeStream(sys.stdout)
sys.stderr = SafeStream(sys.stderr)

notifier = get_notifier()

# ---------------------------------------------------------------------------
# Debug logging — always writes to a file so we have a trace even when
# systemd journal is empty (e.g. pipe closed, SafeStream swallows errors).
# ---------------------------------------------------------------------------
DEBUG_LOG = os.environ.get("AUTOSNAP_DEBUG_LOG", "/tmp/autosnap_debug.log")
DEBUG_ENABLED = os.environ.get("AUTOSNAP_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")

def dbg(msg: str):
    if not DEBUG_ENABLED:
        return
    try:
        line = f"{dt.datetime.now().isoformat()} {msg}\n"
        with open(DEBUG_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass

# Timeout (seconds) for a single `zfs destroy` call.  If a snapshot has
# holds or clones the destroy can block indefinitely; this prevents that.
ZFS_DESTROY_TIMEOUT = int(os.environ.get("ZFS_DESTROY_TIMEOUT", "120"))

TASK_PROP = "com.45drives_scheduler:task_name"
TIER_PROP = "com.45drives_scheduler:scheduler_interval_tier"

class Snapshot:
    def __init__(self, name: str, guid: str, creation_epoch: int, task_tag: Optional[str], tier_tag: Optional[str] = None):
        self.name = name
        self.guid = guid
        self.creation_epoch = creation_epoch
        self.task_tag = task_tag
        self.tier_tag = tier_tag  # value of scheduler_interval_tier property (tN format)

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

# Timeout for ZFS list/get commands that can hang on degraded pools (seconds)
ZFS_LIST_TIMEOUT = int(os.environ.get("ZFS_LIST_TIMEOUT", "600"))

def run(cmd: List[str], timeout: int = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)


def _snapshot_has_holds(snap_name: str) -> bool:
    """Return True if *snap_name* has any user holds that would block destroy."""
    try:
        p = subprocess.run(
            ["zfs", "holds", "-H", snap_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30,
        )
        # Each line is a hold; if there's output, holds exist.
        return bool(p.stdout.strip())
    except Exception as e:
        dbg(f"holds check failed for {snap_name}: {e}")
        return False


def safe_destroy(snap_name: str) -> bool:
    """
    Destroy a snapshot with a timeout and a pre-check for holds.
    Returns True on success, False if skipped/failed (non-fatal).
    """
    if _snapshot_has_holds(snap_name):
        msg = f"WARNING: snapshot {snap_name} has holds — skipping destroy"
        print(msg, file=sys.stderr)
        dbg(msg)
        notifier.notify(f"STATUS={msg}")
        return False
    try:
        subprocess.run(
            ["zfs", "destroy", snap_name],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=ZFS_DESTROY_TIMEOUT,
        )
        return True
    except subprocess.TimeoutExpired:
        msg = f"WARNING: zfs destroy timed out after {ZFS_DESTROY_TIMEOUT}s for {snap_name} — skipping"
        print(msg, file=sys.stderr)
        dbg(msg)
        notifier.notify(f"STATUS={msg}")
        return False
    except subprocess.CalledProcessError as e:
        detail = e.stderr.strip() if e.stderr else str(e)
        msg = f"WARNING: zfs destroy failed for {snap_name}: {detail}"
        print(msg, file=sys.stderr)
        dbg(msg)
        return False


def create_snapshot(filesystem: str, is_recursive: bool, task_name: str, custom_name: Optional[str], tier_idx=None) -> str:
    if not filesystem:
        print("ERROR: filesystem is empty", file=sys.stderr)
        dbg("ERROR: filesystem is empty")
        sys.exit(1)

    ts = dt.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    tier_tag = f"-t{tier_idx}" if tier_idx is not None else ""
    if custom_name:
        snapname = f"{filesystem}@{custom_name}{tier_tag}-{ts}"
    else:
        snapname = f"{filesystem}@{task_name}{tier_tag}-{ts}"

    cmd = ["zfs", "snapshot"]
    if is_recursive:
        cmd.append("-r")
    cmd.append(snapname)

    dbg(f"Creating snapshot: {' '.join(cmd)}")
    notifier.notify(f"STATUS=Creating snapshot {snapname}…")
    try:
        res = run(cmd)
        print(f"Created snapshot: {snapname}")
        dbg(f"Snapshot created: {snapname}")
        notifier.notify(f"STATUS=Snapshot created: {snapname} 20% complete")
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() if e.stderr else "zfs snapshot failed"
        notifier.notify(f"STATUS=Snapshot creation failed: {msg}")
        print(f"ERROR: zfs snapshot failed: {msg}", file=sys.stderr)
        dbg(f"ERROR: zfs snapshot failed: {msg}")
        sys.exit(1)

    # Tag snapshot with task ownership and tier index via ZFS properties
    try:
        run(["zfs", "set", f"{TASK_PROP}={task_name}", snapname])
    except subprocess.CalledProcessError as e:
        # Non-fatal, but warn so pruning by tag may skip this one
        print(f"WARNING: failed to tag snapshot {snapname}: {e.stderr.strip()}", file=sys.stderr)
        dbg(f"WARNING: failed to tag snapshot {snapname}: {e.stderr.strip()}")

    if tier_idx is not None:
        try:
            run(["zfs", "set", f"{TIER_PROP}=t{tier_idx}", snapname])
        except subprocess.CalledProcessError as e:
            print(f"WARNING: failed to set tier property on {snapname}: {e.stderr.strip()}", file=sys.stderr)
            dbg(f"WARNING: failed to set tier on {snapname}: {e.stderr.strip()}")

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
        names = run(["zfs", "list", "-H", "-t", "snapshot", "-r", "-o", "name,guid", filesystem], timeout=ZFS_LIST_TIMEOUT).stdout.splitlines()
    except subprocess.TimeoutExpired:
        print(f"ERROR: Timed out after {ZFS_LIST_TIMEOUT}s listing snapshots on {filesystem}. The pool may be degraded or unresponsive.", file=sys.stderr)
        dbg(f"ERROR: Timed out listing snapshots on {filesystem}")
        sys.exit(1)
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

    # Batch get creation as epoch (-p) and our tag properties
    try:
        props_out = run(["zfs", "get", "-H", "-p", "-r", "-o", "name,property,value", "creation", filesystem], timeout=ZFS_LIST_TIMEOUT).stdout.splitlines()
        tag_out  = run(["zfs", "get", "-H", "-r", "-o", "name,property,value", TASK_PROP, filesystem], timeout=ZFS_LIST_TIMEOUT).stdout.splitlines()
        tier_out = run(["zfs", "get", "-H", "-r", "-o", "name,property,value", TIER_PROP, filesystem], timeout=ZFS_LIST_TIMEOUT).stdout.splitlines()
    except subprocess.TimeoutExpired:
        print(f"ERROR: Timed out after {ZFS_LIST_TIMEOUT}s fetching snapshot properties on {filesystem}. The pool may be degraded or unresponsive.", file=sys.stderr)
        dbg(f"ERROR: Timed out fetching snapshot properties on {filesystem}")
        sys.exit(1)

    creation_map = {}
    for line in props_out:
        try:
            name, prop, value = line.split("\t")
            if prop == "creation":
                # value is epoch seconds with -p
                creation_map[name] = int(value)
        except ValueError:
            continue

    # Build tag map from ZFS properties
    tag_map = {}
    for line in tag_out:
        try:
            name, prop, value = line.split("\t")
            if prop == TASK_PROP and value != "-":
                tag_map[name] = value
        except ValueError:
            continue

    # Build tier map from ZFS properties
    tier_map = {}
    for line in tier_out:
        try:
            name, prop, value = line.split("\t")
            if prop == TIER_PROP and value != "-":
                tier_map[name] = value
        except ValueError:
            continue

    for name, guid in pairs:
        ce = creation_map.get(name)
        if ce is None:
            # fall back if missing
            ce = int(dt.datetime.now().timestamp())
        snaps.append(Snapshot(name, guid, ce, tag_map.get(name), tier_map.get(name)))

    return snaps

def _is_autosnap_task_snapshot(snap_name: str, task_name: str, custom_name: str = "") -> bool:
    """Check if a snapshot belongs to this task by name pattern (fallback).
    Tier filtering is handled separately via ZFS properties; this function
    only checks task ownership. Matches new format (customName-timestamp),
    default format (taskName-timestamp), and legacy formats."""
    if "@" not in snap_name:
        return False
    suf = snap_name.split("@", 1)[1]
    tn = (task_name or "").strip()
    cn = (custom_name or "").strip()
    if not tn:
        return False

    # New format with tier tag: name-tN-timestamp
    if cn and re.match(rf'^{re.escape(cn)}-t\d+-\d{{4}}', suf):
        return True
    if re.match(rf'^{re.escape(tn)}-t\d+-\d{{4}}', suf):
        return True
    # Format without tier tag: name-timestamp
    if cn and suf.startswith(f"{cn}-"):
        return True
    if suf.startswith(f"{tn}-"):
        return True
    # Legacy format: customName-taskName-timestamp
    if cn and suf.startswith(f"{cn}-{tn}-"):
        return True
    return False


def prune_snapshots_by_retention(filesystem: str, task_name: str, retention_time: int, retention_unit: str, exclude_snap: str, tier_idx=None, custom_name: str = "") -> None:
    dbg(f"prune_snapshots_by_retention: fs={filesystem} task={task_name} retention={retention_time} {retention_unit} tier_idx={tier_idx}")
    if retention_time <= 0 or not retention_unit:
        print("Retention not configured; skipping prune.")
        notifier.notify("STATUS=Snapshot created; pruning not configured. 100% complete")
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
        notifier.notify(f"STATUS=Snapshot created; unknown retention unit '{retention_unit}', skipping prune. 100% complete")
        return

    cutoff = int(dt.datetime.now().timestamp()) - (retention_time * unit_seconds)
    snaps = get_local_snapshots(filesystem)
    dbg(f"prune: found {len(snaps)} total snapshots for {filesystem}")

    candidates = []
    for s in snaps:
        if s.name == exclude_snap:
            continue

        # Primary: check ZFS property tag (most reliable, works with any naming scheme)
        belongs = (s.task_tag == task_name)

        # Fallback: name-based matching, but ONLY for untagged snapshots.
        # If a snapshot is tagged for a different task, never claim it.
        if not belongs and not s.task_tag:
            belongs = _is_autosnap_task_snapshot(s.name, task_name, custom_name)

        if not belongs:
            continue

        # Tier filtering: use scheduler_interval_tier property
        if tier_idx is not None:
            snap_tier = s.tier_tag  # from ZFS property (tN format)
            if snap_tier is not None and snap_tier != f"t{tier_idx}":
                continue  # belongs to a different tier
        
        if s.creation_epoch <= cutoff:
            candidates.append(s)
    
    if not candidates:
        print("No snapshots to prune.")
        dbg("prune: no candidates")
        notifier.notify("STATUS=Snapshot created; no old snapshots to prune. 100% complete")
        return

    candidates.sort(key=lambda s: s.creation_epoch)
    dbg(f"prune: {len(candidates)} candidates to destroy")

    pruned = 0
    skipped = 0
    total = len(candidates)
    base = 20  # snapshot phase
    notifier.notify(f"STATUS=Pruning {total} old snapshot(s)… {base}% complete")
    for idx, s in enumerate(candidates, start=1):
        dbg(f"prune: destroying {s.name} ({idx}/{total})")
        if safe_destroy(s.name):
            pruned += 1
            print(f"Deleted snapshot: {s.name}")
        else:
            skipped += 1

        pct = 20 + int(idx * 80 / total)
        notifier.notify(f"STATUS=Pruning {total} old snapshot(s)… {pct}% complete")

    msg = f"Pruned {pruned} snapshot(s) older than {retention_time} {retention_unit}."
    if skipped:
        msg += f" Skipped {skipped} (held/busy)."
    print(msg)
    dbg(msg)
    notifier.notify(f"STATUS={msg} 100% complete")

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
    try:
        filesystem = os.environ.get("autoSnapConfig_filesystem_dataset", "").strip()
        is_recursive = os.environ.get("autoSnapConfig_recursive_flag", "false").strip().lower() == "true"
        use_custom_name = os.environ.get("autoSnapConfig_customName_flag", "false").strip().lower() == "true"
        custom_name = (os.environ.get("autoSnapConfig_customName", "").strip() or None) if use_custom_name else None
        task_name = os.environ.get("taskName", "").strip()

        dbg("=== autosnap task start ===")
        dbg(f"filesystem={filesystem} recursive={is_recursive} task_name={task_name} custom_name={custom_name}")

        # Task-level (default) retention from env
        rt_raw = os.environ.get("autoSnapConfig_snapshotRetention_retentionTime", "0").strip()
        ru = os.environ.get("autoSnapConfig_snapshotRetention_retentionUnit", "").strip()
        try:
            rt = int(rt_raw)
        except ValueError:
            rt = 0

        # Multi-interval tier support: override retention from schedule JSON if available
        schedule_json_path = os.environ.get("scheduleJsonPath", "")
        # Fallback: derive schedule JSON path from task name if env var is missing
        if not schedule_json_path and task_name:
            derived_path = f"/etc/systemd/system/houston_scheduler_AutomatedSnapshotTask_{task_name}.json"
            if os.path.isfile(derived_path):
                schedule_json_path = derived_path
                dbg(f"scheduleJsonPath not in env; using derived path: {derived_path}")
        schedule_data = load_schedule_json(schedule_json_path)

        tier_idx = None # None = legacy pruning (all task snapshots)

        if schedule_data and isinstance(schedule_data.get("intervals"), list):
            intervals = schedule_data["intervals"]
            has_per_interval_retention = any(
                isinstance(iv.get("retention"), dict) for iv in intervals
            )

            if has_per_interval_retention and len(intervals) > 1:
                now = dt.datetime.now()
                tier_idx = match_current_tier(intervals, now)
                print(f"Multi-tier: matched tier {tier_idx} of {len(intervals)}")
                dbg(f"Multi-tier: matched tier {tier_idx} of {len(intervals)}")

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

        dbg(f"retention: time={rt} unit={ru}")

        # --- Manual-run detection ---
        # When the task is started via "Run Now" (legacy-run-task-now.py),
        # a marker file is placed under /run/houston-scheduler-manual/.
        # If present, skip tier tagging so manual snapshots get plain names.
        manual_marker = f"/run/houston-scheduler-manual/houston_scheduler_AutomatedSnapshotTask_{task_name}"
        is_manual_run = os.path.isfile(manual_marker)
        if is_manual_run:
            try:
                os.remove(manual_marker)
            except OSError:
                pass
            dbg("Manual run detected — skipping tier tag")
            tier_idx = None

        notifier.notify("STATUS=Starting snapshot task…")
        notifier.notify("READY=1")
        notifier.notify("STATUS=Running snapshot task…")

        created = create_snapshot(filesystem, is_recursive, task_name, custom_name, tier_idx=tier_idx)
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

        notifier.notify("STATUS=Snapshot task completed. 100% complete")
        dbg("=== autosnap task completed ===")

        # Persist last-run timestamp so the UI can show it even after
        # the schedule is disabled/re-enabled (systemd clears its timestamps).
        try:
            lastrun_path = f"/etc/systemd/system/houston_scheduler_AutomatedSnapshotTask_{task_name}.lastrun"
            with open(lastrun_path, "w") as f:
                f.write(str(int(time.time())))
        except Exception as e:
            dbg(f"WARNING: failed to write lastrun file: {e}")

    except Exception as e:
        tb = traceback.format_exc()
        dbg(f"FATAL: {tb}")
        print(f"FATAL: {e}", file=sys.stderr)
        print(tb, file=sys.stderr)
        notifier.notify(f"STATUS=Snapshot task failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

