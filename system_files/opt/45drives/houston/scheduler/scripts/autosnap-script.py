import subprocess
import sys
import datetime
import os
import time  # Import the time module

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
 
	# Sleep for 5 seconds to slow down execution for debugging
	# time.sleep(5)
	return new_snap

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

def prune_snapshots(filesystem, max_retain_count):
	snapshots = get_local_snapshots(filesystem)
 
	if max_retain_count is not 0:
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
						print(f"Deleted snapshot: {snapshot.name}")
						# Sleep for 5 seconds after each deletion for debugging
						time.sleep(5)
					except subprocess.CalledProcessError as e:
						print(f"Failed to delete snapshot {snapshot.name}: {e}")
						sys.exit(1)	
				print(f"snapshot retention policy executed on {filesystem} - keeping {max_retain_count} snapshots (deleted {len(snapshots_to_delete)})")
	
				# Sleep for 5 seconds after pruning snapshots
				# time.sleep(5)
		else:
			# print("No snapshots to prune.")
			return
	else:
		# print("No snapshots to prune.")
		return


def main():
	filesystem = os.environ.get('autoSnapConfig_filesystem_dataset', '')
	isRecursiveSnap = os.environ.get('autoSnapConfig_recursive_flag', False)
	customName = os.environ.get('autoSnapConfig_customName', '')
	snapsToKeep = os.environ.get('autoSnapConfig_snapRetention', '')

	create_snapshot(filesystem, isRecursiveSnap, customName)
	prune_snapshots(filesystem, snapsToKeep)

if __name__ == "__main__":
	main()
