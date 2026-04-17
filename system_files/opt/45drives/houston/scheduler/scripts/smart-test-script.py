import subprocess
import sys
import os
import traceback
import datetime as dt
from notify import get_notifier


class SafeStream:
    """Wrap stdout/stderr so broken pipes don't crash the script."""
    def __init__(self, stream):
        self._stream = stream
    def write(self, data):
        try:
            return self._stream.write(data)
        except Exception:
            return 0
    def flush(self):
        try:
            return self._stream.flush()
        except Exception:
            return None
    def isatty(self):
        try:
            return self._stream.isatty()
        except Exception:
            return False
    def fileno(self):
        try:
            return self._stream.fileno()
        except Exception:
            return -1
    def __getattr__(self, name):
        return getattr(self._stream, name)

sys.stdout = SafeStream(sys.stdout)
sys.stderr = SafeStream(sys.stderr)

notifier = get_notifier()

DEBUG_LOG = os.environ.get("SMART_DEBUG_LOG", "/tmp/smart_test_debug.log")
DEBUG_ENABLED = os.environ.get("SMART_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")

def dbg(msg: str):
    if not DEBUG_ENABLED:
        return
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{dt.datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass

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
    try:
        diskPathList = os.environ.get('smartTestConfig_disks', '')
        testType = os.environ.get('smartTestConfig_testType', 'short')

        dbg(f"=== smart test task start === disks={diskPathList} type={testType}")

        notifier.notify("STATUS=Starting SMART test task…")
        notifier.notify("READY=1")
        notifier.notify("STATUS=Running SMART test task…")

        run_smartctl_test(diskPathList, testType)

        notifier.notify("STATUS=SMART test task finished scheduling tests.")
        dbg("=== smart test task completed ===")

    except SystemExit:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        dbg(f"FATAL: {tb}")
        print(f"FATAL: {e}", file=sys.stderr)
        print(tb, file=sys.stderr)
        notifier.notify(f"STATUS=SMART test task failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()