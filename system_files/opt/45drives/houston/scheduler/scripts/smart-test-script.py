import subprocess
import sys
import os
import traceback
import datetime as dt
from notify import get_notifier
from task_retry import run_with_retry_policy


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

# Strip anything that could escape /tmp or alias another path; this script runs as root.
_DEBUG_TASK_NAME = "".join(
    c for c in os.environ.get("taskName", "").strip() if c.isalnum() or c in "-_"
)[:64]
# An empty SMART_DEBUG_LOG in the unit's env file would otherwise win over the default.
DEBUG_LOG = os.environ.get("SMART_DEBUG_LOG", "").strip() or (
    f"/tmp/smart_test_debug_{_DEBUG_TASK_NAME}.log" if _DEBUG_TASK_NAME else "/tmp/smart_test_debug.log"
)
DEBUG_ENABLED = os.environ.get("SMART_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")

def dbg(msg: str):
    if not DEBUG_ENABLED:
        return
    try:
        # O_NOFOLLOW: refuse to append through a symlink planted in world-writable /tmp.
        fd = os.open(DEBUG_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as f:
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
    run_with_retry_policy(main, unit_prefix="houston_scheduler_SmartTest_")