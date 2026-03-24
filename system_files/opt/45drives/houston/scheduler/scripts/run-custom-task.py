#!/usr/bin/env python3
"""Wrapper for CustomTask that sends sd_notify READY=1 before executing the user's command."""
import sys
import os
import subprocess

from notify import get_notifier

def main():
    if len(sys.argv) < 2:
        print("ERROR: No command provided to run-custom-task.py", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1:]
    notifier = get_notifier()

    notifier.notify("READY=1")
    notifier.notify(f"STATUS=Running: {' '.join(command)}")

    result = subprocess.run(command)

    if result.returncode == 0:
        notifier.notify("STATUS=Completed successfully")
    else:
        notifier.notify(f"STATUS=Exited with code {result.returncode}")

    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
