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
	# return new_snap


def prune_snapshots(filesystem, max_retain_count):
	snapshots = []

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


def main():
	parser = argparse.ArgumentParser(description='ZFS Replication Script')
	parser.add_argument('filesystem', type=str, help='source filesystem to snapshot')
	parser.add_argument('-R', '--recursive', action='store_true', help='recursively snap all child datasets')
	parser.add_argument('-cn', '--customName', type=str, nargs='?', default=None, help='custom name for snapshot')
	parser.add_argument('--snapsToKeep', type=str, default='0', help='snaps to keep')

	args = parser.parse_args()
 
	filesystem = args.filesystem
	isRecursiveSnap = args.recursive
	customName = args.customName
	snapsToKeep = args.snapsToKeep

	create_snapshot(filesystem, isRecursiveSnap, customName)
	prune_snapshots(filesystem, snapsToKeep)
if __name__ == "__main__":
	main()