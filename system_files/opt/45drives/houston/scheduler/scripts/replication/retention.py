"""Safe snapshot destruction and retention pruning."""

import datetime
import subprocess
import time

from .constants import ZFS_DESTROY_TIMEOUT
from .context import notifier
from .logging_utils import _fmt_cmd, dbg, safe_print
from .snapshots import dataset_of_snapshot, get_local_snapshots, get_remote_snapshots, is_task_snapshot, snapshot_suffix
from .ssh import SSH_BASE_OPTS, ssh_run_args

def _snapshot_has_holds_local(snap_name: str) -> bool:
    """Return True if *snap_name* has any user holds that would block destroy."""
    try:
        p = subprocess.run(
            ["zfs", "holds", "-H", snap_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30,
        )
        return bool(p.stdout.strip())
    except Exception as e:
        dbg(f"holds check failed for {snap_name}: {e}")
        return False


def _snapshot_has_holds_remote(snap_name, remote_user, remote_host, remote_port):
    """Return True if remote snapshot has holds."""
    try:
        p = ssh_run_args(
            remote_user, remote_host, remote_port,
            ["zfs", "holds", "-H", snap_name],
            capture_output=True, check=False, text=True, timeout=30,
        )
        return bool((p.stdout or "").strip())
    except Exception as e:
        dbg(f"remote holds check failed for {snap_name}: {e}")
        return False


def safe_destroy_local(snap_name: str) -> bool:
    """Destroy a local snapshot with holds check + timeout. Returns True on success."""
    if _snapshot_has_holds_local(snap_name):
        msg = f"WARNING: snapshot {snap_name} has holds — skipping destroy"
        print(msg)
        dbg(msg)
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
        print(msg)
        dbg(msg)
        return False
    except subprocess.CalledProcessError as e:
        detail = e.stderr.strip() if e.stderr else str(e)
        msg = f"WARNING: zfs destroy failed for {snap_name}: {detail}"
        print(msg)
        dbg(msg)
        return False


def safe_destroy_remote(snap_name, remote_user, remote_host, remote_port) -> bool:
    """Destroy a remote snapshot with holds check + timeout. Returns True on success."""
    if _snapshot_has_holds_remote(snap_name, remote_user, remote_host, remote_port):
        msg = f"WARNING: remote snapshot {snap_name} has holds — skipping destroy"
        print(msg)
        dbg(msg)
        return False
    try:
        p = ssh_run_args(
            remote_user, remote_host, remote_port,
            ["zfs", "destroy", snap_name],
            capture_output=True, check=False, text=True,
            timeout=ZFS_DESTROY_TIMEOUT,
        )
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            msg = f"WARNING: remote zfs destroy failed for {snap_name}: {err}"
            print(msg)
            dbg(msg)
            return False
        return True
    except subprocess.TimeoutExpired:
        msg = f"WARNING: remote zfs destroy timed out after {ZFS_DESTROY_TIMEOUT}s for {snap_name} — skipping"
        print(msg)
        dbg(msg)
        return False


def destroy_snapshots_with_progress(snapshots, dest_fs, remote_user=None, remote_host=None,
                                    ssh_port="22", reason="for full receive"):
    """Destroy destination snapshots ahead of a full receive, reporting progress.

    Returns (destroyed, failed).
    """
    total = len(snapshots)
    where = f"remote destination {dest_fs}" if remote_host else f"destination {dest_fs}"
    status_label = "Destroying remote snapshots" if remote_host else "Destroying destination snapshots"
    print(f"Destroying {total} snapshot(s) on {where} {reason}…")
    notifier.notify(f"STATUS={status_label}… 0/{total} (0.0%)")
    dbg(f"destroy start: {total} snapshot(s) on {where} {reason}")

    destroyed = 0
    failed = 0
    start = time.time()
    last_emit = 0.0
    last_print = start

    for idx, snap in enumerate(snapshots, 1):
        if remote_host:
            cmd = ["ssh"] + SSH_BASE_OPTS
            if str(ssh_port) != "22":
                cmd += ["-p", str(ssh_port)]
            cmd += [f"{remote_user}@{remote_host}", "zfs", "destroy", "-R", snap.name]
        else:
            cmd = ["zfs", "destroy", "-R", snap.name]

        dbg(f"RUN {_fmt_cmd(cmd)}")
        dp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True)
        if dp.returncode != 0:
            err_out = (dp.stderr or dp.stdout or "").strip()
            # Already gone counts as cleared, not as a failure.
            if "does not exist" not in err_out and "could not find" not in err_out:
                failed += 1
                print(f"WARNING: failed to destroy {snap.name}: {err_out}")
                dbg(f"destroy FAILED {snap.name}: {err_out}")
            else:
                destroyed += 1
        else:
            destroyed += 1

        now = time.time()
        pct = idx * 100.0 / total
        if idx == total or (now - last_emit) >= 1.0:
            notifier.notify(f"STATUS={status_label}… {idx}/{total} ({pct:.1f}%)")
            last_emit = now

        if idx == total or (now - last_print) >= 5.0:
            elapsed = now - start
            rate = idx / elapsed if elapsed > 0 else 0
            eta = f" ETA={int((total - idx) / rate)}s" if rate > 0 and idx < total else ""
            safe_print(f"{status_label}… {idx}/{total} ({pct:.1f}%){eta}")
            dbg(f"destroy progress: {idx}/{total} ({pct:.1f}%) "
                f"destroyed={destroyed} failed={failed} rate={rate:.1f}/s{eta}")
            last_print = now

    elapsed = time.time() - start
    dbg(f"destroy finished: total={total} destroyed={destroyed} failed={failed} elapsed={elapsed:.1f}s")
    if failed:
        print(f"Destination snapshots cleared with {failed} failure(s) ({destroyed}/{total} destroyed).")
        notifier.notify(f"STATUS={status_label} — destroyed {destroyed}/{total} ({failed} failed).")
    else:
        print(f"Destination snapshots cleared ({destroyed}/{total}).")
        notifier.notify(f"STATUS={status_label} — destroyed {destroyed}/{total}.")
    return destroyed, failed


def prune_snapshots_by_retention(
    filesystem,
    task_name,
    retention_time,
    retention_unit,
    excluded_snapshot_name,
    remote_user=None,
    remote_host=None,
    remote_port="22",
    transferMethod="ssh",
    progress_base=0,
    progress_span=100,
    tier_idx=None,
    custom_name="",
):
    if remote_host:
        snapshots = get_remote_snapshots(remote_user, remote_host, remote_port, filesystem)
        if snapshots is None:
            msg = f"Remote dataset {filesystem} does not exist. Nothing to prune."
            final_pct = min(100, int(progress_base) + int(progress_span))
            notifier.notify(f"STATUS={msg} {final_pct}% complete")
            return final_pct
    else:
        snapshots = get_local_snapshots(filesystem)

    if snapshots is None:
        msg = f"{'Remote ' if remote_host else ''}dataset {filesystem} does not exist. Nothing to prune."
        final_pct = min(100, int(progress_base) + int(progress_span))
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    now = datetime.datetime.now()

    unit_multipliers = {
        "minutes": 60 * 1000,
        "hours": 60 * 60 * 1000,
        "days": 24 * 60 * 60 * 1000,
        "weeks": 7 * 24 * 60 * 60 * 1000,
        "months": 30 * 24 * 60 * 60 * 1000,
        "years": 365 * 24 * 60 * 60 * 1000,
    }

    try:
        retention_val = int(retention_time)
    except (TypeError, ValueError):
        retention_val = 0

    if (retention_val == 0) and (not retention_unit):
        msg = "Retention not configured. No pruning will be performed."
        final_pct = min(100, int(progress_base) + int(progress_span))
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    if retention_val <= 0 or retention_unit not in unit_multipliers:
        msg = f"Retention period is not valid (time={retention_time}, unit='{retention_unit}'). No pruning will be performed."
        final_pct = min(100, int(progress_base) + int(progress_span))
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    retention_milliseconds = retention_val * unit_multipliers[retention_unit]
    snapshots_to_delete = []

    excluded_suffix = excluded_snapshot_name.split("@", 1)[-1] if excluded_snapshot_name else None

    # Compatibility path for snapshots created before children were tagged
    # directly: fall back to the root's tags for the same suffix.
    root_tags = {}
    for snapshot in snapshots:
        if dataset_of_snapshot(snapshot.name) != filesystem:
            continue
        tags = (getattr(snapshot, "task_tag", None), getattr(snapshot, "tier_tag", None))
        if tags[0] or tags[1]:
            root_tags[snapshot_suffix(snapshot.name)] = tags

    for snapshot in snapshots:
        task_tag = getattr(snapshot, "task_tag", None)
        tier_tag = getattr(snapshot, "tier_tag", None)
        if not task_tag and not tier_tag:
            task_tag, tier_tag = root_tags.get(snapshot_suffix(snapshot.name), (None, None))

        # Primary: check ZFS property tag (most reliable, works with any naming scheme)
        belongs = (task_tag == task_name)

        # Fallback: name-based matching, but ONLY for untagged snapshots.
        # If a snapshot is tagged for a different task, never claim it.
        if not belongs and not task_tag:
            belongs = is_task_snapshot(snapshot.name, task_name, custom_name=custom_name)

        if not belongs:
            continue

        # Tier filtering via ZFS property
        if tier_idx is not None:
            if tier_tag is not None and tier_tag != f"t{tier_idx}":
                continue  # belongs to a different tier

        snap_suffix = snapshot_suffix(snapshot.name)
        if excluded_suffix and snap_suffix == excluded_suffix:
            continue

        age_milliseconds = (now - snapshot.creation).total_seconds() * 1000
        if age_milliseconds > retention_milliseconds:
            snapshots_to_delete.append(snapshot)

    start = max(0, min(100, int(progress_base)))
    span = max(0, min(100 - start, int(progress_span)))
    prefix = "remote " if remote_host else ""

    if not snapshots_to_delete:
        msg = "No snapshots to prune."
        final_pct = min(100, start + span)
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    total = len(snapshots_to_delete)
    notifier.notify(f"STATUS=Pruning {total} {prefix}snapshot(s)… {start}% complete")
    dbg(f"prune: {total} candidates to destroy (remote={bool(remote_host)})")

    pruned = 0
    skipped = 0
    for idx, snapshot in enumerate(snapshots_to_delete, start=1):
        dbg(f"prune: destroying {snapshot.name} ({idx}/{total})")
        if remote_host:
            ok = safe_destroy_remote(snapshot.name, remote_user, remote_host, remote_port)
        else:
            ok = safe_destroy_local(snapshot.name)

        if ok:
            pruned += 1
            print(f"Deleted snapshot: {snapshot.name}")
        else:
            skipped += 1

        pct = start + int(idx * span / total)
        notifier.notify(f"STATUS=Pruning {total} {prefix}snapshot(s)… {pct}% complete")

    msg = f"Pruned {pruned} snapshots older than retention period ({retention_val} {retention_unit})."
    if skipped:
        msg += f" Skipped {skipped} (held/busy)."
    final_pct = min(100, start + span)
    notifier.notify(f"STATUS={msg} {final_pct}% complete")
    dbg(msg)
    return final_pct
