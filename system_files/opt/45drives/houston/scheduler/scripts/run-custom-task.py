#!/usr/bin/env python3
"""Wrapper for CustomTask that sends sd_notify READY=1 before executing the user's command."""
import sys
import os
import subprocess
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

DEBUG_LOG = os.environ.get("CUSTOM_TASK_DEBUG_LOG", "/tmp/custom_task_debug.log")
DEBUG_ENABLED = os.environ.get("CUSTOM_TASK_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")

def dbg(msg: str):
    if not DEBUG_ENABLED:
        return
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{dt.datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass

def main():
    notifier = get_notifier()
    try:
        if len(sys.argv) < 2:
            print("ERROR: No command provided to run-custom-task.py", file=sys.stderr)
            sys.exit(1)

        command = sys.argv[1:]
        dbg(f"=== custom task start === cmd={' '.join(command)}")

        notifier.notify("READY=1")
        notifier.notify(f"STATUS=Running: {' '.join(command)}")

        result = subprocess.run(command)

        if result.returncode == 0:
            notifier.notify("STATUS=Completed successfully")
            dbg("=== custom task completed ===")

            # Persist last-run timestamp for UI display across disable/enable cycles
            try:
                import time as _time
                _task_name = os.environ.get("taskName", "").strip()
                if _task_name:
                    _lr = f"/etc/systemd/system/houston_scheduler_CustomTask_{_task_name}.lastrun"
                    with open(_lr, "w") as f:
                        f.write(str(int(_time.time())))
            except Exception:
                pass
        else:
            notifier.notify(f"STATUS=Exited with code {result.returncode}")
            dbg(f"custom task exited with code {result.returncode}")

        sys.exit(result.returncode)

    except SystemExit:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        dbg(f"FATAL: {tb}")
        print(f"FATAL: {e}", file=sys.stderr)
        print(tb, file=sys.stderr)
        notifier.notify(f"STATUS=Custom task failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
