"""Snapshot inventory, creation, tagging, and capacity checks."""

import datetime
import re
import subprocess
import sys
import time

from .constants import TASK_PROP, TIER_PROP, ZFS_LIST_TIMEOUT
from .context import notifier
from .models import Snapshot
from .process import format_bytes, run_logged
from .ssh import ssh_run_args

def split_zfs_list_line(line: str):
    line = (line or "").rstrip("\n")
    if "\t" in line:
        return line.split("\t")

    parts = line.rsplit(None, 3)
    if len(parts) < 3:
        return line.split()
    return parts


def parse_snapshot_line(line: str):
    parts = split_zfs_list_line(line)
    if len(parts) < 3:
        return None

    name, guid, creation_raw = parts[0], parts[1], parts[2]
    txg_raw = parts[3] if len(parts) >= 4 else ""

    try:
        creation_epoch = int(creation_raw)
        created_dt = datetime.datetime.fromtimestamp(creation_epoch)
    except Exception:
        return None

    order_key = creation_epoch
    if txg_raw and str(txg_raw).isdigit():
        order_key = int(txg_raw)

    return Snapshot(name, guid, created_dt, creation_epoch=creation_epoch, order_key=order_key)


def snapshot_suffix(full_snap_name: str) -> str:
    return (full_snap_name or "").split("@", 1)[-1]


def dataset_of_snapshot(full_snap_name: str) -> str:
    return (full_snap_name or "").split("@", 1)[0]


def filter_dataset_snapshots(snaps, dataset: str):
    ds = (dataset or "").strip()
    return [s for s in (snaps or []) if dataset_of_snapshot(s.name) == ds]


def is_task_snapshot(full_snap_name: str, task_name: str, custom_name: str = "") -> bool:
    """Check if a snapshot belongs to this task by name pattern (fallback).
    Tier filtering is handled separately via ZFS properties; this function
    only checks task ownership. Matches new format (customName-timestamp),
    default format (taskName-timestamp), and legacy formats."""
    suf = snapshot_suffix(full_snap_name)
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


def filter_task_snapshots(snaps, task_name: str, custom_name: str = ""):
    """Return snapshots that belong to the task.

    Primary match uses TASK_PROP tag. For untagged legacy snapshots, fall back
    to name-based matching. Tagged snapshots owned by other tasks are never
    claimed by fallback matching.
    """
    filtered = []
    for snap in (snaps or []):
        belongs = (hasattr(snap, 'task_tag') and snap.task_tag == task_name)

        if not belongs and not getattr(snap, 'task_tag', None):
            belongs = is_task_snapshot(snap.name, task_name, custom_name=custom_name)

        if belongs:
            filtered.append(snap)

    return filtered


def get_local_snapshots(filesystem):
    cmd = [
        "zfs",
        "list",
        "-H",
        "-p",
        "-o",
        "name,guid,creation,createtxg",
        "-t",
        "snapshot",
        "-r",
        filesystem,
    ]
    try:
        p = run_logged(cmd, text=True, timeout=ZFS_LIST_TIMEOUT)
    except subprocess.TimeoutExpired:
        msg = f"Timed out after {ZFS_LIST_TIMEOUT}s listing snapshots on {filesystem}. The pool may be degraded or unresponsive."
        print(msg, file=sys.stderr)
        notifier.notify(f"STATUS={msg}")
        sys.exit(1)
    
    if p.returncode == 0:
        snaps = []
        for line in (p.stdout or "").splitlines():
            snap = parse_snapshot_line(line)
            if snap:
                snaps.append(snap)

        # Fetch task tags for ownership tracking
        tag_map = {}
        tier_map = {}
        try:
            tag_cmd = ["zfs", "get", "-H", "-r", "-o", "name,property,value", TASK_PROP, filesystem]
            tag_p = run_logged(tag_cmd, text=True)
            if tag_p.returncode == 0:
                for line in (tag_p.stdout or "").splitlines():
                    try:
                        name, prop, value = line.split("\t")
                        if prop == TASK_PROP and value != "-":
                            tag_map[name] = value
                    except ValueError:
                        continue
        except Exception:
            pass
        try:
            tier_cmd = ["zfs", "get", "-H", "-r", "-o", "name,property,value", TIER_PROP, filesystem]
            tier_p = run_logged(tier_cmd, text=True)
            if tier_p.returncode == 0:
                for line in (tier_p.stdout or "").splitlines():
                    try:
                        name, prop, value = line.split("\t")
                        if prop == TIER_PROP and value != "-":
                            tier_map[name] = value
                    except ValueError:
                        continue
        except Exception:
            pass
        for s in snaps:
            s.task_tag = tag_map.get(s.name)
            s.tier_tag = tier_map.get(s.name)

        return snaps

    err = (p.stderr or p.stdout or "").lower()
    if "dataset does not exist" in err or "cannot open" in err:
        return None
    raise subprocess.CalledProcessError(p.returncode, cmd, output=p.stdout, stderr=p.stderr)


def get_remote_snapshots(user, host, ssh_port, filesystem):
    args = [
        "zfs",
        "list",
        "-H",
        "-p",
        "-o",
        "name,guid,creation,createtxg",
        "-t",
        "snapshot",
        "-r",
        filesystem,
    ]

    try:
        p = ssh_run_args(user, host, ssh_port, args, capture_output=True, check=False, text=False, timeout=ZFS_LIST_TIMEOUT)
    except subprocess.TimeoutExpired:
        msg = f"Timed out after {ZFS_LIST_TIMEOUT}s listing remote snapshots on {user}@{host}:{filesystem}. The remote pool may be degraded or unresponsive."
        print(msg, file=sys.stderr)
        notifier.notify(f"STATUS={msg}")
        sys.exit(1)

    if p.returncode == 0:
        snapshots = []
        out = (p.stdout or b"")
        if isinstance(out, str):
            out = out.encode()
        for raw_line in out.split(b"\n"):
            line = raw_line.decode(errors="replace")
            snap = parse_snapshot_line(line)
            if snap:
                snapshots.append(snap)
        del out  # free raw bytes early

        # Fetch task tags from remote for ownership tracking
        tag_map = {}
        tier_map = {}
        try:
            tag_args = ["zfs", "get", "-H", "-r", "-o", "name,property,value", TASK_PROP, filesystem]
            tag_p = ssh_run_args(user, host, ssh_port, tag_args, capture_output=True, check=False, text=False)
            if tag_p.returncode == 0:
                tag_out = (tag_p.stdout or b"")
                if isinstance(tag_out, str):
                    tag_out = tag_out.encode()
                for raw_line in tag_out.split(b"\n"):
                    try:
                        parts = raw_line.decode(errors="replace").split("\t")
                        if len(parts) >= 3 and parts[1] == TASK_PROP and parts[2] != "-":
                            tag_map[parts[0]] = parts[2]
                    except (ValueError, IndexError):
                        continue
                del tag_out
        except Exception:
            pass
        try:
            tier_args = ["zfs", "get", "-H", "-r", "-o", "name,property,value", TIER_PROP, filesystem]
            tier_p = ssh_run_args(user, host, ssh_port, tier_args, capture_output=True, check=False, text=False)
            if tier_p.returncode == 0:
                tier_out = (tier_p.stdout or b"")
                if isinstance(tier_out, str):
                    tier_out = tier_out.encode()
                for raw_line in tier_out.split(b"\n"):
                    try:
                        parts = raw_line.decode(errors="replace").split("\t")
                        if len(parts) >= 3 and parts[1] == TIER_PROP and parts[2] != "-":
                            tier_map[parts[0]] = parts[2]
                    except (ValueError, IndexError):
                        continue
                del tier_out
        except Exception:
            pass
        for s in snapshots:
            s.task_tag = tag_map.get(s.name)
            s.tier_tag = tier_map.get(s.name)

        return snapshots

    errb = (p.stderr or b"")
    outb = (p.stdout or b"")
    if isinstance(errb, str):
        errb = errb.encode()
    if isinstance(outb, str):
        outb = outb.encode()
    err_output = errb.decode(errors="replace").lower() + outb.decode(errors="replace").lower()

    if "dataset does not exist" in err_output or "cannot open" in err_output:
        return None

    print(f"ERROR: Failed to fetch remote snapshots for {filesystem}:\n{err_output}")
    sys.exit(1)


def get_written_since_snapshot(dataset, snapshot_fullname, remote_user=None, remote_host=None, remote_port="22"):
    prop = f"written@{snapshot_fullname}"
    base_cmd = ["zfs", "get", "-H", "-p", "-o", "value", prop, dataset]

    if remote_host:
        p = ssh_run_args(remote_user, remote_host, remote_port, base_cmd, capture_output=True, check=False, text=True)
        if p.returncode != 0:
            return None
        out = (p.stdout or "").strip()
    else:
        p = subprocess.run(base_cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            return None
        out = (p.stdout or "").strip()

    if not out or out == "-":
        return None

    try:
        return int(out)
    except ValueError:
        return None


def get_available_bytes(dataset, remote_user=None, remote_host=None, remote_port=22):
    base_cmd = ["zfs", "get", "-H", "-p", "-o", "value", "available", dataset]

    if remote_host:
        p = ssh_run_args(remote_user, remote_host, remote_port, base_cmd, capture_output=True, check=False, text=True)
        if p.returncode != 0:
            return None
        out = (p.stdout or "").strip()
    else:
        p = subprocess.run(base_cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            return None
        out = (p.stdout or "").strip()

    if not out or out == "-":
        return None

    try:
        return int(out)
    except ValueError:
        return None


def create_snapshot_local(filesystem, is_recursive, task_name, custom_name=None, tier_idx=None):
    command = ["zfs", "snapshot"]
    if is_recursive:
        command.append("-r")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    tier_tag = f"-t{tier_idx}" if tier_idx is not None else ""
    if custom_name:
        new_snap = f"{filesystem}@{custom_name}{tier_tag}-{timestamp}"
    else:
        new_snap = f"{filesystem}@{task_name}{tier_tag}-{timestamp}"
    command.append(new_snap)

    notifier.notify(f"STATUS=Creating snapshot {new_snap}…")
    available = get_available_bytes(filesystem)
    if available is not None and available <= 0:
        msg = f"Not enough space to create snapshot on {filesystem}. Available: {format_bytes(available)}."
        print(msg)
        notifier.notify(f"STATUS={msg}")
        sys.exit(1)
    try:
        # subprocess.run(command, check=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        run_logged(command, check=True, text=True)
    except subprocess.CalledProcessError as e:
        raw = (e.stderr or "") + (
            "\n" + (e.stdout or "")
            if (e.stderr or "") and (e.stdout or "")
            else (e.stdout or "")
        )
        msg = raw.lower()
        if "snapshot already exists" in msg or "dataset already exists" in msg:
            print(f"Snapshot already exists ({new_snap}) — likely a queued duplicate start; exiting successfully.")
            notifier.notify(f"STATUS=Snapshot {new_snap} already exists; treating as completed.")
            sys.exit(0)
        detail = (raw or msg).strip()
        print(f"Snapshot creation failed (rc={e.returncode}): {detail}")
        notifier.notify(f"STATUS=Snapshot creation failed: {detail}")
        raise

    print(f"new snapshot created: {new_snap}")
    notifier.notify(f"STATUS=Snapshot created: {new_snap}")

    # Tag snapshot with task ownership and tier index via ZFS properties
    try:
        run_logged(["zfs", "set", f"{TASK_PROP}={task_name}", new_snap], check=True, text=True)
    except Exception as e:
        print(f"WARNING: failed to tag snapshot {new_snap}: {e}")

    if tier_idx is not None:
        try:
            run_logged(["zfs", "set", f"{TIER_PROP}=t{tier_idx}", new_snap], check=True, text=True)
        except Exception as e:
            print(f"WARNING: failed to set tier property on {new_snap}: {e}")

    return new_snap


def create_snapshot_remote(filesystem, is_recursive, task_name, custom_name, remote_user, remote_host, ssh_port, tier_idx=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    tier_tag = f"-t{tier_idx}" if tier_idx is not None else ""
    if custom_name:
        new_snap = f"{filesystem}@{custom_name}{tier_tag}-{timestamp}"
    else:
        new_snap = f"{filesystem}@{task_name}{tier_tag}-{timestamp}"

    cmd = ["zfs", "snapshot"]
    if is_recursive:
        cmd.append("-r")
    cmd.append(new_snap)

    notifier.notify(f"STATUS=Creating remote snapshot {new_snap}…")

    available = get_available_bytes(
        filesystem,
        remote_user=remote_user,
        remote_host=remote_host,
        remote_port=ssh_port,
    )
    if available is not None and available <= 0:
        msg = f"Not enough space to create remote snapshot on {filesystem}. Available: {format_bytes(available)}."
        print(msg)
        notifier.notify(f"STATUS={msg}")
        sys.exit(1)

    p = ssh_run_args(remote_user, remote_host, ssh_port, cmd, capture_output=True, check=False, text=True)

    # Retry on transient "dataset is busy" errors (e.g. another send/recv just finished)
    if p.returncode != 0:
        raw0 = (p.stderr or "") + ("\n" + (p.stdout or "") if (p.stderr or "") and (p.stdout or "") else (p.stdout or ""))
        if "dataset is busy" in raw0.lower():
            max_retries = 5
            for attempt in range(1, max_retries + 1):
                delay = 3 * attempt
                print(f"Remote snapshot creation got 'dataset is busy' — retrying in {delay}s (attempt {attempt}/{max_retries})")
                notifier.notify(f"STATUS=Dataset busy, retrying snapshot in {delay}s ({attempt}/{max_retries})…")
                time.sleep(delay)
                p = ssh_run_args(remote_user, remote_host, ssh_port, cmd, capture_output=True, check=False, text=True)
                if p.returncode == 0:
                    break
                raw0 = (p.stderr or "") + ("\n" + (p.stdout or "") if (p.stderr or "") and (p.stdout or "") else (p.stdout or ""))
                if "dataset is busy" not in raw0.lower():
                    break  # Different error, fall through to normal handling

    if p.returncode != 0:
        raw = (p.stderr or "") + ("\n" + (p.stdout or "") if (p.stderr or "") and (p.stdout or "") else (p.stdout or ""))
        msg = raw.lower()
        if "snapshot already exists" in msg or "dataset already exists" in msg:
            print(f"Remote snapshot already exists ({new_snap}) — likely a queued duplicate start; exiting successfully.")
            notifier.notify(f"STATUS=Remote snapshot {new_snap} already exists; treating as completed.")
            sys.exit(0)
        detail = (raw or msg).strip()
        print(f"Remote snapshot creation failed (rc={p.returncode}): {detail}")
        notifier.notify(f"STATUS=Remote snapshot creation failed: {detail}")
        raise subprocess.CalledProcessError(p.returncode, ["ssh", f"{remote_user}@{remote_host}", "<quoted>"], output=p.stdout, stderr=p.stderr)

    print(f"new remote snapshot created: {new_snap}")
    notifier.notify(f"STATUS=Remote snapshot created: {new_snap}")

    # Tag remote snapshot with task ownership and tier index via ZFS properties
    try:
        ssh_run_args(remote_user, remote_host, ssh_port,
                     ["zfs", "set", f"{TASK_PROP}={task_name}", new_snap],
                     capture_output=True, check=False, text=True)
    except Exception as e:
        print(f"WARNING: failed to tag remote snapshot {new_snap}: {e}")

    if tier_idx is not None:
        try:
            ssh_run_args(remote_user, remote_host, ssh_port,
                         ["zfs", "set", f"{TIER_PROP}=t{tier_idx}", new_snap],
                         capture_output=True, check=False, text=True)
        except Exception as e:
            print(f"WARNING: failed to set tier property on remote {new_snap}: {e}")

    return new_snap


def tag_received_snapshots(dest_filesystem, snap_suffix, task_name, tier_idx=None,
                           remote_user=None, remote_host=None, remote_port="22"):
    """
    After a successful receive, tag the destination snapshot(s) with our custom
    ZFS properties (task_name, tier). ZFS send/receive does not propagate user
    properties, so we must set them explicitly on the receive side.

    For recursive receives, tags only the root dataset snapshot (matching the
    source tagging behavior).
    """
    dest_snap = f"{dest_filesystem}@{snap_suffix}"
    props_to_set = [(TASK_PROP, task_name)]
    if tier_idx is not None:
        props_to_set.append((TIER_PROP, f"t{tier_idx}"))

    for prop, value in props_to_set:
        try:
            if remote_user and remote_host:
                ssh_run_args(remote_user, remote_host, remote_port,
                             ["zfs", "set", f"{prop}={value}", dest_snap],
                             capture_output=True, check=True, text=True)
            else:
                run_logged(["zfs", "set", f"{prop}={value}", dest_snap], check=True, text=True)
        except Exception as e:
            print(f"WARNING: failed to tag received snapshot {dest_snap} with {prop}={value}: {e}")


def snapshot_exists_on_destination(
    dest_filesystem: str,
    snapshot_suffix_name: str,
    remote_user=None,
    remote_host=None,
    remote_port="22",
):
    target_name = f"{dest_filesystem}@{snapshot_suffix_name}"
    if remote_host:
        dest_snaps = get_remote_snapshots(remote_user, remote_host, remote_port, dest_filesystem)
    else:
        dest_snaps = get_local_snapshots(dest_filesystem)

    if dest_snaps is None:
        return False, target_name

    for snap in dest_snaps:
        if snap.name == target_name:
            return True, target_name

    return False, target_name
