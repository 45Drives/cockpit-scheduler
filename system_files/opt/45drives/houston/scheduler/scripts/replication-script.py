import subprocess
import sys
import datetime
import os

class Snapshot:
	def __init__(self, name, guid, creation):
		self.name = name
		self.guid = guid
		self.creation = creation
	 
def create_snapshot(filesystem, is_recursive, custom_name=None):
	command = [ 'zfs', 'snapshot' ]
	if is_recursive:
		command.append('-r')
	timestamp = datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')
 
	if custom_name:
		new_snap = (f'{filesystem}@scheduler-{custom_name}-{timestamp}')
	else:
		new_snap = (f'{filesystem}@scheduler-{timestamp}')
  
	command.append(new_snap)
	
	subprocess.run(command)
	print(f"new snapshot created: {new_snap}")
	return new_snap

def prune_snapshots(filesystem, max_retain_count, remoteUser="", remoteHost="", remotePort=""):
	snapshots = []
 
	if remoteHost:
		snapshots = get_remote_snapshots(remoteUser, remoteHost, remotePort, filesystem)
	else:
		snapshots = get_local_snapshots(filesystem)

	if max_retain_count is not '0' and max_retain_count is not 0:
		if len(snapshots) is not 0:
			snapshots.sort(key=lambda x: x.creation)

			if len(snapshots) <= int(max_retain_count):
				print(f"snapshot retention policy delayed on {filesystem} - currently {len(snapshots)} snapshots out of {max_retain_count} allowed")
				return
			else:
				snapshots_to_delete = snapshots[:-int(max_retain_count)]  # Older snapshots beyond the retain limit
				for snapshot in snapshots_to_delete:
					delete_command = ['zfs', 'destroy', snapshot.name]
					try:
						subprocess.run(delete_command, check=True)
						# print(f"Deleted snapshot: {snapshot.name}")
					except subprocess.CalledProcessError as e:
						print(f"ERROR: Failed to delete snapshot {snapshot.name}: {e}")
						sys.exit(1)	
				print(f"snapshot retention policy executed on {filesystem} - keeping {max_retain_count} snapshots (deleted {len(snapshots_to_delete)})")
		else:
			# print("No snapshots to prune.")
			return
	else:
		# print("No snapshots to prune.")
		return

def get_local_snapshots(filesystem):
	command = ['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem]
	try:
		output = subprocess.check_output(command)
		snapshots = []
		for line in output.decode().splitlines():
			parts = line.split()
			if len(parts) >= 3:
				snapshot_name = parts[0]
				snapshot_guid = parts[1]
				snapshot_creation = parts[2]
				snapshot = Snapshot(snapshot_name, snapshot_guid, snapshot_creation)
				snapshots.append(snapshot)
		return snapshots
	except subprocess.CalledProcessError as e:
		print(f"ERROR: Failed to fetch local snapshots: {e}")
		return []

def get_remote_snapshots(user, host, port, filesystem):
	# ssh_cmd = ['ssh', f"{user}@{host}", '-p', str(port), 'zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem]
	ssh_cmd = ['ssh']
	if port != '22':
		ssh_cmd.extend(['-p', port])
	ssh_cmd.append(user + '@' + host)

	ssh_cmd.extend(['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem])

	# print(f"remote Command: {' '.join(ssh_cmd)}")  # Debug output
 
	try:
		output = subprocess.check_output(ssh_cmd)
		snapshots = []
		for line in output.decode().splitlines():
			parts = line.split()
			if len(parts) >= 3:
				snapshot_name = parts[0]
				snapshot_guid = parts[1]
				snapshot_creation = parts[2]
				snapshot = Snapshot(snapshot_name, snapshot_guid, snapshot_creation)
				snapshots.append(snapshot)
		return snapshots
	except subprocess.CalledProcessError as e:
		print(f"ERROR: Failed to fetch remote snapshots: {e}")
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
	
def send_snapshot(sendName, recvName, sendName2="", compressed=False, raw=False, recvHost="", recvPort=22, recvHostUser="", mBufferSize=1, mBufferUnit="G", forceOverwrite=False):
	try:
		# Initial local send command
		send_cmd = ['zfs', 'send']
		
		# send_cmd.append('-v')
		
		if compressed:
			send_cmd.append('-Lce')

		if raw:
			send_cmd.append('-w')

		if sendName2 != "":
			send_cmd.extend(['-i', sendName2])

		send_cmd.append(sendName)

		# print(f"SEND_CMD: {send_cmd}")
		print(f"sending {sendName} to {recvName}")

		process_send = subprocess.Popen(
			send_cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
		)
		

		# If sending locally
		if recvHost == "" or recvHost is None:
			recv_cmd = ['zfs', 'recv']
			
			# recv_cmd.append('-v')
			if forceOverwrite:
				recv_cmd.append('-F')

			recv_cmd.append(recvName)

			# print(f"RECV_CMD: {recv_cmd}")
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
		if recvHost != "" and recvHost is not None:

			m_buff_cmd = ['mbuffer', '-s', '256k']
			m_buff_cmd.extend(['-m', mBufferSize + mBufferUnit])

			process_m_buff = subprocess.Popen(
				m_buff_cmd,
				stdin=process_send.stdout,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				universal_newlines=True,
			)

			ssh_cmd = ['ssh']

			if recvPort != '22':
				ssh_cmd.extend(['-p', recvPort])

			ssh_cmd.append(recvHostUser + '@' + recvHost)

			ssh_cmd.extend(['zfs', 'recv'])
			
			# ssh_cmd.append('-v')
			if forceOverwrite:
				ssh_cmd.append('-F')

			ssh_cmd.append(recvName)

			# print(f"ssh_cmd: {ssh_cmd}")	
			print(f"receiving {sendName} in {recvName} via {recvHostUser}@{recvHost}:{recvPort}")

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


	except Exception as e:
		print(f"ERROR: send error: {e}")
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
		snapsToKeepSrc = os.environ.get('zfsRepConfig_snapRetention_source', '')
		snapsToKeepDest = os.environ.get('zfsRepConfig_snapRetention_destination', '')

		forceOverwrite = False
		
		receivingFilesystem = (f"{destinationPath}")
		# receivingFilesystem = (f"{destinationRoot}/{destinationPath}")

		sourceSnapshots = get_local_snapshots(sourceFilesystem)

		sourceSnapshots.sort(key=lambda x: x.creation, reverse=True)

		incrementalSnapName = ""

		if remoteHost:
			destinationSnapshots = get_remote_snapshots(remoteUser, remoteHost, remotePort, receivingFilesystem)
		else:
			destinationSnapshots = get_local_snapshots(receivingFilesystem)

		# print("Fetched source snapshots:", len(sourceSnapshots))
		# for snap in sourceSnapshots:
		# 	print(f"Name: {snap.name}, GUID: {snap.guid}, Creation: {snap.creation}")

		# print("Fetched destination snapshots:", len(destinationSnapshots))
		# for snap in destinationSnapshots:
		# 	print(f"Name: {snap.name}, GUID: {snap.guid}, Creation: {snap.creation}")

		if not destinationSnapshots:
			forceOverwrite = True
			print("No snapshots found on the destination. Forcefully overwriting dataset.")
		else:
			# Identify common snapshots by GUID
			source_guids = {snap.guid: snap.name for snap in sourceSnapshots}  # Map GUIDs to source snapshot names
			common_snapshots = [snap for snap in destinationSnapshots if snap.guid in source_guids]

			if not common_snapshots:
				# raise Exception("No common snapshots found between source and destination. Operation aborted.")
				raise Exception(f"ERROR: Snapshots on source + destination but none in common. Aborting send.")
			else:
				# Find the most recent common snapshot from destinationSnapshots
				common_snapshots.sort(key=lambda x: x.creation, reverse=True)  # Ensure they are sorted by creation time
				mostRecentCommonSnap = common_snapshots[0]
				# Use the GUID to get the correct source snapshot name
				incrementalSnapName = source_guids[mostRecentCommonSnap.guid]  # Fetch the source snapshot name using the GUID
				# print("Setting incrementalSnap to:", incrementalSnapName)


		newSnap = create_snapshot(sourceFilesystem, isRecursiveSnap, customName)
		# print(f"\n-----------PARAMETER CHECK------------\nsourceFS:{sourceFilesystem}\nnewSnap:{newSnap}\nreceivingFilesystem:{receivingFilesystem}\nincrementalSnapName:{incrementalSnapName}\nisCompressed:{isCompressed}\nisRaw:{isRaw}\nremoteHost:{remoteHost}\nremotePort:{remotePort}\nremoteUser:{remoteUser}\nmBufferSize:{mBufferSize}\nmBufferUnit:{mBufferUnit}\nforceOverwrite:{forceOverwrite}\n------------------END-----------------\n")
		send_snapshot(newSnap, receivingFilesystem, incrementalSnapName, isCompressed, isRaw, remoteHost, remotePort, remoteUser, mBufferSize, mBufferUnit, forceOverwrite)
		prune_snapshots(sourceFilesystem, snapsToKeepSrc)	
		prune_snapshots(receivingFilesystem, snapsToKeepDest, remoteUser, remoteHost, remotePort)
  
	except Exception as e:
		print(f"Exception: {e}")
		sys.exit(1)

if __name__ == "__main__":
	main()