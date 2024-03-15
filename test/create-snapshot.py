import argparse
import subprocess
import datetime

def create_snapshot(filesystem, recursive, custom_name=None):
	command = [ 'zfs', 'snapshot']
	if recursive:
		command.append('-r')
	
	if custom_name:
		command.append(f'{filesystem}@{custom_name}')
	else:
		timestamp = datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')
		command.append(f'{filesystem}@{timestamp}')

	subprocess.run(command)

def main():
	parser = argparse.ArgumentParser(description='Create Snapshot')
	parser.add_argument('filesystem', type=str, help='filesystem to snapshot')
	parser.add_argument('--r', action='store_true',help='snap all child datasets')
	parser.add_argument('--custom-name', type=str, nargs='?', default=None, help='custom name for snapshot') 
    # python3 create-snapshot.py <filesystem> --r --custom-name <customName>    
	args = parser.parse_args()

	create_snapshot(args.filesystem, args.r, args.custom_name)

if __name__ == "__main__":
	main()