import subprocess
import argparse
import sys
import datetime

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
		new_snap = (f'{filesystem}@{custom_name}-{timestamp}')
	else:
		
		new_snap = (f'{filesystem}@{timestamp}')
  
	command.append(new_snap)
	
	subprocess.run(command)
	print(f"new snapshot created: {new_snap}")
	return new_snap

def prune_snapshots(filesystem, max_retain_count, sshUser="", sshHost="", sshPort=""):
	snapshots = []
 
	if sshHost:
		snapshots = get_remote_snapshots(sshUser, sshHost, sshPort, filesystem)
	else:
		snapshots = get_local_snapshots(filesystem)

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
					print(f"Failed to delete snapshot {snapshot.name}: {e}")
					sys.exit(1)	
			print(f"snapshot retention policy executed on {filesystem} - keeping {max_retain_count} snapshots (deleted {len(snapshots_to_delete)})")
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
        print(f"Failed to fetch local snapshots: {e}")
        return []

def get_remote_snapshots(user, host, port, filesystem):
    # ssh_cmd = ['ssh', f"{user}@{host}", '-p', str(port), 'zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem]
	ssh_cmd = ['ssh']
	if port != '22':
		ssh_cmd.extend(['-p', port])
	ssh_cmd.append(user + '@' + host)

	ssh_cmd.extend(['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem])

	# print(f"SSH Command: {' '.join(ssh_cmd)}")  # Debug output
 
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
		print(f"Failed to fetch remote snapshots: {e}")
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

		# If sending remotely via SSH
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

			# print(f"SSH_CMD: {ssh_cmd}")	
			print(f"receiving {sendName} in {recvName} via {recvHostUser}@{recvHost}:{recvPort}")

			process_ssh_recv = subprocess.Popen(
				ssh_cmd,
				stdin=process_m_buff.stdout,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				universal_newlines=True,
			)

			stdout, stderr = process_ssh_recv.communicate()

			if process_ssh_recv.returncode != 0:
				print(f"SSH recv error: {stderr}")
				sys.exit(1)
			else:
				print(stdout)
    
			print(f"received remote send")


	except Exception as e:
		print(f"send error: {e}")
		sys.exit(1)


def main():
	parser = argparse.ArgumentParser(description='ZFS Replication Script')
	parser.add_argument('filesystem', type=str, help='source filesystem to snapshot')
	parser.add_argument('-R', '--recursive', action='store_true', help='recursively snap all child datasets')
	parser.add_argument('-cn', '--customName', type=str, nargs='?', default=None, help='custom name for snapshot')
	compression_options = parser.add_mutually_exclusive_group()
	compression_options.add_argument('-r', '--raw', action='store_true', help='send raw')
	compression_options.add_argument('-c', '--compressed', action='store_true', help='send compressed')
	parser.add_argument('--root', type=str, help='root of send destination')
	parser.add_argument('--path', type=str, help='path of send destination')
	parser.add_argument('--user', type=str, nargs='?', default='root', help='user of ssh connection (root)')
	parser.add_argument('--host', type=str, nargs='?', default='', help='hostname or ip of ssh connection')
	parser.add_argument('--port', type=str, default='22', help='port to connect via ssh (22)')
	parser.add_argument('--mbuffsize', type=str, default='1', help='size value of mbuffer')
	parser.add_argument('--mbuffunit', type=str, default='G', help='unit to use for mbuffer size')
	parser.add_argument('--snapsToKeepSrc', type=str, default='0', help='snaps to keep on source')
	parser.add_argument('--snapsToKeepDest', type=str, default='0', help='snaps to keep on destination')

	args = parser.parse_args()
 
	sourceFilesystem = args.filesystem
	isRecursiveSnap = args.recursive
	customName = args.customName
	isRaw = args.raw
	isCompressed = args.compressed
	destinationRoot = args.root
	destinationPath = args.path
	sshUser = args.user
	sshHost = args.host
	sshPort = args.port
	mBufferSize = args.mbuffsize
	mBufferUnit = args.mbuffunit
	snapsToKeepSrc = args.snapsToKeepSrc
	snapsToKeepDest = args.snapsToKeepDest

	forceOverwrite = False
	
	receivingFilesystem = (f"{destinationPath}")
	# receivingFilesystem = (f"{destinationRoot}/{destinationPath}")

	sourceSnapshots = get_local_snapshots(sourceFilesystem)

	sourceSnapshots.sort(key=lambda x: x.creation, reverse=True)

	incrementalSnapName = ""
  
	if sshHost:
		destinationSnapshots = get_remote_snapshots(sshUser, sshHost, sshPort, receivingFilesystem)
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
			print(f"Snapshots on source + destination but none in common. Aborting send.")
			sys.exit(1)
		else:
			# Find the most recent common snapshot from destinationSnapshots
			common_snapshots.sort(key=lambda x: x.creation, reverse=True)  # Ensure they are sorted by creation time
			mostRecentCommonSnap = common_snapshots[0]
			# Use the GUID to get the correct source snapshot name
			incrementalSnapName = source_guids[mostRecentCommonSnap.guid]  # Fetch the source snapshot name using the GUID
			# print("Setting incrementalSnap to:", incrementalSnapName)

  
	newSnap = create_snapshot(sourceFilesystem, isRecursiveSnap, customName)
	# print(f"\n-----------PARAMETER CHECK------------\nsourceFS:{sourceFilesystem}\nnewSnap:{newSnap}\nreceivingFilesystem:{receivingFilesystem}\nincrementalSnapName:{incrementalSnapName}\nisCompressed:{isCompressed}\nisRaw:{isRaw}\nsshHost:{sshHost}\nsshPort:{sshPort}\nsshUser:{sshUser}\nmBufferSize:{mBufferSize}\nmBufferUnit:{mBufferUnit}\nforceOverwrite:{forceOverwrite}\n------------------END-----------------\n")
	send_snapshot(newSnap, receivingFilesystem, incrementalSnapName, isCompressed, isRaw, sshHost, sshPort, sshUser, mBufferSize, mBufferUnit, forceOverwrite)
	prune_snapshots(sourceFilesystem, snapsToKeepSrc)	
	prune_snapshots(receivingFilesystem, snapsToKeepDest, sshUser, sshHost, sshPort)
if __name__ == "__main__":
	main()