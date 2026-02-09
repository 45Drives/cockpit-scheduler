import subprocess
import sys
import datetime
import os
import time
import json
import shlex
import getpass
from notify import get_notifier

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
    ssh_cmd = ssh_base_args(user, host, ssh_port)
    ssh_cmd.extend(
        [
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
    )

    try:
        output = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT)
        snapshots = []
        for line in output.decode(errors="replace").splitlines():
            snap = parse_snapshot_line(line)
            if snap:
                snapshots.append(snap)
        return snapshots

    except subprocess.CalledProcessError as e:
        err_output = e.output.decode(errors="replace").lower()
        if "dataset does not exist" in err_output or "cannot open" in err_output:
            return None
        print(f"ERROR: Failed to fetch remote snapshots for {filesystem}: {e}\nOutput:\n{err_output}")
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


def get_written_since_snapshot(dataset, snapshot_fullname, remote_user=None, remote_host=None, remote_port=22):
    prop = f"written@{snapshot_fullname}"
    base_cmd = ["zfs", "get", "-H", "-p", "-o", "value", prop, dataset]

    if remote_host:
        cmd = ssh_base_args(remote_user, remote_host, remote_port) + base_cmd
    else:
        cmd = base_cmd

    p = subprocess.run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        return None

    out = (p.stdout or "").strip()
    if not out or out == "-":
        return None

    try:
        return int(out)
    except ValueError:
        return None


def create_snapshot_local(filesystem, is_recursive, task_name, custom_name=None):
    command = ["zfs", "snapshot"]
    if is_recursive:
        command.append("-r")
    timestamp = datetime.datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
    new_snap = f"{filesystem}@{(custom_name + '-') if custom_name else ''}{task_name}-{timestamp}"
    command.append(new_snap)

    notifier.notify(f"STATUS=Creating snapshot {new_snap}…")
    try:
        subprocess.run(command, check=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        msg = ((e.stderr or "") + "\n" + (e.stdout or "")).lower()
        if "dataset already exists" in msg:
            print(f"Snapshot already exists ({new_snap}) — likely a queued duplicate start; exiting successfully.")
            notifier.notify(f"STATUS=Snapshot {new_snap} already exists; treating as completed.")
            sys.exit(0)
        notifier.notify(f"STATUS=Snapshot creation failed: {msg}")
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

    ssh_cmd = ssh_base_args(remote_user, remote_host, ssh_port) + cmd
    p = subprocess.run(ssh_cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if p.returncode != 0:
        msg = ((p.stderr or "") + "\n" + (p.stdout or "")).lower()
        if "dataset already exists" in msg:
            print(f"Remote snapshot already exists ({new_snap}) — likely a queued duplicate start; exiting successfully.")
            notifier.notify(f"STATUS=Remote snapshot {new_snap} already exists; treating as completed.")
            sys.exit(0)
        notifier.notify(f"STATUS=Remote snapshot creation failed: {msg}")
        raise subprocess.CalledProcessError(p.returncode, ssh_cmd, output=p.stdout, stderr=p.stderr)

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
            ssh_cmd = ["ssh"]
            if transferMethod == "ssh" and str(remote_port) != "22":
                ssh_cmd.extend(["-p", str(remote_port)])
            ssh_cmd.append(f"{remote_user}@{remote_host}")
            delete_command = ssh_cmd + ["zfs", "destroy", snapshot.name]
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

    process_send = subprocess.Popen(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if transferMethod == "local" or not recvHost:
        recv_cmd = ["zfs", "recv"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(recvName)

        process_recv = subprocess.Popen(
            recv_cmd,
            stdin=process_send.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process_recv.communicate()
        if process_recv.returncode != 0:
            notifier.notify("STATUS=Local receive failed.")
            print(f"recv error: {stderr}")
            sys.exit(1)
        notifier.notify("STATUS=Local receive completed.")
        if stdout:
            print(stdout)
        return

    if transferMethod == "ssh":
        notifier.notify(f"STATUS=Sending snapshot {sendName} to {recvHostUser}@{recvHost}:{recvName} via ssh…")

        m_buff_cmd = ["mbuffer", "-s", "256k", "-m", str(mBufferSize) + mBufferUnit]
        process_m_buff = subprocess.Popen(
            m_buff_cmd,
            stdin=process_send.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        ssh_cmd = ["ssh"]
        if str(recvSshPort) != "22":
            ssh_cmd.extend(["-p", str(recvSshPort)])
        ssh_cmd.append(f"{recvHostUser}@{recvHost}")

        recv_q = shlex.quote(recvName)
        flags = "-F" if forceOverwrite else ""
        ssh_cmd.append(f"zfs recv {flags} {recv_q}")

        process_remote_recv = subprocess.Popen(
            ssh_cmd,
            stdin=process_m_buff.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process_remote_recv.communicate()
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
        listen_cmd = f"nc -l {shlex.quote(data_port)} | zfs recv {'-F ' if forceOverwrite else ''}{recv_q}"
        ssh_cmd_listener = ssh_base_args(recvHostUser, recvHost, ssh_port)
        ssh_cmd_listener.append(listen_cmd)

        ssh_process_listener = subprocess.Popen(
            ssh_cmd_listener,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        time.sleep(2)

        send_cmd_list = build_zfs_send_args(
            sendName,
            sendName2,
            recursive=recursive,
            compressed=compressed,
            raw=raw,
        )
        mbuffer_cmd = ["mbuffer", "-s", "256k", "-m", f"{mBufferSize}{mBufferUnit}"]
        nc_cmd = ["nc", recvHost, data_port]

        process_send2 = subprocess.Popen(send_cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process_mbuffer = subprocess.Popen(
            mbuffer_cmd,
            stdin=process_send2.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process_nc = subprocess.Popen(nc_cmd, stdin=process_mbuffer.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        _, nc_stderr = process_nc.communicate()

        send_stderr = process_send2.stderr.read().decode(errors="replace") if process_send2.stderr else ""
        mbuf_stderr = process_mbuffer.stderr.read().decode(errors="replace") if process_mbuffer.stderr else ""

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat send failed.")
            print(f"[Sender Side] nc error: {nc_stderr.decode(errors='replace')}")
            if mbuf_stderr:
                print(f"[Sender Side] mbuffer error: {mbuf_stderr}")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            ssh_process_listener.terminate()
            sys.exit(1)

        ssh_stdout, ssh_stderr = ssh_process_listener.communicate(timeout=300)
        if ssh_process_listener.returncode != 0:
            notifier.notify("STATUS=Remote receive via netcat failed.")
            print(f"[Receiver Side] Error during receive: {ssh_stderr.strip()}")
            sys.exit(1)

        notifier.notify("STATUS=Netcat send/receive completed.")

        snapshot_check_cmd = ssh_base_args(recvHostUser, recvHost, ssh_port)
        snapshot_check_cmd.extend(["zfs", "list", recvName])
        snapshot_process = subprocess.run(
            snapshot_check_cmd,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if snapshot_process.returncode != 0:
            print(f"[Receiver Side] Error checking dataset: {snapshot_process.stderr.strip()}")
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
    """
    Pull mode: run zfs send on remote source, stream to local zfs recv.
    Note: if transferMethod was 'netcat', this test implementation still uses SSH for the data path.
    """
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
    ssh_send_cmd = ssh_base_args(remoteUser, remoteHost, remoteSshPort) + remote_send_args

    if remoteBaseSnapName:
        print(f"pulling incrementally from {remoteBaseSnapName} -> {remoteSnapName} into {localRecvFs}")
    else:
        print(f"pulling {remoteSnapName} into {localRecvFs}")

    process_remote_send = subprocess.Popen(
        ssh_send_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    m_buff_cmd = ["mbuffer", "-s", "256k", "-m", str(mBufferSize) + mBufferUnit]
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=process_remote_send.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    recv_cmd = ["zfs", "recv"]
    if forceOverwrite:
        recv_cmd.append("-F")
    recv_cmd.append(localRecvFs)

    process_local_recv = subprocess.Popen(
        recv_cmd,
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    stdout, stderr = process_local_recv.communicate()
    if process_local_recv.returncode != 0:
        notifier.notify("STATUS=Local receive (pull) failed.")
        print(f"ERROR: local recv error: {stderr}")

        remote_err = process_remote_send.stderr.read().decode(errors="replace") if process_remote_send.stderr else ""
        mbuf_err = process_m_buff.stderr.read().decode(errors="replace") if process_m_buff.stderr else ""
        if remote_err:
            print(f"[Remote zfs send stderr]\n{remote_err}")
        if mbuf_err:
            print(f"[mbuffer stderr]\n{mbuf_err}")

        sys.exit(1)

    notifier.notify("STATUS=Pull receive completed.")
    if stdout:
        print(stdout)

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

            # print("EUID:", os.geteuid(), "USER:", getpass.getuser(), "HOME:", os.environ.get("HOME"))
            # subprocess.run(["ssh", "-V"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            # cmd = [
            #     "ssh",
            #     "-o", "BatchMode=yes",
            #     "-o", "IdentitiesOnly=yes",
            #     "-o", "ConnectTimeout=10",
            #     "-vv",
            #     f"{remoteUser}@{remoteHost}",
            #     "true",
            # ]
            # p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            # print(p.stdout)
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
