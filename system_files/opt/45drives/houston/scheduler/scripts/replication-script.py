import subprocess
import sys
import datetime
import os
import time
import json
import shlex
import re
import threading
import traceback
from collections import deque
import getpass
from notify import get_notifier


class SafeStream:
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


# Avoid crashing if stdout/stderr are closed by the service manager
sys.stdout = SafeStream(sys.stdout)
sys.stderr = SafeStream(sys.stderr)

notifier = get_notifier()


class Snapshot:
    def __init__(self, name, guid, creation, creation_epoch=0, order_key=0):
        self.name = name
        self.guid = guid
        self.creation = creation
        self.creation_epoch = creation_epoch
        self.order_key = order_key


def split_zfs_list_line(line: str):
    line = (line or "").rstrip("\n")
    if "\t" in line:
        return line.split("\t")

    parts = line.rsplit(None, 3)
    if len(parts) < 3:
        return line.split()
    return parts


def safe_print(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            sys.stderr.write(str(msg) + "\n")
            sys.stderr.flush()
        except Exception:
            pass


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


def as_bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def send_houston_notification(payload):
    try:
        dbus_script = "/opt/45drives/houston/houston-notify"
        debug_log = "/tmp/zfs_replication_debug.log"
        subprocess.run(
            ["python3", dbus_script, json.dumps(payload)],
            stdout=open(debug_log, "a"),
            stderr=subprocess.STDOUT,
        )
    except Exception as notify_error:
        print(f"Failed to send D-Bus notification: {notify_error}")


def ssh_base_args(user, host, port):
    args = ["ssh"]
    if str(port) != "22":
        args.extend(["-p", str(port)])
    args.append(f"{user}@{host}")
    return args


def ssh_run_args(user, host, port, args, *, capture_output=True, check=False, text=False, timeout=None):
    ssh_cmd = ["ssh"]
    if str(port) != "22":
        ssh_cmd += ["-p", str(port)]
    ssh_cmd.append(f"{user}@{host}")

    remote_cmd = " ".join(shlex.quote(str(a)) for a in args)
    ssh_cmd.append(remote_cmd)

    return subprocess.run(
        ssh_cmd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        universal_newlines=text,
        check=check,
        timeout=timeout,
    )


def ssh_popen_args(user, host, port, args, *, stdin=None, stdout=None, stderr=None, universal_newlines=False):
    ssh_cmd = ["ssh"]
    if str(port) != "22":
        ssh_cmd += ["-p", str(port)]
    ssh_cmd.append(f"{user}@{host}")

    remote_cmd = " ".join(shlex.quote(str(a)) for a in args)
    ssh_cmd.append(remote_cmd)

    return subprocess.Popen(
        ssh_cmd,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        universal_newlines=universal_newlines,
    )


def join_zfs_path(pool: str, dataset: str) -> str:
    pool = (pool or "").strip()
    ds = (dataset or "").strip()

    if not pool:
        return ds
    if not ds:
        return pool

    if ds == pool or ds.startswith(pool + "/"):
        return ds

    first = ds.split("/", 1)[0]
    if first == pool:
        return ds

    return f"{pool}/{ds}"


def snapshot_suffix(full_snap_name: str) -> str:
    return (full_snap_name or "").split("@", 1)[-1]


def dataset_of_snapshot(full_snap_name: str) -> str:
    return (full_snap_name or "").split("@", 1)[0]


def filter_dataset_snapshots(snaps, dataset: str):
    ds = (dataset or "").strip()
    return [s for s in (snaps or []) if dataset_of_snapshot(s.name) == ds]


def is_task_snapshot(full_snap_name: str, task_name: str, custom_name: str = "") -> bool:
    suf = snapshot_suffix(full_snap_name)
    tn = (task_name or "").strip()
    cn = (custom_name or "").strip()

    if not tn:
        return False

    if suf.startswith(f"{tn}-"):
        return True
    if cn and suf.startswith(f"{cn}-{tn}-"):
        return True
    return False


def get_dest_ports(transfer_method: str):
    """
    Returns (ssh_port, data_port).
    - ssh_port: control-plane operations (list/prune/start listener)
    - data_port: data-plane for netcat transfers
    """
    data_port = os.environ.get("zfsRepConfig_destDataset_port", "22")
    ssh_port = os.environ.get("zfsRepConfig_destDataset_sshPort", "")

    transfer_method = (transfer_method or "").strip().lower()

    if transfer_method == "netcat":
        if not ssh_port:
            ssh_port = "22"
        return (ssh_port, data_port)

    if not ssh_port:
        ssh_port = data_port or "22"
    return (ssh_port, data_port)


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
    p = subprocess.run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if p.returncode == 0:
        snaps = []
        for line in (p.stdout or "").splitlines():
            snap = parse_snapshot_line(line)
            if snap:
                snaps.append(snap)
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

    p = ssh_run_args(user, host, ssh_port, args, capture_output=True, check=False, text=False)

    if p.returncode == 0:
        snapshots = []
        out = (p.stdout or b"")
        if isinstance(out, str):
            out = out.encode()
        for line in out.decode(errors="replace").splitlines():
            snap = parse_snapshot_line(line)
            if snap:
                snapshots.append(snap)
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


def build_zfs_send_args(sendName, sendName2, *, recursive, compressed, raw):
    args = ["zfs", "send"]
    if recursive:
        args.append("-R")
    if compressed:
        args.append("-Lce")
    if raw:
        args.append("-w")
    if sendName2:
        args.extend(["-I" if recursive else "-i", sendName2])
    args.append(sendName)
    return args


class StreamCapture:
    def __init__(self, stream, max_lines=200):
        self._lines = deque(maxlen=max_lines)
        self._stream = stream
        self._thread = None
        if stream is not None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self):
        try:
            for line in iter(self._stream.readline, b""):
                self._lines.append(line)
        except Exception:
            pass

    def text(self) -> str:
        if not self._lines:
            return ""
        return b"".join(self._lines).decode(errors="replace")


def estimate_send_size(send_cmd):
    try:
        cmd = list(send_cmd)
        if len(cmd) < 2 or cmd[0] != "zfs" or cmd[1] != "send":
            return None
        cmd.insert(2, "-nP")
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            return None
        text = (p.stdout or b"") + (p.stderr or b"")
        out = text.decode(errors="replace")
        for line in out.splitlines():
            if "size" in line.lower():
                m = re.search(r"\bsize\b\s*=?\s*(\d+)", line, re.IGNORECASE)
                if m:
                    return int(m.group(1))
        nums = re.findall(r"\b\d+\b", out)
        if len(nums) == 1:
            return int(nums[0])
    except Exception:
        return None
    return None


def estimate_send_size_remote(remote_user, remote_host, remote_port, send_cmd):
    try:
        cmd = list(send_cmd)
        if len(cmd) < 2 or cmd[0] != "zfs" or cmd[1] != "send":
            return None
        cmd.insert(2, "-nP")

        p = ssh_run_args(remote_user, remote_host, remote_port, cmd, capture_output=True, check=False, text=False)

        if p.returncode != 0:
            return None

        outb = (p.stdout or b"")
        errb = (p.stderr or b"")
        if isinstance(outb, str):
            outb = outb.encode()
        if isinstance(errb, str):
            errb = errb.encode()

        out = (outb + errb).decode(errors="replace")

        for line in out.splitlines():
            if "size" in line.lower():
                m = re.search(r"\bsize\b\s*=?\s*(\d+)", line, re.IGNORECASE)
                if m:
                    return int(m.group(1))
        nums = re.findall(r"\b\d+\b", out)
        if len(nums) == 1:
            return int(nums[0])
    except Exception:
        return None
    return None


def stream_with_progress(src, dst, total_bytes, label="Transferring", min_interval=1.0):
    bytes_sent = 0
    last_pct = -1
    last_emit = 0.0

    if total_bytes:
        notifier.notify(f"STATUS={label}… 0% complete")
    else:
        notifier.notify(f"STATUS={label}…")

    while True:
        chunk = src.read(1024 * 1024)
        if not chunk:
            break
        try:
            dst.write(chunk)
        except (BrokenPipeError, ValueError):
            break
        bytes_sent += len(chunk)
        now = time.time()
        if total_bytes:
            pct = int(bytes_sent * 100 / total_bytes)
            if pct > last_pct and (now - last_emit) >= min_interval:
                pct = min(pct, 99)
                notifier.notify(f"STATUS={label}… {pct}% complete")
                last_pct = pct
                last_emit = now
        else:
            if (now - last_emit) >= max(5.0, min_interval):
                mib = bytes_sent / (1024 * 1024)
                notifier.notify(f"STATUS={label}… {mib:.1f} MiB sent")
                safe_print(f"{label}… {mib:.1f} MiB sent")
                last_emit = now

    try:
        dst.flush()
    except Exception:
        pass

    return bytes_sent


def get_written_since_snapshot(dataset, snapshot_fullname, remote_user=None, remote_host=None, remote_port=22):
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


def format_bytes(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KiB"
    if n < 1024**3:
        return f"{n / (1024**2):.1f} MiB"
    if n < 1024**4:
        return f"{n / (1024**3):.1f} GiB"
    return f"{n / (1024**4):.1f} TiB"


def create_snapshot_local(filesystem, is_recursive, task_name, custom_name=None):
    command = ["zfs", "snapshot"]
    if is_recursive:
        command.append("-r")
    timestamp = datetime.datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
    new_snap = f"{filesystem}@{(custom_name + '-') if custom_name else ''}{task_name}-{timestamp}"
    command.append(new_snap)

    notifier.notify(f"STATUS=Creating snapshot {new_snap}…")
    available = get_available_bytes(filesystem)
    if available is not None and available <= 0:
        msg = f"Not enough space to create snapshot on {filesystem}. Available: {format_bytes(available)}."
        print(msg)
        notifier.notify(f"STATUS={msg}")
        sys.exit(1)
    try:
        subprocess.run(command, check=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    return new_snap


def create_snapshot_remote(filesystem, is_recursive, task_name, custom_name, remote_user, remote_host, ssh_port):
    timestamp = datetime.datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
    new_snap = f"{filesystem}@{(custom_name + '-') if custom_name else ''}{task_name}-{timestamp}"

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
    return new_snap


def prune_snapshots_by_retention(
    filesystem,
    task_name,
    retention_time,
    retention_unit,
    excluded_snapshot_name,
    remote_user=None,
    remote_host=None,
    remote_port=22,
    transferMethod="ssh",
    progress_base=0,
    progress_span=100,
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

    for snapshot in snapshots:
        if is_task_snapshot(snapshot.name, task_name):
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

    for idx, snapshot in enumerate(snapshots_to_delete, start=1):
        if remote_host:
            p = ssh_run_args(
                remote_user,
                remote_host,
                remote_port,
                ["zfs", "destroy", snapshot.name],
                capture_output=True,
                check=False,
                text=True,
            )
            if p.returncode != 0:
                err = (p.stderr or p.stdout or "").strip()
                print(f"Failed to delete snapshot {snapshot.name}: {err}")
                notifier.notify(f"STATUS=Failed to delete snapshot {snapshot.name}")
                sys.exit(1)
            print(f"Deleted snapshot: {snapshot.name}")
        else:
            delete_command = ["zfs", "destroy", snapshot.name]
            try:
                subprocess.run(delete_command, check=True)
                print(f"Deleted snapshot: {snapshot.name}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to delete snapshot {snapshot.name}: {e}")
                notifier.notify(f"STATUS=Failed to delete snapshot {snapshot.name}")
                sys.exit(1)

        pct = start + int(idx * span / total)
        notifier.notify(f"STATUS=Pruning {total} {prefix}snapshot(s)… {pct}% complete")

    msg = f"Pruned {len(snapshots_to_delete)} snapshots older than retention period ({retention_val} {retention_unit})."
    final_pct = min(100, start + span)
    notifier.notify(f"STATUS={msg} {final_pct}% complete")
    return final_pct


def send_snapshot_push(
    sendName,
    recvName,
    sendName2="",
    compressed=False,
    raw=False,
    recvHost="",
    recvSshPort="22",
    recvHostUser="",
    mBufferSize=1,
    mBufferUnit="G",
    forceOverwrite=False,
    transferMethod="",
    recursive=False,
    recvDataPort=None,
):
    notifier.notify("STATUS=Preparing ZFS send/recv pipeline…")

    send_cmd = build_zfs_send_args(
        sendName,
        sendName2,
        recursive=recursive,
        compressed=compressed,
        raw=raw,
    )

    if sendName2:
        print(f"sending incrementally from {sendName2} -> {sendName} to {recvName}")
    else:
        print(f"sending {sendName} to {recvName}")

    total_bytes = estimate_send_size(send_cmd)
    if total_bytes is None:
        print("Note: Could not estimate send size; progress will be indeterminate.")

    process_send = subprocess.Popen(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if transferMethod == "local" or not recvHost:
        recv_cmd = ["zfs", "recv", "-s"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(recvName)

        process_recv = subprocess.Popen(
            recv_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if process_send.stdout is None or process_recv.stdin is None:
            raise RuntimeError("Failed to initialize send/recv pipes.")

        stream_with_progress(process_send.stdout, process_recv.stdin, total_bytes, label="Transferring")
        try:
            process_recv.stdin.close()
            process_recv.stdin = None
        except Exception:
            pass

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        process_send.wait()

        recv_stdout, recv_stderr = process_recv.communicate()
        recv_stdout = recv_stdout.decode(errors="replace") if recv_stdout else ""
        recv_stderr = recv_stderr.decode(errors="replace") if recv_stderr else ""

        if process_send.returncode != 0:
            notifier.notify("STATUS=Local send failed.")
            if send_stderr:
                print(f"send error: {send_stderr}")
            sys.exit(1)

        if process_recv.returncode != 0:
            notifier.notify("STATUS=Local receive failed.")
            print(f"recv error: {recv_stderr}")
            sys.exit(1)

        notifier.notify("STATUS=Local receive completed.")
        if recv_stdout:
            print(recv_stdout)
        return

    if transferMethod == "ssh":
        notifier.notify(f"STATUS=Sending snapshot {sendName} to {recvHostUser}@{recvHost}:{recvName} via ssh…")

        m_buff_cmd = ["mbuffer", "-s", "256k", "-m", str(mBufferSize) + mBufferUnit]
        process_m_buff = subprocess.Popen(
            m_buff_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mbuf_capture = StreamCapture(process_m_buff.stderr)

        flags = ["zfs", "recv", "-s"]
        if forceOverwrite:
            flags.append("-F")
        flags.append(recvName)

        process_remote_recv = ssh_popen_args(
            recvHostUser,
            recvHost,
            recvSshPort,
            flags,
            stdin=process_m_buff.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
        )

        if process_send.stdout is None or process_m_buff.stdin is None:
            raise RuntimeError("Failed to initialize send/mbuffer pipes.")

        stream_with_progress(process_send.stdout, process_m_buff.stdin, total_bytes, label="Transferring")
        try:
            process_m_buff.stdin.close()
        except Exception:
            pass

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        process_send.wait()
        process_m_buff.wait()

        stdout, stderr = process_remote_recv.communicate()
        stdout = stdout.decode(errors="replace") if stdout else ""
        stderr = stderr.decode(errors="replace") if stderr else ""

        mbuf_err = mbuf_capture.text()

        if process_send.returncode != 0:
            notifier.notify("STATUS=Remote send failed.")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            sys.exit(1)

        if process_m_buff.returncode != 0:
            notifier.notify("STATUS=Remote receive failed.")
            if mbuf_err:
                print(f"[Sender Side] mbuffer error: {mbuf_err}")
            sys.exit(1)

        if process_remote_recv.returncode != 0:
            notifier.notify("STATUS=Remote receive failed.")
            print(f"ERROR: remote recv error: {stderr}")
            sys.exit(1)

        notifier.notify("STATUS=Remote receive completed.")
        if stdout:
            print(stdout)
        return

    if transferMethod == "netcat":
        data_port = str(recvDataPort or recvSshPort or "31337")
        ssh_port = str(recvSshPort or "22")

        notifier.notify(f"STATUS=Sending snapshot {sendName} via netcat to {recvHostUser}@{recvHost}:{recvName}…")

        recv_q = shlex.quote(recvName)
        listen_cmd = f"nc -l {shlex.quote(data_port)} | zfs recv -s {'-F ' if forceOverwrite else ''}{recv_q}"
        ssh_cmd_listener = ssh_base_args(recvHostUser, recvHost, ssh_port)
        ssh_cmd_listener.append(listen_cmd)

        ssh_process_listener = subprocess.Popen(
            ssh_cmd_listener,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        time.sleep(2)

        mbuffer_cmd = ["mbuffer", "-s", "256k", "-m", f"{mBufferSize}{mBufferUnit}"]
        nc_cmd = ["nc", recvHost, data_port]

        process_mbuffer = subprocess.Popen(
            mbuffer_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mbuf_capture = StreamCapture(process_mbuffer.stderr)
        process_nc = subprocess.Popen(
            nc_cmd,
            stdin=process_mbuffer.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if process_send.stdout is None or process_mbuffer.stdin is None:
            raise RuntimeError("Failed to initialize send/mbuffer pipes.")

        stream_with_progress(process_send.stdout, process_mbuffer.stdin, total_bytes, label="Transferring")
        try:
            process_mbuffer.stdin.close()
        except Exception:
            pass

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        process_send.wait()
        process_mbuffer.wait()

        _, nc_stderr = process_nc.communicate()

        mbuf_stderr = mbuf_capture.text()

        if process_send.returncode != 0:
            notifier.notify("STATUS=Netcat send failed.")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            ssh_process_listener.terminate()
            sys.exit(1)

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=Netcat send failed.")
            if mbuf_stderr:
                print(f"[Sender Side] mbuffer error: {mbuf_stderr}")
            ssh_process_listener.terminate()
            sys.exit(1)

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat send failed.")
            print(f"[Sender Side] nc error: {nc_stderr.decode(errors='replace')}")
            ssh_process_listener.terminate()
            sys.exit(1)

        ssh_stdout, ssh_stderr = ssh_process_listener.communicate(timeout=300)
        if ssh_process_listener.returncode != 0:
            notifier.notify("STATUS=Remote receive via netcat failed.")
            print(f"[Receiver Side] Error during receive: {ssh_stderr.strip()}")
            sys.exit(1)

        notifier.notify("STATUS=Netcat send/receive completed.")

        snapshot_process = ssh_run_args(
            recvHostUser,
            recvHost,
            ssh_port,
            ["zfs", "list", recvName],
            capture_output=True,
            check=False,
            text=True,
        )
        if snapshot_process.returncode != 0:
            err = (snapshot_process.stderr or snapshot_process.stdout or "").strip()
            print(f"[Receiver Side] Error checking dataset: {err}")
            sys.exit(1)

        return

    print("ERROR: Invalid transferMethod specified. Must be 'local', 'ssh', or 'netcat'.")
    sys.exit(1)

def send_snapshot_pull(
    remoteSnapName,
    localRecvFs,
    remoteBaseSnapName="",
    compressed=False,
    raw=False,
    remoteHost="",
    remoteSshPort="22",
    remoteUser="root",
    mBufferSize=1,
    mBufferUnit="G",
    forceOverwrite=False,
    recursive=False,
):
    notifier.notify("STATUS=Preparing ZFS pull pipeline…")

    if not remoteHost:
        raise RuntimeError("Pull replication requires a remote host.")

    remote_send_args = build_zfs_send_args(
        remoteSnapName,
        remoteBaseSnapName,
        recursive=recursive,
        compressed=compressed,
        raw=raw,
    )

    total_bytes = estimate_send_size_remote(remoteUser, remoteHost, remoteSshPort, remote_send_args)
    if total_bytes is None:
        print("Note: Could not estimate send size; progress will be indeterminate.")

    if remoteBaseSnapName:
        print(f"pulling incrementally from {remoteBaseSnapName} -> {remoteSnapName} into {localRecvFs}")
    else:
        print(f"pulling {remoteSnapName} into {localRecvFs}")

    process_remote_send = ssh_popen_args(
        remoteUser,
        remoteHost,
        remoteSshPort,
        remote_send_args,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    )

    m_buff_cmd = ["mbuffer", "-s", "256k", "-m", str(mBufferSize) + mBufferUnit]
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    mbuf_capture = StreamCapture(process_m_buff.stderr)

    recv_cmd = ["zfs", "recv", "-s"]
    if forceOverwrite:
        recv_cmd.append("-F")
    recv_cmd.append(localRecvFs)

    process_local_recv = subprocess.Popen(
        recv_cmd,
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if process_remote_send.stdout is None or process_m_buff.stdin is None:
        raise RuntimeError("Failed to initialize send/mbuffer pipes.")

    stream_with_progress(process_remote_send.stdout, process_m_buff.stdin, total_bytes, label="Transferring")
    try:
        process_m_buff.stdin.close()
    except Exception:
        pass

    # Wait for send -> mbuffer -> recv chain to settle
    remote_out, remote_err = process_remote_send.communicate()
    remote_err = remote_err.decode(errors="replace") if remote_err else ""
    process_m_buff.wait()

    stdout, stderr = process_local_recv.communicate()
    stdout = stdout.decode(errors="replace") if stdout else ""
    stderr = stderr.decode(errors="replace") if stderr else ""

    if process_remote_send.returncode != 0:
        notifier.notify("STATUS=Local receive (pull) failed.")
        if remote_err:
            print(f"[Remote zfs send stderr]\n{remote_err}")
        sys.exit(1)

    mbuf_err = mbuf_capture.text()
    if process_m_buff.returncode != 0:
        notifier.notify("STATUS=Local receive (pull) failed.")
        if mbuf_err:
            print(f"[mbuffer stderr]\n{mbuf_err}")
        sys.exit(1)

    if process_local_recv.returncode != 0:
        notifier.notify("STATUS=Local receive (pull) failed.")
        if remote_err:
            print(f"[Remote zfs send stderr]\n{remote_err}")
        print(f"ERROR: local recv error: {stderr}")
        sys.exit(1)

    notifier.notify("STATUS=Pull receive completed.")
    if stdout:
        print(stdout)


def get_receive_resume_token(dest_filesystem, remote_user=None, remote_host=None, remote_port=22):
    base_args = ["zfs", "get", "-H", "-o", "value", "receive_resume_token", dest_filesystem]
    if remote_host:
        p = ssh_run_args(remote_user, remote_host, remote_port, base_args, capture_output=True, check=False, text=True)
        if p.returncode != 0:
            return ""
        token = (p.stdout or "").strip()
    else:
        p = subprocess.run(base_args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            return ""
        token = (p.stdout or "").strip()

    return "" if token in ("", "-") else token


def clear_receive_resume_token(dest_filesystem, remote_user=None, remote_host=None, remote_port=22):
    base_cmd = ["zfs", "receive", "-A", dest_filesystem]
    if remote_host:
        p = ssh_run_args(remote_user, remote_host, remote_port, base_cmd, capture_output=True, check=False, text=True)
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            return False, err
        return True, ""
    else:
        p = subprocess.run(base_cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            return False, err
        return True, ""


def resume_receive_push(
    resume_token,
    recvName,
    recvHost="",
    recvSshPort="22",
    recvHostUser="",
    mBufferSize=1,
    mBufferUnit="G",
    transferMethod="ssh",
    recvDataPort=None,
):
    notifier.notify("STATUS=Resuming ZFS send/recv pipeline from resume token…")

    send_cmd = ["zfs", "send", "-t", resume_token]
    process_send = subprocess.Popen(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if transferMethod == "local" or not recvHost:
        recv_cmd = ["zfs", "recv", "-s", recvName]
        process_recv = subprocess.Popen(
            recv_cmd,
            stdin=process_send.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process_recv.communicate()
        if process_recv.returncode != 0:
            notifier.notify("STATUS=Local resume receive failed.")
            err_msg = f"recv error: {stderr}"
            print(err_msg)
            return False, err_msg
        notifier.notify("STATUS=Local resume receive completed.")
        if stdout:
            print(stdout)
        return True, ""

    if transferMethod == "netcat":
        data_port = str(recvDataPort or recvSshPort or "31337")
        ssh_port = str(recvSshPort or "22")

        recv_q = shlex.quote(recvName)
        listen_cmd = f"nc -l {shlex.quote(data_port)} | zfs recv -s {recv_q}"
        ssh_cmd_listener = ssh_base_args(recvHostUser, recvHost, ssh_port)
        ssh_cmd_listener.append(listen_cmd)

        ssh_process_listener = subprocess.Popen(
            ssh_cmd_listener,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        time.sleep(2)

        mbuffer_cmd = ["mbuffer", "-s", "256k", "-m", f"{mBufferSize}{mBufferUnit}"]
        nc_cmd = ["nc", recvHost, data_port]

        process_mbuffer = subprocess.Popen(
            mbuffer_cmd,
            stdin=process_send.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process_nc = subprocess.Popen(
            nc_cmd,
            stdin=process_mbuffer.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        _, nc_stderr = process_nc.communicate()

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        mbuf_stderr = process_mbuffer.stderr.read().decode(errors="replace") if process_mbuffer.stderr else ""

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat resume send failed.")
            print(f"[Sender Side] nc error: {nc_stderr.decode(errors='replace')}")
            if mbuf_stderr:
                print(f"[Sender Side] mbuffer error: {mbuf_stderr}")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            ssh_process_listener.terminate()
            err_msg = "Netcat resume send failed."
            return False, err_msg

        ssh_stdout, ssh_stderr = ssh_process_listener.communicate(timeout=300)
        if ssh_process_listener.returncode != 0:
            notifier.notify("STATUS=Remote resume receive via netcat failed.")
            err_msg = f"[Receiver Side] Error during receive: {ssh_stderr.strip()}"
            print(err_msg)
            return False, err_msg

        notifier.notify("STATUS=Netcat resume send/receive completed.")
        if ssh_stdout:
            print(ssh_stdout)
        return True, ""

    if transferMethod != "ssh":
        print("ERROR: Resume tokens are only supported for local, ssh, or netcat transfers in this script.")
        return False, "Resume tokens are only supported for local, ssh, or netcat transfers in this script."

    m_buff_cmd = ["mbuffer", "-s", "256k", "-m", str(mBufferSize) + mBufferUnit]
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=process_send.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    process_remote_recv = ssh_popen_args(
        recvHostUser,
        recvHost,
        recvSshPort,
        ["zfs", "recv", "-s", recvName],
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    stdout, stderr = process_remote_recv.communicate()
    if process_remote_recv.returncode != 0:
        notifier.notify("STATUS=Remote resume receive failed.")
        err_msg = f"ERROR: remote recv error: {stderr}"
        print(err_msg)
        return False, err_msg
    notifier.notify("STATUS=Remote resume receive completed.")
    if stdout:
        print(stdout)
    return True, ""


def resume_receive_pull(
    resume_token,
    localRecvFs,
    remoteHost="",
    remoteSshPort="22",
    remoteUser="root",
    mBufferSize=1,
    mBufferUnit="G",
):
    notifier.notify("STATUS=Resuming ZFS pull pipeline from resume token…")

    if not remoteHost:
        raise RuntimeError("Pull replication requires a remote host.")

    process_remote_send = ssh_popen_args(
        remoteUser,
        remoteHost,
        remoteSshPort,
        ["zfs", "send", "-t", resume_token],
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    )

    m_buff_cmd = ["mbuffer", "-s", "256k", "-m", str(mBufferSize) + mBufferUnit]
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=process_remote_send.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    recv_cmd = ["zfs", "recv", "-s", localRecvFs]
    process_local_recv = subprocess.Popen(
        recv_cmd,
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    stdout, stderr = process_local_recv.communicate()
    if process_local_recv.returncode != 0:
        notifier.notify("STATUS=Local resume receive (pull) failed.")
        err_msg = f"ERROR: local recv error: {stderr}"
        print(err_msg)
        remote_err = process_remote_send.stderr.read().decode(errors="replace") if process_remote_send.stderr else ""
        mbuf_err = process_m_buff.stderr.read().decode(errors="replace") if process_m_buff.stderr else ""
        if remote_err:
            print(f"[Remote zfs send stderr]\n{remote_err}")
        if mbuf_err:
            print(f"[mbuffer stderr]\n{mbuf_err}")
        return False, err_msg

    notifier.notify("STATUS=Pull resume receive completed.")
    if stdout:
        print(stdout)
    return True, ""


def snapshot_exists_on_destination(
    dest_filesystem: str,
    snapshot_suffix_name: str,
    remote_user: str = None,
    remote_host: str = None,
    remote_port: str = "22",
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

def dbg(msg):
    with open("/tmp/zfs_rep_debug.log", "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} {msg}\n")


def main():
    try:
        notifier.notify("STATUS=Starting ZFS replication task…")
        notifier.notify("READY=1")
        notifier.notify("STATUS=Planning replication…")

        taskName = os.environ.get("taskName", "")

        direction = (os.environ.get("zfsRepConfig_direction", "push") or "push").strip().lower()
        if direction not in ("push", "pull"):
            direction = "push"

        isRecursiveSnap = as_bool(os.environ.get("zfsRepConfig_sendOptions_recursive_flag"))
        customName = os.environ.get("zfsRepConfig_sendOptions_customName", "")

        isRaw = as_bool(os.environ.get("zfsRepConfig_sendOptions_raw_flag"))
        isCompressed = as_bool(os.environ.get("zfsRepConfig_sendOptions_compressed_flag"))

        transferMethod = (os.environ.get("zfsRepConfig_sendOptions_transferMethod", "") or "").strip().lower()
        sshPort, dataPort = get_dest_ports(transferMethod)

        allowOverwrite = as_bool(os.environ.get("zfsRepConfig_sendOptions_allowOverwrite"), default=False)
        useExistingDest = as_bool(os.environ.get("zfsRepConfig_sendOptions_useExistingDest"), default=False)
        resumeFailAllowOverwrite = as_bool(
            os.environ.get("zfsRepConfig_sendOptions_resumeFailAllowOverwrite"),
            default=False,
        )

        remoteUser = os.environ.get("zfsRepConfig_destDataset_user", "root")
        remoteHost = os.environ.get("zfsRepConfig_destDataset_host", "")

        mBufferSize = os.environ.get("zfsRepConfig_sendOptions_mbufferSize", "1")
        mBufferUnit = os.environ.get("zfsRepConfig_sendOptions_mbufferUnit", "G")

        sourceRetentionTime = os.environ.get("zfsRepConfig_snapshotRetention_source_retentionTime", 0)
        sourceRetentionUnit = os.environ.get("zfsRepConfig_snapshotRetention_source_retentionUnit", "")

        destinationRetentionTime = os.environ.get("zfsRepConfig_snapshotRetention_destination_retentionTime", 0)
        destinationRetentionUnit = os.environ.get("zfsRepConfig_snapshotRetention_destination_retentionUnit", "")

        srcPool = os.environ.get("zfsRepConfig_sourceDataset_pool", "")
        srcDs = os.environ.get("zfsRepConfig_sourceDataset_dataset", "")
        dstPool = os.environ.get("zfsRepConfig_destDataset_pool", "")
        dstDs = os.environ.get("zfsRepConfig_destDataset_dataset", "")

        sourceFilesystem = join_zfs_path(srcPool, srcDs)
        destFilesystem = join_zfs_path(dstPool, dstDs)

        if not sourceFilesystem:
            raise RuntimeError("Source dataset is empty (zfsRepConfig_sourceDataset_pool/dataset).")
        if not destFilesystem:
            raise RuntimeError("Destination dataset is empty (zfsRepConfig_destDataset_pool/dataset).")

        if direction == "pull":
            if not remoteHost:
                raise RuntimeError("Pull replication requires Host to be set (remote source).")

            # In pull mode, destHost/user/port are the remote SOURCE endpoint.
            remote_source_fs = sourceFilesystem
            local_target_fs = destFilesystem

            # Treat "local" as invalid for pull; use ssh data path.
            if transferMethod == "local" or not transferMethod:
                transferMethod = "ssh"

            dbg(f"EUID={os.geteuid()} USER={getpass.getuser()} HOME={os.environ.get('HOME')}")
            dbg(f"remoteUser={remoteUser} remoteHost={remoteHost} sshPort={sshPort}")

            p = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-vv", f"{remoteUser}@{remoteHost}", "true"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )
            dbg("ssh -vv output:\n" + p.stdout)
            dbg(f"ssh returncode={p.returncode}")
            
            # ----- snapshot inventory -----
            sourceSnapshots = get_remote_snapshots(remoteUser, remoteHost, sshPort, remote_source_fs) or []
            sourceSnapshots.sort(key=lambda x: x.order_key)

            destinationSnapshots = get_local_snapshots(local_target_fs)
        else:
            # push mode: local source -> (remote target if host else local)
            local_source_fs = sourceFilesystem
            target_fs = destFilesystem

            if transferMethod == "ssh" and not remoteHost:
                transferMethod = "local"

            sourceSnapshots = get_local_snapshots(local_source_fs) or []
            sourceSnapshots.sort(key=lambda x: x.order_key)

            if remoteHost and remoteUser:
                destinationSnapshots = get_remote_snapshots(remoteUser, remoteHost, sshPort, target_fs)
            else:
                destinationSnapshots = get_local_snapshots(target_fs)

        forceOverwrite = False
        incrementalSnapName = ""

        # Resume token check (destination side)
        if direction == "pull":
            resume_token = get_receive_resume_token(destFilesystem)
            if resume_token:
                msg = f"Found resume token on destination {destFilesystem}. Attempting to resume receive."
                notifier.notify(f"STATUS={msg}")
                print(msg)
                send_houston_notification(
                    {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "event": "zfs_replication_resume_token",
                        "subject": "ZFS Replication Resume Token Found",
                        "email_message": f"{msg} Token: {resume_token}",
                        "fileSystem": destFilesystem,
                        "snapShot": "",
                        "replicationDestination": destFilesystem,
                        "severity": "warning",
                        "errors": resume_token,
                    }
                )
                ok, err = resume_receive_pull(
                    resume_token=resume_token,
                    localRecvFs=destFilesystem,
                    remoteHost=remoteHost,
                    remoteSshPort=sshPort,
                    remoteUser=remoteUser,
                    mBufferSize=str(mBufferSize),
                    mBufferUnit=mBufferUnit,
                )
                if ok:
                    return
                err_lower = (err or "").lower()
                if resumeFailAllowOverwrite:
                    msg = (
                        f"Resume attempt failed for {destFilesystem}; clearing resume token and continuing with normal replication."
                    )
                    notifier.notify(f"STATUS={msg}")
                    print(msg)
                    cleared, clear_err = clear_receive_resume_token(destFilesystem)
                    if not cleared:
                        fail_msg = f"Failed to clear resume token for {destFilesystem}: {clear_err}"
                        notifier.notify(f"STATUS={fail_msg}")
                        print(fail_msg)
                        sys.exit(2)
                elif "modified since" in err_lower or "has been modified" in err_lower:
                    hard_msg = (
                        "Resume failed because destination was modified since the most recent snapshot. "
                        "Refusing to continue with normal replication."
                    )
                    notifier.notify(f"STATUS={hard_msg}")
                    print(hard_msg)
                    sys.exit(2)
                warn_msg = f"Resume attempt failed for {destFilesystem}. Continuing with normal replication."
                notifier.notify(f"STATUS={warn_msg}")
                print(warn_msg)
                send_houston_notification(
                    {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "event": "zfs_replication_resume_failed",
                        "subject": "ZFS Replication Resume Failed",
                        "email_message": f"{warn_msg} Token: {resume_token}. Error: {err}",
                        "fileSystem": destFilesystem,
                        "snapShot": "",
                        "replicationDestination": destFilesystem,
                        "severity": "warning",
                        "errors": f"{resume_token} | {err}",
                    }
                )
        else:
            resume_token = get_receive_resume_token(
                destFilesystem,
                remote_user=remoteUser if remoteHost else None,
                remote_host=remoteHost if remoteHost else None,
                remote_port=sshPort,
            )
            if resume_token:
                msg = f"Found resume token on destination {destFilesystem}. Attempting to resume receive."
                notifier.notify(f"STATUS={msg}")
                print(msg)
                send_houston_notification(
                    {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "event": "zfs_replication_resume_token",
                        "subject": "ZFS Replication Resume Token Found",
                        "email_message": f"{msg} Token: {resume_token}",
                        "fileSystem": destFilesystem,
                        "snapShot": "",
                        "replicationDestination": destFilesystem,
                        "severity": "warning",
                        "errors": resume_token,
                    }
                )
                ok, err = resume_receive_push(
                    resume_token=resume_token,
                    recvName=destFilesystem,
                    recvHost=remoteHost,
                    recvSshPort=sshPort,
                    recvHostUser=remoteUser,
                    mBufferSize=str(mBufferSize),
                    mBufferUnit=mBufferUnit,
                    transferMethod=transferMethod if transferMethod else "ssh",
                    recvDataPort=dataPort,
                )
                if ok:
                    return
                err_lower = (err or "").lower()
                if resumeFailAllowOverwrite:
                    msg = (
                        f"Resume attempt failed for {destFilesystem}; clearing resume token and continuing with normal replication."
                    )
                    notifier.notify(f"STATUS={msg}")
                    print(msg)
                    cleared, clear_err = clear_receive_resume_token(
                        destFilesystem,
                        remote_user=remoteUser if remoteHost else None,
                        remote_host=remoteHost if remoteHost else None,
                        remote_port=sshPort,
                    )
                    if not cleared:
                        fail_msg = f"Failed to clear resume token for {destFilesystem}: {clear_err}"
                        notifier.notify(f"STATUS={fail_msg}")
                        print(fail_msg)
                        sys.exit(2)
                elif "modified since" in err_lower or "has been modified" in err_lower:
                    hard_msg = (
                        "Resume failed because destination was modified since the most recent snapshot. "
                        "Refusing to continue with normal replication."
                    )
                    notifier.notify(f"STATUS={hard_msg}")
                    print(hard_msg)
                    sys.exit(2)
                warn_msg = f"Resume attempt failed for {destFilesystem}. Continuing with normal replication."
                notifier.notify(f"STATUS={warn_msg}")
                print(warn_msg)
                send_houston_notification(
                    {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "event": "zfs_replication_resume_failed",
                        "subject": "ZFS Replication Resume Failed",
                        "email_message": f"{warn_msg} Token: {resume_token}. Error: {err}",
                        "fileSystem": destFilesystem,
                        "snapShot": "",
                        "replicationDestination": destFilesystem,
                        "severity": "warning",
                        "errors": f"{resume_token} | {err}",
                    }
                )

        # destinationSnapshots semantics:
        # None -> dataset missing
        # []   -> exists, no snaps
        # list -> has snaps
        if destinationSnapshots is None:
            print("Destination dataset does not exist. Will create it via full receive (no -F).")
            forceOverwrite = False

        elif not destinationSnapshots:
            print("Destination exists but has no snapshots.")
            if useExistingDest and allowOverwrite:
                print("Using existing destination with overwrite: full send with -F into existing dataset.")
                forceOverwrite = True
            elif useExistingDest:
                print(
                    "Destination dataset already exists and has no snapshots.\n"
                    "ZFS requires -F for a full send into an existing dataset.\n"
                    "Enable Allow Overwrite to permit rollback, or point to a new/empty destination."
                )
                sys.exit(2)
            else:
                print("Treating destination as new dataset path. Full send (no -F).")
                forceOverwrite = False

        else:
            src_guids = {s.guid for s in sourceSnapshots}
            common_candidates = [d for d in destinationSnapshots if d.guid in src_guids]

            if not common_candidates:
                print("No common snapshots found on the destination.")
                if allowOverwrite:
                    print("ALLOW OVERWRITE enabled: proceeding with full send and -F (will roll back dest).")
                    forceOverwrite = True
                else:
                    print("Refusing to overwrite destination without a common base. Enable allowOverwrite or choose a new destination.")
                    sys.exit(2)
            else:
                # Most recent common by destination ordering
                destinationSnapshots.sort(key=lambda s: s.creation_epoch)
                common_candidates.sort(key=lambda s: s.creation_epoch, reverse=True)
                mostRecentCommonSnap = common_candidates[0]

                src_guid_to_name = {s.guid: s.name for s in sourceSnapshots}
                incrementalSnapName = src_guid_to_name[mostRecentCommonSnap.guid]
                print(f"Most recent common snapshot: {incrementalSnapName}")

                # Determine if destination is ahead of common base
                destinationSnapshots.sort(key=lambda s: s.creation_epoch)
                common_idx = -1
                for i, d in enumerate(destinationSnapshots):
                    if d.guid == mostRecentCommonSnap.guid:
                        common_idx = i
                        break

                destAhead = False
                if common_idx >= 0:
                    for d in destinationSnapshots[common_idx + 1 :]:
                        if d.guid not in src_guids:
                            destAhead = True
                            break

                if destAhead and not allowOverwrite:
                    print("Destination has newer snapshots than the common base. Enable Allow Overwrite (-F) or choose a different destination.")
                    sys.exit(2)
                if destAhead and allowOverwrite:
                    print("Destination is ahead; Allow Overwrite enabled: will roll back with -F.")
                    forceOverwrite = True

                # written@SNAP check when overwrite allowed and no newer snaps
                if (not destAhead) and allowOverwrite:
                    if direction == "pull":
                        # destination is local in pull
                        dest_root_snaps = filter_dataset_snapshots(destinationSnapshots, destFilesystem)
                        written_remote = None
                        if dest_root_snaps:
                            dest_root_snaps.sort(key=lambda s: s.order_key)
                            dest_latest = dest_root_snaps[-1]
                            written_remote = get_written_since_snapshot(destFilesystem, dest_latest.name)
                    else:
                        # destination may be remote in push
                        dest_root_snaps = filter_dataset_snapshots(destinationSnapshots, destFilesystem)
                        written_remote = None
                        if dest_root_snaps:
                            dest_root_snaps.sort(key=lambda s: s.order_key)
                            dest_latest = dest_root_snaps[-1]
                            written_remote = get_written_since_snapshot(
                                destFilesystem,
                                dest_latest.name,
                                remote_user=remoteUser if remoteHost else None,
                                remote_host=remoteHost if remoteHost else None,
                                remote_port=sshPort,
                            )

                    if written_remote is None:
                        print("Note: Could not determine written@SNAP; proceeding without forcing -F based on that.")
                    elif written_remote > 0:
                        print("Destination modified since latest snapshot; Allow Overwrite enabled: will receive with -F (rollback).")
                        forceOverwrite = True

        notifier.notify("STATUS=Creating source snapshot…")

        if direction == "pull":
            newSnap = create_snapshot_remote(
                sourceFilesystem,
                isRecursiveSnap,
                taskName,
                customName,
                remoteUser,
                remoteHost,
                sshPort,
            )
            exists, dest_snap_name = snapshot_exists_on_destination(
                destFilesystem,
                snapshot_suffix(newSnap),
                remote_user=None,
                remote_host=None,
                remote_port=sshPort,
            )
            if exists:
                msg = (
                    f"Destination already has snapshot {dest_snap_name}. "
                    "This typically means a prior receive completed or a timestamp reused. "
                    "Refusing to overwrite an existing snapshot name."
                )
                notifier.notify(f"STATUS={msg}")
                print(msg)
                sys.exit(2)
            notifier.notify("STATUS=Pulling snapshot from remote source to local target…")
            send_snapshot_pull(
                remoteSnapName=newSnap,
                localRecvFs=destFilesystem,
                remoteBaseSnapName=incrementalSnapName,
                compressed=isCompressed,
                raw=isRaw,
                remoteHost=remoteHost,
                remoteSshPort=sshPort,
                remoteUser=remoteUser,
                mBufferSize=str(mBufferSize),
                mBufferUnit=mBufferUnit,
                forceOverwrite=forceOverwrite,
                recursive=isRecursiveSnap,
            )
        else:
            newSnap = create_snapshot_local(sourceFilesystem, isRecursiveSnap, taskName, customName)
            exists, dest_snap_name = snapshot_exists_on_destination(
                destFilesystem,
                snapshot_suffix(newSnap),
                remote_user=remoteUser if remoteHost else None,
                remote_host=remoteHost if remoteHost else None,
                remote_port=sshPort,
            )
            if exists:
                msg = (
                    f"Destination already has snapshot {dest_snap_name}. "
                    "This typically means a prior receive completed or a timestamp reused. "
                    "Refusing to overwrite an existing snapshot name."
                )
                notifier.notify(f"STATUS={msg}")
                print(msg)
                sys.exit(2)
            notifier.notify("STATUS=Sending snapshot to destination…")
            send_snapshot_push(
                newSnap,
                destFilesystem,
                incrementalSnapName,
                isCompressed,
                isRaw,
                remoteHost,
                sshPort,
                remoteUser,
                str(mBufferSize),
                mBufferUnit,
                forceOverwrite,
                transferMethod,
                recursive=isRecursiveSnap,
                recvDataPort=dataPort,
            )

        notifier.notify("STATUS=Pruning old snapshots on source/destination…")
        current_pct = 0

        if direction == "pull":
            # Source retention applies to remote source; destination retention applies to local target
            current_pct = prune_snapshots_by_retention(
                sourceFilesystem,
                taskName,
                sourceRetentionTime,
                sourceRetentionUnit,
                newSnap,
                remoteUser,
                remoteHost,
                sshPort,
                transferMethod,
                progress_base=current_pct,
                progress_span=50,
            )
            current_pct = prune_snapshots_by_retention(
                destFilesystem,
                taskName,
                destinationRetentionTime,
                destinationRetentionUnit,
                newSnap,
                progress_base=current_pct,
                progress_span=50,
            )
        else:
            # Push: source local, destination maybe remote
            current_pct = prune_snapshots_by_retention(
                sourceFilesystem,
                taskName,
                sourceRetentionTime,
                sourceRetentionUnit,
                newSnap,
                progress_base=current_pct,
                progress_span=50,
            )
            current_pct = prune_snapshots_by_retention(
                destFilesystem,
                taskName,
                destinationRetentionTime,
                destinationRetentionUnit,
                newSnap,
                remoteUser if remoteHost else None,
                remoteHost if remoteHost else None,
                sshPort,
                transferMethod,
                progress_base=current_pct,
                progress_span=50,
            )

        final_pct = min(100, int(current_pct))
        notifier.notify(f"STATUS=ZFS replication task completed. {final_pct}% complete")

    except Exception as e:
        newSnap = locals().get("newSnap", "unknown")
        srcPool = os.environ.get("zfsRepConfig_sourceDataset_pool", "")
        srcDs = os.environ.get("zfsRepConfig_sourceDataset_dataset", "")
        dstPool = os.environ.get("zfsRepConfig_destDataset_pool", "")
        dstDs = os.environ.get("zfsRepConfig_destDataset_dataset", "")
        sourceFilesystem = join_zfs_path(srcPool, srcDs)
        receivingFilesystem = join_zfs_path(dstPool, dstDs)
        try:
            resume_token = get_receive_resume_token(
                receivingFilesystem,
                remote_user=remoteUser if "remoteUser" in locals() and remoteHost else None,
                remote_host=remoteHost if "remoteHost" in locals() else None,
                remote_port=sshPort if "sshPort" in locals() else "22",
            )
            print(f"receive_resume_token for {receivingFilesystem}: {resume_token or '-'}")
        except Exception:
            print(f"receive_resume_token for {receivingFilesystem}: <error fetching token>")

        tb = traceback.format_exc()
        safe_print(tb)
        notifier.notify("STATUS=ZFS replication task failed.")
        email_error_message = (
            f"ZFS replication failed while sending snapshot {newSnap} "
            f"from {sourceFilesystem} to {receivingFilesystem}"
            f"Error: {str(e)}"
        )

        send_houston_notification(
            {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event": "zfs_replication_failed",
                "subject": "ZFS Replication Failed",
                "email_message": email_error_message,
                "fileSystem": sourceFilesystem,
                "snapShot": newSnap,
                "replicationDestination": receivingFilesystem,
                "severity": "warning",
                "errors": str(e),
            }
        )
        print(f"Exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
