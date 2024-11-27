import subprocess
import sys
import datetime
import os

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
	
	subprocess.run(command)
	print(f"new snapshot created: {new_snap}")

	return new_snap

def get_local_snapshots(filesystem):
    command = ['zfs', 'list', '-H', '-o', 'name,guid,creation', '-t', 'snapshot', '-r', filesystem]
    try:
        output = subprocess.check_output(command)
        snapshots = []
        for line in output.decode().splitlines():
            # print(f'print line: {line}')
            parts = line.split(maxsplit=2)  # Split into exactly 3 parts: name, guid, and creation
            if len(parts) == 3:
                snapshot_name = parts[0]
                snapshot_guid = parts[1]
                # snapshot_creation = parts[2]  # Keep the full creation field
                snapshot_creation = datetime.datetime.strptime(parts[2], "%a %b %d %H:%M %Y")
                snapshot = Snapshot(snapshot_name, snapshot_guid, snapshot_creation)
                snapshots.append(snapshot)
                # print(f'snapshot: {snapshot_name}: {snapshot_creation}')
        return snapshots
    except subprocess.CalledProcessError as e:
        print(f"Failed to fetch local snapshots: {e}")
        return []


def prune_snapshots_by_retention(filesystem, task_name, retention_time, retention_unit, excluded_snapshot_name):
	snapshots = get_local_snapshots(filesystem)
	now = datetime.datetime.now()

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
			print(f'excluded snap: {excluded_snapshot_name}')
			# Exclude current snapshot and focus on snapshots belonging to task
			if task_name in snapshot.name and snapshot.name != excluded_snapshot_name:
				# print(f'creation: {snapshot.creation}')
				creation_time = snapshot.creation
				age_milliseconds = (now - creation_time).total_seconds() * 1000
				if age_milliseconds > retention_milliseconds:
					snapshots_to_delete.append(snapshot)

		for snapshot in snapshots_to_delete:
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

def main():
	filesystem = os.environ.get('autoSnapConfig_filesystem_dataset', '')
	isRecursiveSnap = os.environ.get('autoSnapConfig_recursive_flag', False)
	customName = os.environ.get('autoSnapConfig_customName', '')
	retentionTime = os.environ.get('autoSnapConfig_snapshotRetention_retentionTime', 0)
	retentionUnit = os.environ.get('autoSnapConfig_snapshotRetention_retentionUnit', '')
	taskName = os.environ.get('taskName', '')

	createdSnapName = create_snapshot(filesystem, isRecursiveSnap, taskName, customName)

	if retentionTime is not 0 and retentionTime is not '0' and retentionUnit is not '':
		prune_snapshots_by_retention(filesystem, taskName, retentionTime, retentionUnit, createdSnapName)

if __name__ == "__main__":
	main()