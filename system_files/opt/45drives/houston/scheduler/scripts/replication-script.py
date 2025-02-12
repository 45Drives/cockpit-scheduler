import subprocess
import sys
import datetime
import os
import time

class Snapshot:
	def __init__(self, name, guid, creation):
		self.name = name
		self.guid = guid
		self.creation = creation
	 
def create_snapshot(filesystem, is_recursive, task_name, custom_name=None):
	command = [ 'zfs', 'snapshot' ]
	if is_recursive:
		command.append('-r')
	timestamp = datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')
	if custom_name:
		new_snap = (f'{filesystem}@{custom_name}-{task_name}-{timestamp}')
	else:
		new_snap = (f'{filesystem}@{task_name}-{timestamp}')
	command.append(new_snap)
	subprocess.run(command, check=True)
	print(f"new snapshot created: {new_snap}")

	return new_snap


def prune_snapshots_by_retention(
	filesystem, task_name, retention_time, retention_unit, 
	excluded_snapshot_name, remote_user=None, remote_host=None, remote_port=22
):
	# Determine whether to fetch snapshots locally or remotely
	if remote_host :
		snapshots = get_remote_snapshots(remote_user, remote_host, remote_port, filesystem)
		# If None is returned, that means the dataset doesn't exist at all; no pruning needed
		if snapshots is None:
			print(f"Remote dataset {filesystem} does not exist. Nothing to prune.")
			return
	else:
		snapshots = get_local_snapshots(filesystem)

	now = datetime.datetime.now()

	# Define unit multipliers for retention calculation
	unit_multipliers = {
	  	"minutes": 60 * 1000,
		"hours": 60 * 60 * 1000,
		"days": 24 * 60 * 60 * 1000,
		"weeks": 7 * 24 * 60 * 60 * 1000,
		"months": 30 * 24 * 60 * 60 * 1000,
		"years": 365 * 24 * 60 * 60 * 1000
	}

	multiplier = unit_multipliers.get(retention_unit, 0)
 
	retention_milliseconds = int(retention_time) * multiplier
	if retention_milliseconds == 0:
		print("Retention period is not valid. No pruning will be performed.")
	else:
		snapshots_to_delete = []
		for snapshot in snapshots:
			print(f"Excluded snap: {excluded_snapshot_name}")
   
			# Exclude the newest snapshot we just made
			if task_name in snapshot.name and snapshot.name != excluded_snapshot_name:
				creation_time = snapshot.creation
				age_milliseconds = (now - creation_time).total_seconds() * 1000
				if age_milliseconds > retention_milliseconds:
					snapshots_to_delete.append(snapshot)

		for snapshot in snapshots_to_delete:
			# Build the delete command
			if remote_host:
				delete_command = [
					"ssh",
					f"{remote_user}@{remote_host}",
					"-p", str(remote_port),
					"zfs", "destroy", snapshot.name
				]
			else:
				delete_command = ['zfs', 'destroy', snapshot.name]

			try:
				subprocess.run(delete_command, check=True)
				print(f"Deleted snapshot: {snapshot.name}")
			except subprocess.CalledProcessError as e:
				print(f"Failed to delete snapshot {snapshot.name}: {e}")
				sys.exit(1)

		if snapshots_to_delete:
			print(f"Pruned {len(snapshots_to_delete)} snapshots older than retention period ({retention_time} {retention_unit}).")
		else:
			print("No snapshots to prune.")



def get_local_snapshots(filesystem):
	command = ['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem]
	try:
		output = subprocess.check_output(command)
		snapshots = []
		for line in output.decode().splitlines():
			parts = line.split(maxsplit=2)  # name, guid, creation
			if len(parts) >= 3:
				snapshot_name = parts[0]
				snapshot_guid = parts[1]
				snapshot_creation = datetime.datetime.strptime(parts[2], "%a %b %d %H:%M %Y")
				snapshots.append(Snapshot(snapshot_name, snapshot_guid, snapshot_creation))
		return snapshots
	except subprocess.CalledProcessError as e:
		print(f"ERROR: Failed to fetch local snapshots for {filesystem}: {e}")
		return []


def get_remote_snapshots(user, host, port, filesystem):
	"""
	Returns:
	  - A list of Snapshot objects if the remote dataset exists.
	  - An empty list [] if the dataset exists but has no snapshots.
	  - None if the dataset does not exist at all.
	"""
	ssh_cmd = ['ssh']
	# Only add '-p' if port is not the default '22'
	if str(port) != '22':
		ssh_cmd.extend(['-p', str(port)])
	ssh_cmd.append(user + '@' + host)

	ssh_cmd.extend(['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem])

	try:
		output = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT)
		snapshots = []
		for line in output.decode().splitlines():
			parts = line.split(maxsplit=2)
			if len(parts) >= 3:
				snapshot_name = parts[0]
				snapshot_guid = parts[1]
				# For remote, we need to parse the creation time:
				#  e.g. "Wed Feb  8 13:02 2023"
				try:
					snapshot_creation = datetime.datetime.strptime(parts[2], "%a %b %d %H:%M %Y")
				except ValueError:
					# If for some reason the date parse fails, skip
					continue
				snapshots.append(Snapshot(snapshot_name, snapshot_guid, snapshot_creation))
		return snapshots

	except subprocess.CalledProcessError as e:
		# CalledProcessError will have a non-zero return code and the output in e.output
		err_output = e.output.decode(errors='replace').lower()
		if "dataset does not exist" in err_output or "cannot open" in err_output:
			# Return None to indicate the dataset truly doesn't exist
			return None
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
	transferMethod=""
):
	try:
		# Build the zfs send command
		send_cmd = ['zfs', 'send']
		if compressed:
			send_cmd.append('-Lce')
		if raw:
			send_cmd.append('-w')
		if sendName2 != "":
			send_cmd.extend(['-i', sendName2])
		send_cmd.append(sendName)

		if sendName2 != "":
			print(f"sending incrementally from {sendName2} -> {sendName} to {recvName}")
		else:
			print(f"sending {sendName} to {recvName}")

		process_send = subprocess.Popen(
			send_cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
		)

		# If sending locally
		if transferMethod == "local":
			recv_cmd = ['zfs', 'recv']
			if forceOverwrite:
				recv_cmd.append('-F')
			recv_cmd.append(recvName)

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
				print(f"recv error: {stderr}")
				sys.exit(1)
			else:
				print(stdout)
			print(f"received local send")

		# If sending remotely via ssh
		elif transferMethod == "ssh":
			print("sending via ssh")
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
				print(f"ERROR: remote recv error: {stderr}")
				sys.exit(1)
			else:
				print(stdout)
			print(f"received remote send")

		elif transferMethod == "netcat":
			try:
				print("Sending via netcat...")
				# Start the listener on the receiver side
				listen_cmd = f'nc -l {recvPort} | zfs receive {"-F " + recvName if forceOverwrite else recvName}'
				ssh_cmd_listener = f'ssh {recvHostUser}@{recvHost} "{listen_cmd}"'
				print(f"[Receiver Side] Listener command: {ssh_cmd_listener}")

				ssh_process_listener = subprocess.Popen(
					ssh_cmd_listener,
					shell=True,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					universal_newlines=True,
				)

				# Wait briefly to ensure the listener is ready
				time.sleep(5)

				# Prepare mbuffer
				# m_buff_cmd = ['mbuffer', '-s', '256k', '-m', str(mBufferSize) + mBufferUnit]
    
    			# Prepare mbuffer command
				m_buff_cmd = ['mbuffer', '-s', '256k']
				m_buff_cmd.extend(['-m', mBufferSize + mBufferUnit])
				print(f"[Sender Side] mbuffer command: {' '.join(m_buff_cmd)}")
    
				send_cmd_list = ['zfs', 'send']
				if compressed:
					send_cmd_list.append('-Lce')
				if raw:
					send_cmd_list.append('-w')
				if sendName2 != "":
					send_cmd_list.extend(['-i', sendName2])
				send_cmd_list.append(sendName)
    
				if sendName2 != "":
					print(f"sending incrementally from {sendName2} -> {sendName} to {recvName}")
				else:
					print(f"sending {sendName} to {recvName}")
				# Prepare and run the ZFS send command
				send_cmd_str = ' '.join(send_cmd_list)
				m_buff_cmd_str = ' '.join(m_buff_cmd)
				nc_command = f'{send_cmd_str} | {m_buff_cmd_str} | nc {recvHost} {recvPort}'
				print(f"[Sender Side] Netcat command: {nc_command}")

				nc_process = subprocess.Popen(
					nc_command,
					shell=True,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
				)
				nc_stdout, nc_stderr = nc_process.communicate()

				print(f"[Sender Side] nc stdout: {nc_stdout}")
				print(f"[Sender Side] nc stderr: {nc_stderr}")
				# Check for errors from nc process
				if nc_process.returncode != 0:
					print(f"[Sender Side] nc error: {nc_stderr}")
					sys.exit(1)

				print("[Sender Side] Successfully sent data via netcat.")

				# Verify dataset on the receiver
				snapshot_check_cmd = ['ssh', f'{recvHostUser}@{recvHost}', f'zfs list {recvName}']
				print(f"[Receiver Side] Snapshot check command: {' '.join(snapshot_check_cmd)}")
				snapshot_process = subprocess.Popen(
					snapshot_check_cmd,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					universal_newlines=True,
				)
				snapshot_output, snapshot_err = snapshot_process.communicate()

				print(f"[Receiver Side] Snapshot check stdout: {snapshot_output}")
				print(f"[Receiver Side] Snapshot check stderr: {snapshot_err}")

				if snapshot_err.strip():
					print(f"[Receiver Side] Error checking received dataset: {snapshot_err.strip()}")
				else:
					if snapshot_output.strip():
						print(f"[Receiver Side] Received dataset exists: {snapshot_output.strip()}")
					else:
						print("[Receiver Side] Dataset does not exist.")

			except subprocess.CalledProcessError as e:
				print(f"[Sender Side] Command failed with exit code {e.returncode}. Error: {e.stderr}")
				sys.exit(1)

			except Exception as e:
				print(f"ERROR: Send error: {e}")
				sys.exit(1)

		else:
			print("ERROR: Invalid transferMethod specified. Must be 'local', 'ssh', or 'netcat'.")
			sys.exit(1)

	except Exception as e:
		print(f"ERROR: Send error: {e}")
		sys.exit(1)


def main():
	try:
		sourceFilesystem = os.environ.get('zfsRepConfig_sourceDataset_dataset', '')
		isRecursiveSnap = os.environ.get('zfsRepConfig_sendOptions_recursive_flag', False)
		customName = os.environ.get('zfsRepConfig_sendOptions_customName', '')
		isRaw = os.environ.get('zfsRepConfig_sendOptions_raw_flag', False)
		isCompressed = os.environ.get('zfsRepConfig_sendOptions_compressed_flag', False)
		destinationRoot = os.environ.get('zfsRepConfig_destDataset_pool', '')
		destinationPath = os.environ.get('zfsRepConfig_destDataset_dataset', '')
		remoteUser = os.environ.get('zfsRepConfig_destDataset_user', 'root')
		remoteHost = os.environ.get('zfsRepConfig_destDataset_host', '')
		remotePort = os.environ.get('zfsRepConfig_destDataset_port', 22)
		mBufferSize = os.environ.get('zfsRepConfig_sendOptions_mbufferSize', 1)
		mBufferUnit = os.environ.get('zfsRepConfig_sendOptions_mbufferUnit', 'G')
		sourceRetentionTime = os.environ.get('zfsRepConfig_snapshotRetention_source_retentionTime', 0)
		sourceRetentionUnit = os.environ.get('zfsRepConfig_snapshotRetention_source_retentionUnit', '')
		destinationRetentionTime = os.environ.get('zfsRepConfig_snapshotRetention_destination_retentionTime', 0)
		destinationRetentionUnit = os.environ.get('zfsRepConfig_snapshotRetention_destination_retentionUnit', '')
		transferMethod = os.environ.get('zfsRepConfig_sendOptions_transferMethod', '')

		taskName = os.environ.get('taskName', '')

		forceOverwrite = False
		receivingFilesystem = f"{destinationPath}"  # or f"{destinationRoot}/{destinationPath}" if needed

		# Get source snapshots
		sourceSnapshots = get_local_snapshots(sourceFilesystem)
		sourceSnapshots.sort(key=lambda x: x.creation, reverse=True)
		incrementalSnapName = ""

		# Depending on remote or local, get destination snapshots
		if transferMethod == "netcat":
			port = '22'
		else:
			port = remotePort

		if remoteHost and remoteUser:
			destinationSnapshots = get_remote_snapshots(remoteUser, remoteHost, port, receivingFilesystem)
		else:
			destinationSnapshots = get_local_snapshots(receivingFilesystem)
		# print("Fetched source snapshots:", len(sourceSnapshots))
		# for snap in sourceSnapshots:
		# 	print(f"Name: {snap.name}, GUID: {snap.guid}, Creation: {snap.creation}")

		# print("Fetched destination snapshots:", len(destinationSnapshots))
		# for snap in destinationSnapshots:
		# 	print(f"Name: {snap.name}, GUID: {snap.guid}, Creation: {snap.creation}")

		# If destinationSnapshots is None, that means dataset does not exist on remote
		if destinationSnapshots is None:
			print(f"Remote dataset {receivingFilesystem} does not exist. Creating it with full send.")
			forceOverwrite = False

		# If no snapshots exist (i.e., an empty list), but the dataset does exist, we might need force
		elif not destinationSnapshots:
			forceOverwrite = True
			print("No snapshots found on the destination (but dataset exists). Forcefully overwriting dataset.")

		else:
			# We have some snapshots on the destination. Check for common snapshots by GUID.
			source_guids = {snap.guid: snap.name for snap in sourceSnapshots}
			common_snapshots = [snap for snap in destinationSnapshots if snap.guid in source_guids]

			if not common_snapshots:
				print("No common snapshots found on the destination. (Full send may require force overwrite.)")
				# Decide whether to force-overwrite or abort:
				# Here we do NOT set forceOverwrite automatically; adjust to your needs:
				forceOverwrite = True  # or False if you want to fail instead
			else:
				# We do have common snapshots; find the most recent one on destination
				common_snapshots.sort(key=lambda x: x.creation, reverse=True)
				mostRecentCommonSnap = common_snapshots[0]
				incrementalSnapName = source_guids[mostRecentCommonSnap.guid]
				print(f"Most recent common snapshot: {incrementalSnapName}")

		# Create a new local snapshot on the source
		newSnap = create_snapshot(sourceFilesystem, isRecursiveSnap, taskName, customName)
		# print(f"\n-----------PARAMETER CHECK------------\nsourceFS:{sourceFilesystem}\nnewSnap:{newSnap}\nreceivingFilesystem:{receivingFilesystem}\nincrementalSnapName:{incrementalSnapName}\nisCompressed:{isCompressed}\nisRaw:{isRaw}\nremoteHost:{remoteHost}\nremotePort:{remotePort}\nremoteUser:{remoteUser}\nmBufferSize:{mBufferSize}\nmBufferUnit:{mBufferUnit}\nforceOverwrite:{forceOverwrite}\n------------------END-----------------\n")
		# Perform the send (full or incremental)
		send_snapshot(
			newSnap,
			receivingFilesystem,
			incrementalSnapName,
			isCompressed,
			isRaw,
			remoteHost,
			port,
			remoteUser,
			str(mBufferSize),
			mBufferUnit,
			forceOverwrite,
			transferMethod
		)

		# Prune snapshots on source
		prune_snapshots_by_retention(
			sourceFilesystem,
			taskName,
			sourceRetentionTime,
			sourceRetentionUnit,
			newSnap
		)

		# Prune snapshots on destination
		prune_snapshots_by_retention(
			receivingFilesystem,
			taskName,
			destinationRetentionTime,
			destinationRetentionUnit,
			newSnap,
			remoteUser,
			remoteHost,
			port
		)

	except Exception as e:
		print(f"Exception: {e}")
		sys.exit(1)


if __name__ == "__main__":
	main()
