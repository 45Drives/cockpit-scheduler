import subprocess
import argparse
import re
import json
import os
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
	
	if custom_name:
		new_snap = (f'{filesystem}@{custom_name}')
	else:
		timestamp = datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')
		new_snap = (f'{filesystem}@{timestamp}')
  
	command.append(new_snap)
	
	subprocess.run(command)
 
	return new_snap

 
def get_local_snapshots(filesystem):
	try:
		output = subprocess.check_output(['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem])
		snapshots = []
		for line in output.splitlines():
			match = re.match(r'^([\w\/@]+)\s+(\d+)\s+([A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}\s+\d{4})', line.decode('utf-8'))
			if match:
				snapshot_name = match.group(1)
				snapshot_guid = match.group(2)
				snapshot_creation = match.group(3)
				snapshot = Snapshot(snapshot_name, snapshot_guid, snapshot_creation)
				snapshots.append(snapshot)

		return snapshots
	except subprocess.CalledProcessError:
		return []

def get_remote_snapshots(user, host, port, filesystem):
	try:
		ssh_cmd = ['ssh']
		if port != '22':
			ssh_cmd.extend(['-p', port])
		ssh_cmd.append(user + '@' + host)
		
		ssh_cmd.extend(['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem])
		output = subprocess.check_output(ssh_cmd)
		snapshots = []
		for line in output.splitlines():
			match = re.match(r'^([\w\/@]+)\s+(\d+)\s+([A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}\s+\d{4})', line.decode('utf-8'))
			if match:
				snapshot_name = match.group(1)
				snapshot_guid = match.group(2)
				snapshot_creation = match.group(3)
				snapshot = Snapshot(snapshot_name, snapshot_guid, snapshot_creation)
				snapshots.append(snapshot)

		return snapshots

	except subprocess.CalledProcessError:
		return []
        	
def get_most_recent_snapshot(snapshots):
    if snapshots:
        return snapshots[0]
    else:
        return None
    
def send_snapshot(sendName, recvName, sendName2="", compressed=False, raw=False, recvHost="", recvPort=22, recvHostUser="", mBufferSize=1, mBufferUnit="G"):
    try:
        # Initial local send command
        send_cmd = ['zfs', 'send', '-v']

        if compressed:
            send_cmd.append('-Lce')

        if raw:
            send_cmd.append('-w')

        if sendName2 != "":
            send_cmd.extend(['-i', sendName2])

        send_cmd.append(sendName)

        print(f"SEND_CMD: {send_cmd}")

        process_send = subprocess.Popen(
            send_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # If sending locally
        if recvHost == "":
            recv_cmd = ['zfs', 'recv', '-v']

            recv_cmd.append(recvName)

            print(f"RECV_CMD: {recv_cmd}")

            process_recv = subprocess.Popen(
                recv_cmd,
                stdin=process_send.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
           
            stdout, stderr = process_recv.communicate()

            if process_recv.returncode != 0:
                raise Exception(f"Error: {stderr}")
            else:
                print(stdout)

        # If sending remotely via SSH
        if recvHost != "":

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
            ssh_cmd.append('-v')

            ssh_cmd.append(recvName)

            print(f"SSH_CMD: {ssh_cmd}")

            process_ssh_recv = subprocess.Popen(
                ssh_cmd,
                stdin=process_m_buff.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            stdout, stderr = process_ssh_recv.communicate()

            print(f"SSH_STDERR: {stderr}")

            if process_ssh_recv.returncode != 0:
                raise Exception(f"Error: {stderr}")
            else:
                print(stdout)

    except Exception as e:
        print(f"An error occurred: {e}")


def main():
	parser = argparse.ArgumentParser(description='ZFS Replication Script')
	parser.add_argument('filesystem', type=str, help='source filesystem to snapshot')
	parser.add_argument('-R', '--recursive', action='store_true', help='recursively snap all child datasets')
	parser.add_argument('-cn', '--custom-name', type=str, nargs='?', default=None, help='custom name for snapshot')
	compression_options = parser.add_mutually_exclusive_group()
	compression_options.add_argument('-r', '--raw', action='store_true', help='send raw')
	compression_options.add_argument('-c', '--compressed', action='store_true', help='send compressed')
	parser.add_argument('--root', type=str, help='root of send destination')
	parser.add_argument('--path', type=str, help='path of send destination')
	parser.add_argument('--user', type=str, nargs='?', default='root', help='user of ssh connection (root)')
	parser.add_argument('--host', type=str, nargs='?', default="", help='hostname or ip of ssh connection')
	parser.add_argument('--port', type=str, default='22', help='port to connect via ssh (22)')
	parser.add_argument('--mbuffsize', type=str, default='1', help='size value of mbuffer')
	parser.add_argument('--mbuffunit', type=str, default='G', help='unit to use for mbuffer size')

	args = parser.parse_args()
 
	sourceFilesystem = args.filesystem
	isRecursiveSnap = args.recursive
	customName = args.custom_name
	isRaw = args.raw
	isCompressed = args.compressed
	destinationRoot = args.root
	destinationPath = args.path
	sshUser = args.user
	sshHost = args.host
	sshPort = args.port
	mBufferSize = args.mbuffsize
	mBufferUnit = args.mbuffunit

	receivingFilesystem = (f"{destinationRoot}{destinationPath}")

	sourceSnapshots = get_local_snapshots(sourceFilesystem)
	sourceSnapshots.sort(key=lambda x: x.creation, reverse=True)

	incrementalSnapName = ""
  
	if sshHost:
		destinationSnapshots = get_remote_snapshots(sshUser, sshHost, sshPort, receivingFilesystem)
	else:
		destinationSnapshots = get_local_snapshots(receivingFilesystem)
  
	if destinationSnapshots is not None:
		destinationSnapshots.sort(key=lambda x: x.creation, reverse=True)
		# print("sourceSnapshots:")
		# for snap in sourceSnapshots:
			# print(f"Name: {snap.name}, GUID: {snap.guid}, Creation: {snap.creation}")

		# print("destinationSnapshots:")
		# for snap in destinationSnapshots:
			# print(f"Name: {snap.name}, GUID: {snap.guid}, Creation: {snap.creation}")

		mostRecentDestinationSnap = get_most_recent_snapshot(destinationSnapshots)
		if mostRecentDestinationSnap is not None:
			# print(f"\n********mostRecentDestSnap********\nName: {mostRecentDestinationSnap.name}\nGUID: {mostRecentDestinationSnap.guid}\nCreation: {mostRecentDestinationSnap.creation}\n****************END***************\n")

			for source_snap in sourceSnapshots:
				if source_snap.guid == mostRecentDestinationSnap.guid:
					incrementalSnapName = source_snap.name
					print("Setting incrementalSnap to:", incrementalSnapName)
					break  # Exit loop once a matching snapshot is found
				else:
					incrementalSnapName = ""  # If no match is found, set to empty string
					# print("Not a match.")
		
			common_snapshots = set(sourceSnapshots) & set(destinationSnapshots)

			if common_snapshots:
				common_ancestor = max(common_snapshots)
				if common_ancestor in destinationSnapshots:
					incrementalSnapName = common_ancestor
	
	newSnap = create_snapshot(sourceFilesystem, isRecursiveSnap, customName)
	print(f"\n-----------PARAMETER CHECK------------\nnewSnap:{newSnap}\nreceivingFilesystem:{receivingFilesystem}\nincrementalSnapName:{incrementalSnapName}\nisCompressed:{isCompressed}\nisRaw:{isRaw}\nsshHost:{sshHost}\nsshPort:{sshPort}\nsshUser:{sshUser}\nmBufferSize:{mBufferSize}\nmBufferUnit:{mBufferUnit}\n------------------END-----------------\n")
	send_snapshot(newSnap, receivingFilesystem, incrementalSnapName, isCompressed, isRaw, sshHost, sshPort, sshUser, mBufferSize, mBufferUnit)

if __name__ == "__main__":
	main()