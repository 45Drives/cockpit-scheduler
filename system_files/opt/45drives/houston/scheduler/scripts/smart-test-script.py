import subprocess
import sys
import os
from notify import get_notifier

notifier = get_notifier()

def run_smartctl_test(diskPathList, testType):
    valid_test_types = ['offline', 'short', 'long', 'conveyance']
 
    if testType not in valid_test_types:
        msg = f"Invalid test type: {testType}. Valid test types are: {', '.join(valid_test_types)}"
        print(msg)
        notifier.notify(f"STATUS={msg}")
        sys.exit(1)

    diskPaths = diskPathList.split(',')
    total = len([d for d in diskPaths if d.strip()])
    if total == 0:
        msg = "No disks specified for SMART test."
        print(msg)
        notifier.notify(f"STATUS={msg}")
        return

    for idx, diskPath in enumerate(diskPaths, start=1):
        diskPath = diskPath.strip()
        if not diskPath:
            continue

        notifier.notify(f"STATUS=Starting {testType} SMART test on {diskPath} ({idx}/{total})…")

        try:
            command = ['smartctl', '-t', testType, f'{diskPath}']
            print(f"Running command: {' '.join(command)}")
            result = subprocess.run(command, universal_newlines=True)
            if result.returncode == 0:
                msg = f"Successfully started {testType} test on {diskPath}"
                print(msg)
                notifier.notify(f"STATUS={msg}")
            else:
                msg = f"Failed to start {testType} test on {diskPath}"
                print(msg)
                notifier.notify(f"STATUS={msg}")
                # stderr may be None if not captured; leave as-is
        except Exception as e:
            msg = f"An error occurred while starting {testType} test on {diskPath}: {e}"
            print(msg)
            notifier.notify(f"STATUS={msg}")

def main():
    diskPathList = os.environ.get('smartTestConfig_disks', '')
    testType = os.environ.get('smartTestConfig_testType', 'short')

    notifier.notify("STATUS=Starting SMART test task…")
    notifier.notify("READY=1")
    notifier.notify("STATUS=Running SMART test task…")

    run_smartctl_test(diskPathList, testType)

    notifier.notify("STATUS=SMART test task finished scheduling tests.")


if __name__ == "__main__":
    main()