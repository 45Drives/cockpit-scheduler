import subprocess
import sys
import datetime
import os
import time
import json
from notify import get_notifier

notifier = get_notifier()

class Snapshot:
	def __init__(self, name, guid, creation):
		self.name = name
		self.guid = guid
		self.creation = creation
def send_houston_notification(payload):
    try:
        dbus_script = "/opt/45drives/houston/houston-notify"
        debug_log = "/tmp/zfs_replication_debug.log"
        subprocess.run([
            "python3",
            dbus_script,
            json.dumps(payload)
        ], stdout=open(debug_log, "a"), stderr=subprocess.STDOUT)
    except Exception as notify_error:
        print(f"Failed to send D-Bus notification: {notify_error}")

# 	return new_snap
def create_snapshot(filesystem, is_recursive, task_name, custom_name=None):
    command = ['zfs', 'snapshot']
    if is_recursive:
        command.append('-r')
    timestamp = datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')
    new_snap = f'{filesystem}@{(custom_name+"-") if custom_name else ""}{task_name}-{timestamp}'
    command.append(new_snap)

    notifier.notify(f"STATUS=Creating snapshot {new_snap}…")
    try:
        subprocess.run(command, check=True, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").lower()
        if "dataset already exists" in msg:
            print(f"Snapshot already exists ({new_snap}) — likely a queued duplicate start; exiting successfully.")
            notifier.notify(f"STATUS=Snapshot {new_snap} already exists; treating as completed.")
            sys.exit(0)
        notifier.notify(f"STATUS=Snapshot creation failed: {msg}")
        raise

    print(f"new snapshot created: {new_snap}")
    notifier.notify(f"STATUS=Snapshot created: {new_snap}")
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
    transferMethod='ssh',
    progress_base=0,
    progress_span=100,
):
    """
    Prune snapshots according to retention settings, and report progress
    as a monotonic percentage segment:

      - progress_base: starting percentage for this phase (0–100)
      - progress_span: how many percentage points this phase may consume

    The function returns the final percentage reached, so the caller can
    chain phases without ever going backwards.
    """
    # Determine whether to fetch snapshots locally or remotely
    if remote_host:
        snapshots = get_remote_snapshots(remote_user, remote_host, remote_port, filesystem, transferMethod)
        # If None is returned, that means the dataset doesn't exist at all; no pruning needed
        if snapshots is None:
            print(f"Remote dataset {filesystem} does not exist. Nothing to prune.")
            msg = f"Remote dataset {filesystem} does not exist. Nothing to prune."
            # Advance to the end of this phase anyway
            final_pct = min(100, int(progress_base) + int(progress_span))
            notifier.notify(f"STATUS={msg} {final_pct}% complete")
            return final_pct
    else:
        snapshots = get_local_snapshots(filesystem)

    if snapshots is None:
        msg = f"{'Remote ' if remote_host else ''}dataset {filesystem} does not exist. Nothing to prune."
        print(msg)
        final_pct = min(100, int(progress_base) + int(progress_span))
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    now = datetime.datetime.now()

    # Define unit multipliers for retention calculation
    unit_multipliers = {
        "minutes": 60 * 1000,
        "hours":   60 * 60 * 1000,
        "days":    24 * 60 * 60 * 1000,
        "weeks":   7 * 24 * 60 * 60 * 1000,
        "months":  30 * 24 * 60 * 60 * 1000,
        "years":   365 * 24 * 60 * 60 * 1000,
    }

    # Normalize retention_time to an int, with 0 as fallback
    try:
        retention_val = int(retention_time)
    except (TypeError, ValueError):
        retention_val = 0

    # Case 1: retention explicitly disabled -> no pruning, but we still advance progress
    if (retention_val == 0) and (not retention_unit):
        msg = "Retention not configured. No pruning will be performed."
        print(msg)
        final_pct = min(100, int(progress_base) + int(progress_span))
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    # Case 2: bad unit or non-positive value -> invalid config
    if retention_val <= 0 or retention_unit not in unit_multipliers:
        msg = f"Retention period is not valid (time={retention_time}, unit='{retention_unit}'). No pruning will be performed."
        print(msg)
        final_pct = min(100, int(progress_base) + int(progress_span))
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    multiplier = unit_multipliers[retention_unit]
    retention_milliseconds = retention_val * multiplier

    snapshots_to_delete = []

    excluded_suffix = excluded_snapshot_name.split('@', 1)[-1] if excluded_snapshot_name else None

    for snapshot in snapshots:
        # Only prune snapshots created by this task, excluding the one we just made
        if task_name in snapshot.name:
            snap_suffix = snapshot.name.split('@', 1)[-1] if '@' in snapshot.name else snapshot.name
            if excluded_suffix and snap_suffix == excluded_suffix:
                continue  # skip the newest one
            creation_time = snapshot.creation
            age_milliseconds = (now - creation_time).total_seconds() * 1000
            if age_milliseconds > retention_milliseconds:
                snapshots_to_delete.append(snapshot)

    # Normalise progress segment
    start = max(0, min(100, int(progress_base)))
    span = max(0, min(100 - start, int(progress_span)))

    prefix = "remote " if remote_host else ""

    if not snapshots_to_delete:
        msg = "No snapshots to prune."
        print(msg)
        final_pct = min(100, start + span)
        notifier.notify(f"STATUS={msg} {final_pct}% complete")
        return final_pct

    total = len(snapshots_to_delete)
    notifier.notify(f"STATUS=Pruning {total} {prefix}snapshot(s)… {start}% complete")

    for idx, snapshot in enumerate(snapshots_to_delete, start=1):
        # Build the delete command
        if remote_host:
            ssh_cmd = ['ssh']
            if transferMethod == 'ssh' and str(remote_port) != '22':
                ssh_cmd.extend(['-p', str(remote_port)])

            ssh_cmd.append(f"{remote_user}@{remote_host}")
            delete_command = ssh_cmd + ["zfs", "destroy", snapshot.name]
        else:
            delete_command = ['zfs', 'destroy', snapshot.name]

        try:
            subprocess.run(delete_command, check=True)
            print(f"Deleted snapshot: {snapshot.name}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to delete snapshot {snapshot.name}: {e}")
            notifier.notify(f"STATUS=Failed to delete snapshot {snapshot.name}")
            # We still keep progress monotonic; just abort the task
            sys.exit(1)

        pct = start + int(idx * span / total)
        notifier.notify(f"STATUS=Pruning {total} {prefix}snapshot(s)… {pct}% complete")

    msg = f"Pruned {len(snapshots_to_delete)} snapshots older than retention period ({retention_val} {retention_unit})."
    print(msg)
    final_pct = min(100, start + span)
    notifier.notify(f"STATUS={msg} {final_pct}% complete")
    return final_pct

def get_local_snapshots(filesystem):
    # cmd = ['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem]
    cmd = ['zfs', 'list', '-H', '-p', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem]
    p = subprocess.run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode == 0:
        snaps = []
        for line in (p.stdout or "").splitlines():
            parts = line.split(maxsplit=2)
            if len(parts) >= 3:
                try:
                    # created = datetime.datetime.strptime(parts[2], "%a %b %d %H:%M %Y")
                    created = datetime.datetime.fromtimestamp(int(parts[2]))
                except ValueError:
                    continue
                snaps.append(Snapshot(parts[0], parts[1], created))
        return snaps
    # Non-zero: detect “does not exist” and return None, else raise
    err = (p.stderr or p.stdout or "").lower()
    if "dataset does not exist" in err or "cannot open" in err:
        return None
    raise subprocess.CalledProcessError(p.returncode, cmd, output=p.stdout, stderr=p.stderr)


def get_remote_snapshots(user, host, port, filesystem, transferMethod):
	"""
	Returns:
	  - A list of Snapshot objects if the remote dataset exists.
	  - An empty list [] if the dataset exists but has no snapshots.
	  - None if the dataset does not exist at all.
	"""
 
	ssh_cmd = ssh_base_args(user, host, port)

	ssh_cmd.extend(['zfs', 'list', '-H', '-p', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem])

	try:
		output = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT)
		snapshots = []
		for line in output.decode().splitlines():
			parts = line.split(maxsplit=2)
			if len(parts) >= 3:
				snapshot_name = parts[0]
				snapshot_guid = parts[1]
				try:
					snapshot_creation = datetime.datetime.fromtimestamp(int(parts[2]))
				except ValueError:
					continue  # Skip if parsing fails
				snapshots.append(Snapshot(snapshot_name, snapshot_guid, snapshot_creation))
		return snapshots

	except subprocess.CalledProcessError as e:
		err_output = e.output.decode(errors='replace').lower()
		if "dataset does not exist" in err_output or "cannot open" in err_output:
			return None  # Dataset does not exist
		else:
			print(f"ERROR: Failed to fetch remote snapshots for {filesystem}: {e}\nOutput:\n{err_output}")
			sys.exit(1)

	except Exception as e:
		print(f"An unexpected error occurred: {e}")
		sys.exit(1)


def get_most_recent_snapshot(snapshots):
	if snapshots:
		snapshots.sort(key=lambda x: x.creation, reverse=True)
		return snapshots[0]
	else:
		return None

def build_zfs_send_args(sendName, sendName2, *, recursive, compressed, raw):
    args = ['zfs', 'send']
    if recursive:
        args.append('-R')
    if compressed:
        args.append('-Lce')
    if raw:
        args.append('-w')
    if sendName2:
        args.extend(['-I' if recursive else '-i', sendName2])
    args.append(sendName)
    return args

def ssh_base_args(user, host, port):
    args = ['ssh']
    if str(port) != '22':
        args.extend(['-p', str(port)])
    args.append(f'{user}@{host}')
    return args

def send_snapshot(
	sendName, 
	recvName, 
	sendName2="", 
	compressed=False, 
	raw=False, 
	recvHost="", 
	recvPort='22', 
	recvHostUser="", 
	mBufferSize=1, 
	mBufferUnit="G", 
	forceOverwrite=False,
	transferMethod="",
 	recursive=False, 
):
	try:
		notifier.notify("STATUS=Preparing ZFS send/recv pipeline…")
		send_cmd = build_zfs_send_args( sendName, sendName2,
			recursive=recursive,
			compressed=compressed,
			raw=raw
   		)

		if sendName2 != "":
			print(f"sending incrementally from {sendName2} -> {sendName} to {recvName}")
		else:
			print(f"sending {sendName} to {recvName}")

		process_send = subprocess.Popen(
			send_cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
		)

		print("send_cmd:", send_cmd)
		# If sending locally
		if transferMethod == "local":
			recv_cmd = ['zfs', 'recv']
			if forceOverwrite:
				recv_cmd.append('-F')
			recv_cmd.append(recvName)
			print("recv_cmd:", recv_cmd)

			print(f"receiving {sendName} in {recvName}")
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
			else:
				notifier.notify("STATUS=Local receive completed.")
				print(stdout)
			print(f"received local send")

		# If sending remotely via ssh
		elif transferMethod == "ssh":
			print("sending via ssh")
			notifier.notify(f"STATUS=Sending snapshot {sendName} to {recvHostUser}@{recvHost}:{recvName} via ssh…")
			m_buff_cmd = ['mbuffer', '-s', '256k', '-m', str(mBufferSize) + mBufferUnit]
			process_m_buff = subprocess.Popen(
				m_buff_cmd,
				stdin=process_send.stdout,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				universal_newlines=True,
			)

			ssh_cmd = ['ssh']
			if str(recvPort) != '22':
				ssh_cmd.extend(['-p', str(recvPort)])

			ssh_cmd.append(recvHostUser + '@' + recvHost)
			ssh_cmd.extend(['zfs', 'recv'])

			if forceOverwrite:
				ssh_cmd.append('-F')
			ssh_cmd.append(recvName)

			print(f"receiving {sendName} in {recvName} via {recvHostUser}@{recvHost}:{recvPort}")
			print(f"ssh command: {ssh_cmd}")

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
			else:
				notifier.notify("STATUS=Remote receive completed.")
				print(stdout)
			print(f"received remote send")

		elif transferMethod == "netcat":
			try:
				notifier.notify(f"STATUS=Sending snapshot {sendName} via netcat to {recvHostUser}@{recvHost}:{recvPort}…")
				print("Sending via netcat...")
				
				# Correct listener command
				listen_cmd = f"nc -l {recvPort} | zfs recv {'-F ' + recvName if forceOverwrite else recvName}"
				ssh_cmd_listener = ssh_base_args(recvHostUser, recvHost, recvPort)  # control-plane port
				ssh_cmd_listener.append(listen_cmd)
				print(f"[Receiver Side] Listener command: {' '.join(ssh_cmd_listener)}")

				ssh_process_listener = subprocess.Popen(
					ssh_cmd_listener,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					universal_newlines=True,
				)

				# Wait briefly to ensure listener readiness
				time.sleep(5)
    
				send_cmd_list = build_zfs_send_args(
					sendName, sendName2,
					recursive=recursive,
					compressed=compressed,
					raw=raw,
				)

				print(f"[Sender Side] ZFS send command: {' '.join(send_cmd_list)}")

				# Combine send -> mbuffer -> netcat pipeline
				# nc_command = f"{' '.join(send_cmd_list)} | {' '.join(m_buff_cmd)} | nc {recvHost} {recvPort}"
				nc_command = f"{' '.join(send_cmd_list)} | mbuffer -s 256k -m {mBufferSize}{mBufferUnit} | nc {recvHost} {recvPort}"
				print(f"[Sender Side] Netcat command: {nc_command}")

				nc_process = subprocess.Popen(
					nc_command,
					shell=True,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
				)
				nc_stdout, nc_stderr = nc_process.communicate()

				if nc_process.returncode != 0:
					notifier.notify("STATUS=Netcat send failed.")
					print(f"[Sender Side] nc error: {nc_stderr.decode()}")
					ssh_process_listener.terminate()
					sys.exit(1)

				print("[Sender Side] Successfully sent data via netcat.")

				# Ensure receiver completed successfully
				ssh_stdout, ssh_stderr = ssh_process_listener.communicate(timeout=300)
				if ssh_process_listener.returncode != 0:
					notifier.notify("STATUS=Remote receive via netcat failed.")
					print(f"[Receiver Side] Error during receive: {ssh_stderr.strip()}")
					sys.exit(1)
     
				notifier.notify("STATUS=Netcat send/receive completed.")
    
				# Verify dataset on receiver
				snapshot_check_cmd = ['ssh', f'{recvHostUser}@{recvHost}', f'zfs list {recvName}']
				snapshot_process = subprocess.run(snapshot_check_cmd, universal_newlines=True, stdout=subprocess.PIPE)

				if snapshot_process.returncode != 0:
					print(f"[Receiver Side] Error checking dataset: {snapshot_process.stderr.strip()}")
					sys.exit(1)

				print(f"[Receiver Side] Received dataset exists: {snapshot_process.stdout.strip()}")
	
			except subprocess.TimeoutExpired:
				print("[Receiver Side] Receiver timed out.")
				ssh_process_listener.terminate()
				sys.exit(1)

			except subprocess.CalledProcessError as e:
				print(f"Error: {e.stderr}")
				ssh_process_listener.terminate()
				sys.exit(1)

		else:
			print("ERROR: Invalid transferMethod specified. Must be 'local', 'ssh', or 'netcat'.")
			sys.exit(1)

	except Exception as e:
		notifier.notify(f"STATUS=Send error: {e}")
		print(f"ERROR: Send error: {e}")
		sys.exit(1)

def join_zfs_path(pool: str, dataset: str) -> str:
	pool = (pool or "").strip()
	ds = (dataset or "").strip()
	if not pool:         # remote-only path or user passed full name in dataset
		return ds
	if not ds:
		return pool
	# If dataset already includes the pool prefix, keep it
	if ds == pool or ds.startswith(pool + "/"):
		return ds
	# If dataset looks like a full path but with the same pool, keep it
	first = ds.split("/", 1)[0]
	if first == pool:
		return ds
	return f"{pool}/{ds}"


def main():
	try:
		notifier.notify("STATUS=Starting ZFS replication task…")
		notifier.notify("READY=1")
		notifier.notify("STATUS=Planning replication…")
		# ---------- helpers ----------
		def as_bool(v, default=False):
			if v is None:
				return default
			return str(v).strip().lower() in ('1', 'true', 'yes', 'on')

		# ---------- params ----------
		sourceFilesystem = os.environ.get('zfsRepConfig_sourceDataset_dataset', '')

		isRecursiveSnap = as_bool(os.environ.get('zfsRepConfig_sendOptions_recursive_flag'))
		customName = os.environ.get('zfsRepConfig_sendOptions_customName', '')

		isRaw = as_bool(os.environ.get('zfsRepConfig_sendOptions_raw_flag'))
		isCompressed = as_bool(os.environ.get('zfsRepConfig_sendOptions_compressed_flag'))

		destinationRoot = os.environ.get('zfsRepConfig_destDataset_pool', '')
		destinationPath = os.environ.get('zfsRepConfig_destDataset_dataset', '')
		receivingFilesystem = join_zfs_path(destinationRoot, destinationPath)

		remoteUser = os.environ.get('zfsRepConfig_destDataset_user', 'root')
		remoteHost = os.environ.get('zfsRepConfig_destDataset_host', '')
		remotePort = os.environ.get('zfsRepConfig_destDataset_port', '22')  # keep as string for ssh -p comparisons

		mBufferSize = os.environ.get('zfsRepConfig_sendOptions_mbufferSize', '1')
		mBufferUnit = os.environ.get('zfsRepConfig_sendOptions_mbufferUnit', 'G')

		sourceRetentionTime = os.environ.get('zfsRepConfig_snapshotRetention_source_retentionTime', 0)
		sourceRetentionUnit = os.environ.get('zfsRepConfig_snapshotRetention_source_retentionUnit', '')

		destinationRetentionTime = os.environ.get('zfsRepConfig_snapshotRetention_destination_retentionTime', 0)
		destinationRetentionUnit = os.environ.get('zfsRepConfig_snapshotRetention_destination_retentionUnit', '')

		transferMethod = os.environ.get('zfsRepConfig_sendOptions_transferMethod', '')
		allowOverwrite = as_bool(os.environ.get('zfsRepConfig_sendOptions_allowOverwrite'), default=False)
		useExistingDest = as_bool(os.environ.get('zfsRepConfig_sendOptions_useExistingDest'), default=False)

		taskName = os.environ.get('taskName', '')

		# ---------- initial state ----------
		forceOverwrite = False
		# receivingFilesystem = f"{destinationPath}"  # or f"{destinationRoot}/{destinationPath}" if you prefer
		incrementalSnapName = ""

		# ---------- fetch snapshots ----------
		sourceSnapshots = get_local_snapshots(sourceFilesystem) or []
		sourceSnapshots.sort(key=lambda x: x.creation)

		if remoteHost and remoteUser:
			destinationSnapshots = get_remote_snapshots(
				remoteUser, remoteHost, remotePort, receivingFilesystem, transferMethod
			)
		else:
			destinationSnapshots = get_local_snapshots(receivingFilesystem)

		# destinationSnapshots is:
		#   None        -> dataset missing
		#   []          -> dataset exists, no snapshots
		#   [ZfsSnap...] -> has snapshots
		if destinationSnapshots is None:
			print(f"Destination {receivingFilesystem} does not exist. Will create it via full send (no -F).")
			forceOverwrite = False

		elif not destinationSnapshots:
			print(f"Destination {receivingFilesystem} exists but has no snapshots.")
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
				print("Treating destination as new dataset path under the pool. Full send (no -F).")
				forceOverwrite = False

		else:
			source_guids = {s.guid: s.name for s in sourceSnapshots}
			common = [d for d in destinationSnapshots if d.guid in source_guids]

			if not common:
				print("No common snapshots found on the destination.")
				if allowOverwrite:
					print("ALLOW OVERWRITE is enabled: proceeding with full send and -F (will roll back dest).")
					forceOverwrite = True
				else:
					print(
						"Refusing to overwrite destination without a common base. "
						"Enable allowOverwrite or choose/create an empty destination."
					)
					sys.exit(2)
			else:
				common.sort(key=lambda x: x.creation, reverse=True)
				mostRecentCommonSnap = common[0]
				incrementalSnapName = source_guids[mostRecentCommonSnap.guid]
				print(f"Most recent common snapshot: {incrementalSnapName}")

				# detect destination-ahead/divergence
				src_guids = {s.guid for s in sourceSnapshots}
				base_creation = mostRecentCommonSnap.creation
				destAhead = any(
					(d.creation > base_creation) and (d.guid not in src_guids)
					for d in destinationSnapshots
				)

				if destAhead and not allowOverwrite:
					print(
						"Destination has newer snapshots than the common base. "
						"Enable Allow Overwrite (-F) or choose a different destination."
					)
					sys.exit(2)
				elif destAhead and allowOverwrite:
					print("Destination is ahead; Allow Overwrite enabled: will roll back with -F.")
					forceOverwrite = True
				# else: normal incremental is fine

		notifier.notify("STATUS=Creating source snapshot…")	
		# ---------- create a fresh source snapshot to send ----------
		newSnap = create_snapshot(sourceFilesystem, isRecursiveSnap, taskName, customName)

		# ---------- send (full or incremental) ----------
		notifier.notify("STATUS=Sending snapshot to destination…")
		send_snapshot(
			newSnap,
			receivingFilesystem,
			incrementalSnapName,
			isCompressed,
			isRaw,
			remoteHost,
			remotePort,
			remoteUser,
			str(mBufferSize),
			mBufferUnit,
			forceOverwrite,
			transferMethod,
			recursive=isRecursiveSnap, 
		)

		notifier.notify("STATUS=Pruning old snapshots on source/destination…")

		# Start at 0% for pruning phases
		current_pct = 0

		# Source prune: 0 → 50
		current_pct = prune_snapshots_by_retention(
			sourceFilesystem,
			taskName,
			sourceRetentionTime,
			sourceRetentionUnit,
			newSnap,
			progress_base=current_pct,
			progress_span=50,
		)

		# Destination prune: 50 → 100
		current_pct = prune_snapshots_by_retention(
			receivingFilesystem,
			taskName,
			destinationRetentionTime,
			destinationRetentionUnit,
			newSnap,
			remoteUser,
			remoteHost,
			remotePort,
			transferMethod,
			progress_base=current_pct,
			progress_span=50,
		)

		# Final completion status (should be 100%)
		final_pct = min(100, int(current_pct))
		notifier.notify(f"STATUS=ZFS replication task completed. {final_pct}% complete")

	except Exception as e:
		newSnap = locals().get("newSnap", "unknown")
		sourceFilesystem = os.environ.get('zfsRepConfig_sourceDataset_dataset', '')
		receivingFilesystem = os.environ.get('zfsRepConfig_destDataset_dataset', '')
		notifier.notify("STATUS=ZFS replication task failed.")
		email_error_message = (
			f"ZFS replication failed while sending snapshot {newSnap} "
			f"from {sourceFilesystem} to {receivingFilesystem}"
			f"Error: {str(e)}"
		)
		ui_error_message = str(e)

		send_houston_notification({
			"timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			"event": "zfs_replication_failed",
			"subject": "ZFS Replication Failed",
			"email_message": email_error_message,
			"fileSystem": sourceFilesystem,
			"snapShot": newSnap,
			"replicationDestination": receivingFilesystem,
			"severity": "warning",
			"errors": ui_error_message
		})
		print(f"Exception: {e}")
		sys.exit(1)


if __name__ == "__main__":
	main()
