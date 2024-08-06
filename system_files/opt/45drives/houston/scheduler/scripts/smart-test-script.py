import subprocess
import sys
import os

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
	diskPathList = os.environ.get('smartTestConfig_disks', '')
	testType = os.environ.get('smartTestConfig_testType', 'short')
 
	run_smartctl_test(diskPathList, testType)

if __name__ == "__main__":
	main()