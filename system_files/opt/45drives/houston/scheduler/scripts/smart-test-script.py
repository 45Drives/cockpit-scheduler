import subprocess
import argparse
import sys

def run_smartctl_test(diskPathList, testType):
	valid_test_types = ['offline', 'short', 'long', 'conveyance']
 
	if testType not in valid_test_types:
		print(f"Invalid test type: {testType}. Valid test types are: {', '.join(valid_test_types)}")
		sys.exit(1)

	# Splitting the diskString into individual disks
	diskPaths = diskPathList.split(',')
	for diskPath in diskPaths:
		diskPath = diskPath.strip()
  
		try:
			command = ['smartctl', '-t', testType, f'{diskPath}']
			print(f"Running command: {' '.join(command)}")
			result = subprocess.run(command, universal_newlines=True)
			if result.returncode == 0:
				print(f"Successfully started {testType} test on {diskPath}")
			else:
				print(f"Failed to start {testType} test on {diskPath}")
				print(result.stderr)
		except Exception as e:
			print(f"An error occurred while starting {testType} test on {diskPath}: {e}")

def main():
	parser = argparse.ArgumentParser(description='SMART Test Script')
	parser.add_argument('--disks', type=str, help='comma delimited string of the disk(s) path(s)')
	parser.add_argument('--type', type=str, help='type of S.M.A.R.T. test to perform on disk(s)')

	args = parser.parse_args()
 
	diskPathList = args.disks
	testType = args.type
 
	run_smartctl_test(diskPathList, testType)

if __name__ == "__main__":
	main()