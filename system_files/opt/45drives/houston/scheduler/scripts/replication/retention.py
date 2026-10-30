"""Safe snapshot destruction and retention pruning."""

import datetime
import subprocess
import time

from .constants import ZFS_DESTROY_TIMEOUT
from .context import notifier
from .logging_utils import _fmt_cmd, dbg, safe_print
from .snapshots import dataset_of_snapshot, get_local_snapshots, get_remote_snapshots, is_task_snapshot, snapshot_suffix
from .ssh import ssh_run_args

# One `zfs destroy` per batch instead of per snapshot: a connection per snapshot trips
# sshd MaxStartups / fail2ban on the target once a dataset holds thousands of them.
DESTROY_BATCH_SIZE = 100
DESTROY_BATCH_MAX_CHARS = 32000


class SnapshotDestroyError(RuntimeError):
    """Raised when snapshots that must be cleared before a full receive could not be destroyed."""

    def __init__(self, message, held=False):
        super().__init__(message)
        # ZFS reports a held snapshot as "dataset is busy"; this lets callers tell the two apart.
        self.held = held


def _run_zfs(args, remote_user=None, remote_host=None, remote_port="22", timeout=None):
    if remote_host:
        return ssh_run_args(remote_user, remote_host, remote_port, args,
                            capture_output=True, check=False, text=True, timeout=timeout)
    dbg(f"RUN {_fmt_cmd(args)}")
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=timeout)


def _error_text(p) -> str:
    return (p.stderr or p.stdout or "").strip() or f"exit code {p.returncode}"


def destroy_batches(names):
    """Group snapshot names by dataset into batches that fit in one `zfs destroy` argument."""
    by_dataset = {}
    for name in names:
        by_dataset.setdefault(dataset_of_snapshot(name), []).append(name)
    for dataset_names in by_dataset.values():
        batch, size = [], 0
        for name in dataset_names:
            if batch and (len(batch) >= DESTROY_BATCH_SIZE or size + len(name) > DESTROY_BATCH_MAX_CHARS):
                yield batch
                batch, size = [], 0
            batch.append(name)
            size += len(snapshot_suffix(name)) + 1
        if batch:
            yield batch


def _destroy_spec(batch) -> str:
    return dataset_of_snapshot(batch[0]) + "@" + ",".join(snapshot_suffix(n) for n in batch)


def _held_snapshots(names, remote_user=None, remote_host=None, remote_port="22"):
    """Map each of *names* that carries user holds to its hold tags, using one `zfs holds` call."""
    try:
        p = _run_zfs(["zfs", "holds", "-H", *names], remote_user, remote_host, remote_port, timeout=60)
    except Exception as e:
        dbg(f"holds check failed for {len(names)} snapshot(s): {e}")
        return {}
    wanted = set(names)
    held = {}
    for line in (p.stdout or "").splitlines():
        fields = line.split("\t")
        name = fields[0].strip()
        if name in wanted:
            held.setdefault(name, []).append(fields[1].strip() if len(fields) > 1 else "?")
    return held


def _removed_with_ancestor(name, removed):
    """True if *name* went with a `zfs destroy -R` of the same snapshot on an ancestor dataset."""
    dataset, suffix = dataset_of_snapshot(name), snapshot_suffix(name)
    return any(dataset.startswith(parent + "/") and suffix in suffixes for parent, suffixes in removed.items())


def _remaining_snapshots(dataset, remote_user=None, remote_host=None, remote_port="22"):
    """Snapshot names still present directly on *dataset*, or None if they could not be listed."""
    try:
        p = _run_zfs(["zfs", "list", "-H", "-o", "name", "-t", "snapshot", "-d", "1", dataset],
                     remote_user, remote_host, remote_port, timeout=60)
    except Exception as e:
        dbg(f"snapshot listing failed for {dataset}: {e}")
        return None
    if p.returncode != 0:
        err = _error_text(p)
        if "does not exist" in err:
            return set()
        dbg(f"snapshot listing failed for {dataset}: {err}")
        return None
    return {line.strip() for line in (p.stdout or "").splitlines() if line.strip()}


def _destroy_one(snap_name, remote_user=None, remote_host=None, remote_port="22") -> bool:
    where = "remote " if remote_host else ""
    try:
        p = _run_zfs(["zfs", "destroy", snap_name], remote_user, remote_host, remote_port,
                     timeout=ZFS_DESTROY_TIMEOUT)
    except subprocess.TimeoutExpired:
        msg = f"WARNING: {where}zfs destroy timed out after {ZFS_DESTROY_TIMEOUT}s for {snap_name} — skipping"
        print(msg)
        dbg(msg)
        return False
    if p.returncode != 0:
        msg = f"WARNING: {where}zfs destroy failed for {snap_name}: {_error_text(p)}"
        print(msg)
        dbg(msg)
        return False
    return True


def safe_destroy_batch(names, remote_user=None, remote_host=None, remote_port="22"):
    """Destroy one dataset's snapshots with a single holds check and a single `zfs destroy`.

    Held snapshots are skipped. If the batch destroy fails, each snapshot still present is
    retried on its own so one undeletable snapshot does not block the rest. Returns the set
    of names that are gone afterwards.
    """
    where = "remote " if remote_host else ""
    held = _held_snapshots(names, remote_user, remote_host, remote_port)
    for name in names:
        if name in held:
            msg = f"WARNING: {where}snapshot {name} has holds — skipping destroy"
            print(msg)
            dbg(msg)
    targets = [n for n in names if n not in held]
    if not targets:
        return set()

    try:
        p = _run_zfs(["zfs", "destroy", _destroy_spec(targets)], remote_user, remote_host, remote_port,
                     timeout=ZFS_DESTROY_TIMEOUT * len(targets))
        if p.returncode == 0:
            return set(targets)
        err = _error_text(p)
    except subprocess.TimeoutExpired:
        err = f"timed out after {ZFS_DESTROY_TIMEOUT * len(targets)}s"
    dbg(f"batch destroy of {len(targets)} {where}snapshot(s) failed: {err}")

    remaining = _remaining_snapshots(dataset_of_snapshot(targets[0]), remote_user, remote_host, remote_port)
    if remaining is None:
        msg = f"WARNING: {where}zfs destroy failed for {len(targets)} snapshot(s) on {dataset_of_snapshot(targets[0])}: {err}"
        print(msg)
        dbg(msg)
        return set()
    destroyed = {n for n in targets if n not in remaining}
    for name in targets:
        if name in remaining and _destroy_one(name, remote_user, remote_host, remote_port):
            destroyed.add(name)
    return destroyed


def destroy_snapshots_with_progress(snapshots, dest_fs, remote_user=None, remote_host=None,
                                    ssh_port="22", reason="for full receive"):
    """Destroy destination snapshots ahead of a full receive, in per-dataset batches.

    Stops at the first batch that leaves snapshots behind and raises SnapshotDestroyError,
    because the receive that follows cannot succeed while any of them remain.
    Returns the number of snapshots destroyed.
    """
    total = len(snapshots)
    where = f"remote destination {dest_fs}" if remote_host else f"destination {dest_fs}"
    status_label = "Destroying remote snapshots" if remote_host else "Destroying destination snapshots"
    print(f"Destroying {total} snapshot(s) on {where} {reason}…")
    notifier.notify(f"STATUS={status_label}… 0/{total} (0.0%)")
    dbg(f"destroy start: {total} snapshot(s) on {where} {reason}")

    destroyed = 0
    start = time.time()
    last_emit = 0.0
    last_print = start
    # `zfs destroy -R` implies -r, so each batch also removes the same snapshots from every
    # descendant dataset. Track them so child batches skip what is already gone.
    removed = {}
    batches = list(destroy_batches([s.name for s in snapshots]))

    for index, batch in enumerate(batches):
        already_gone = [n for n in batch if _removed_with_ancestor(n, removed)]
        destroyed += len(already_gone)
        batch = [n for n in batch if n not in already_gone]
        if batch:
            dataset = dataset_of_snapshot(batch[0])
            p = _run_zfs(["zfs", "destroy", "-R", _destroy_spec(batch)], remote_user, remote_host, ssh_port)
            if p.returncode != 0:
                err = _error_text(p)
                dbg(f"batch destroy FAILED ({len(batch)} snapshot(s) on {dataset}): {err}")
                # Snapshots that were already gone are not a failure; only the ones left behind are.
                remaining = _remaining_snapshots(dataset, remote_user, remote_host, ssh_port)
                left = [n for n in batch if remaining is None or n in remaining]
                if left:
                    destroyed += sum(
                        1 for later in batches[index + 1:] for n in later if _removed_with_ancestor(n, removed)
                    )
                    held = _held_snapshots(left, remote_user, remote_host, ssh_port)
                    if held:
                        example = next(iter(held))
                        tags = ", ".join(held[example])
                        cause = (
                            f"{len(held)} snapshot(s) have user holds (e.g. {example}, hold tag: {tags}). "
                            "Release the holds with `zfs release <tag> <snapshot>` and run the task again"
                        )
                    else:
                        example = left[0]
                        cause = err
                    msg = (
                        f"Could not destroy {len(left)} snapshot(s) on {where} (e.g. {example}): {cause}. "
                        f"Stopped after destroying {destroyed}/{total}; the full receive cannot proceed "
                        "while destination snapshots remain."
                    )
                    print(f"ERROR: {msg}")
                    notifier.notify(f"STATUS={status_label} failed — destroyed {destroyed}/{total}.")
                    raise SnapshotDestroyError(msg, held=bool(held))
            else:
                removed.setdefault(dataset, set()).update(snapshot_suffix(n) for n in batch)
            destroyed += len(batch)

        now = time.time()
        pct = destroyed * 100.0 / total
        if destroyed == total or (now - last_emit) >= 1.0:
            notifier.notify(f"STATUS={status_label}… {destroyed}/{total} ({pct:.1f}%)")
            last_emit = now

        if destroyed == total or (now - last_print) >= 5.0:
            elapsed = now - start
            rate = destroyed / elapsed if elapsed > 0 else 0
            eta = f" ETA={int((total - destroyed) / rate)}s" if rate > 0 and destroyed < total else ""
            safe_print(f"{status_label}… {destroyed}/{total} ({pct:.1f}%){eta}")
            dbg(f"destroy progress: {destroyed}/{total} ({pct:.1f}%) rate={rate:.1f}/s{eta}")
            last_print = now

    elapsed = time.time() - start
    dbg(f"destroy finished: total={total} destroyed={destroyed} elapsed={elapsed:.1f}s")
    print(f"Destination snapshots cleared ({destroyed}/{total}).")
    notifier.notify(f"STATUS={status_label} — destroyed {destroyed}/{total}.")
    return destroyed


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
    done = 0
    for batch in destroy_batches([s.name for s in snapshots_to_delete]):
        dbg(f"prune: destroying {len(batch)} snapshot(s) on {dataset_of_snapshot(batch[0])} ({done + len(batch)}/{total})")
        if remote_host:
            gone = safe_destroy_batch(batch, remote_user, remote_host, remote_port)
        else:
            gone = safe_destroy_batch(batch)

        for name in batch:
            if name in gone:
                pruned += 1
                print(f"Deleted snapshot: {name}")
            else:
                skipped += 1

        done += len(batch)
        pct = start + int(done * span / total)
        notifier.notify(f"STATUS=Pruning {total} {prefix}snapshot(s)… {pct}% complete")

    msg = f"Pruned {pruned} snapshots older than retention period ({retention_val} {retention_unit})."
    if skipped:
        msg += f" Skipped {skipped} (held/busy)."
    final_pct = min(100, start + span)
    notifier.notify(f"STATUS={msg} {final_pct}% complete")
    dbg(msg)
    return final_pct
