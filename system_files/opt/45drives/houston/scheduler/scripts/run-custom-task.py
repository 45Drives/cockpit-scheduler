#!/usr/bin/env python3
"""Wrapper for CustomTask that sends sd_notify READY=1 before executing the user's command(s).

Supports multi-script mode via the CUSTOM_TASK_SCRIPTS env variable (JSON array of commands).
Execution mode is controlled by CUSTOM_TASK_EXEC_MODE: 'sequential' (default) or 'parallel'.

Legacy single-command mode (argv) is still supported for backward compatibility.
"""
import sys
import os
import subprocess
import traceback
import datetime as dt
import json
import concurrent.futures
import shlex

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


def run_single_command(command, notifier, label=""):
    """Run a single command (list of args). Returns the exit code."""
    prefix = f"[{label}] " if label else ""
    dbg(f"{prefix}running: {' '.join(command)}")
    notifier.notify(f"STATUS={prefix}Running: {' '.join(command)}")
    result = subprocess.run(command)
    dbg(f"{prefix}exit code: {result.returncode}")
    return result.returncode


def parse_script_entry(entry):
    """Parse a script entry (string or dict) into a command list.

    Supported formats:
      - str: a shell command string (parsed with shlex)
      - dict: {"filePath": "/path/to/script.sh"} or {"command": "echo hello"}
    """
    if isinstance(entry, str):
        return shlex.split(entry)
    if isinstance(entry, dict):
        fp = entry.get("filePath", "").strip()
        if fp:
            if fp.endswith(".py"):
                return ["python3", "-u", fp]
            else:
                return ["bash", fp]
        cmd = entry.get("command", "").strip()
        if cmd:
            return shlex.split(cmd)
    raise ValueError(f"Invalid script entry: {entry!r}")


def persist_lastrun():
    """Write the last-run timestamp file so the UI can show it."""
    try:
        import time as _time
        _task_name = os.environ.get("taskName", "").strip()
        if _task_name:
            _lr = f"/etc/systemd/system/houston_scheduler_CustomTask_{_task_name}.lastrun"
            with open(_lr, "w") as f:
                f.write(str(int(_time.time())))
    except Exception:
        pass


def main():
    notifier = get_notifier()
    try:
        # Check for multi-script mode via env
        scripts_json = os.environ.get("customTaskConfig_scripts", "").strip()
        exec_mode = os.environ.get("customTaskConfig_executionMode", "sequential").strip().lower()

        if scripts_json:
            # Multi-script mode
            try:
                scripts = json.loads(scripts_json)
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid scripts JSON: {e}", file=sys.stderr)
                sys.exit(1)

            if not isinstance(scripts, list) or len(scripts) == 0:
                print("ERROR: scripts must be a non-empty JSON array", file=sys.stderr)
                sys.exit(1)

            commands = []
            for i, entry in enumerate(scripts):
                try:
                    commands.append(parse_script_entry(entry))
                except ValueError as e:
                    print(f"ERROR: Script #{i+1}: {e}", file=sys.stderr)
                    sys.exit(1)

            dbg(f"=== multi-script custom task start === mode={exec_mode} scripts={len(commands)}")
            notifier.notify("READY=1")
            notifier.notify(f"STATUS=Running {len(commands)} script(s) ({exec_mode})")

            if exec_mode == "parallel":
                # Run all commands in parallel
                failed = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(commands)) as executor:
                    futures = {}
                    for i, cmd in enumerate(commands):
                        label = f"Script {i+1}/{len(commands)}"
                        futures[executor.submit(run_single_command, cmd, notifier, label)] = i

                    for future in concurrent.futures.as_completed(futures):
                        idx = futures[future]
                        try:
                            rc = future.result()
                            if rc != 0:
                                failed.append((idx + 1, rc))
                        except Exception as e:
                            failed.append((idx + 1, -1))
                            dbg(f"Script {idx+1} exception: {e}")

                if failed:
                    failed_str = ", ".join(f"#{n} (exit {rc})" for n, rc in failed)
                    notifier.notify(f"STATUS=Failed: {failed_str}")
                    dbg(f"multi-script parallel: failed={failed_str}")
                    sys.exit(1)
                else:
                    notifier.notify("STATUS=All scripts completed successfully")
                    dbg("=== multi-script parallel completed ===")
                    persist_lastrun()
                    sys.exit(0)
            else:
                # Sequential: run one by one, stop on first failure
                for i, cmd in enumerate(commands):
                    label = f"Script {i+1}/{len(commands)}"
                    rc = run_single_command(cmd, notifier, label)
                    if rc != 0:
                        notifier.notify(f"STATUS=Script {i+1}/{len(commands)} failed (exit {rc})")
                        dbg(f"multi-script sequential: script {i+1} failed with code {rc}")
                        sys.exit(rc)

                notifier.notify("STATUS=All scripts completed successfully")
                dbg("=== multi-script sequential completed ===")
                persist_lastrun()
                sys.exit(0)

        # Legacy single-command mode (argv)
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
            persist_lastrun()
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
