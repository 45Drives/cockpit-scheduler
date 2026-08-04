"""Receive-resume tokens and durable one-shot task state."""

import datetime
import json
import os
import subprocess
import sys

from .logging_utils import dbg
from .ssh import ssh_run_args

_ONE_SHOT_KEYS = [
    "zfsRepConfig_sendOptions_forceFullSend",
    "zfsRepConfig_sendOptions_dryRun",
    "zfsRepConfig_sendOptions_resumeOnly",
]

def get_receive_resume_token(dest_filesystem, remote_user=None, remote_host=None, remote_port="22"):
    base_args = ["zfs", "get", "-H", "-o", "value", "receive_resume_token", dest_filesystem]
    if remote_host:
        p = ssh_run_args(remote_user, remote_host, remote_port, base_args, capture_output=True, check=False, text=True)
        if p.returncode != 0:
            return ""
        token = (p.stdout or "").strip()
    else:
        p = subprocess.run(base_args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            return ""
        token = (p.stdout or "").strip()

    return "" if token in ("", "-") else token


def clear_receive_resume_token(dest_filesystem, remote_user=None, remote_host=None, remote_port="22"):
    base_cmd = ["zfs", "receive", "-A", dest_filesystem]
    if remote_host:
        p = ssh_run_args(remote_user, remote_host, remote_port, base_cmd, capture_output=True, check=False, text=True)
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            return False, err
        return True, ""
    else:
        p = subprocess.run(base_cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()
            return False, err
        return True, ""


def _clear_one_shot_flags(task_name: str, keys=None):
    """Reset one-shot flags in the task env file so they only fire once."""
    if keys is None:
        keys = _ONE_SHOT_KEYS
    env_path = f"/etc/systemd/system/houston_scheduler_ZfsReplicationTask_{task_name}.env"
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
        new_lines = []
        cleared_flags = []
        for line in lines:
            stripped = line.strip()
            matched = False
            for key in keys:
                if stripped.startswith(f"{key}="):
                    val = stripped.split("=", 1)[1].strip().lower()
                    if val not in ("false", "0", "no", "off", ""):
                        short_name = key.rsplit("_", 1)[-1]
                        cleared_flags.append(short_name)
                    new_lines.append(f"{key}=false\n")
                    matched = True
                    break
                # Handle corrupted lines where the key got concatenated onto a previous value
                if f"{key}=" in stripped and not stripped.startswith(f"{key}="):
                    idx = stripped.index(f"{key}=")
                    prefix = stripped[:idx]
                    new_lines.append(f"{prefix}\n")
                    new_lines.append(f"{key}=false\n")
                    short_name = key.rsplit("_", 1)[-1]
                    cleared_flags.append(short_name)
                    matched = True
                    break
            if not matched:
                new_lines.append(line)
        if cleared_flags:
            with open(env_path, "w") as f:
                f.writelines(new_lines)
            print(f"One-shot flags cleared ({', '.join(cleared_flags)}) — next run will use normal mode.")
            subprocess.run(["systemctl", "daemon-reload"], timeout=30)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"WARNING: could not clear one-shot flags: {e}", file=sys.stderr)


def _pending_full_send_path(task_name: str) -> str:
    return f"/etc/systemd/system/houston_scheduler_ZfsReplicationTask_{task_name}.fullsend"


def _write_pending_full_send(task_name: str, snapshot_name: str, dest_filesystem: str,
                              direction: str, source_filesystem: str):
    """Record that a full send is in progress so interrupted sends can be continued."""
    if not task_name:
        return
    path = _pending_full_send_path(task_name)
    state = {
        "snapshot": snapshot_name,
        "destFilesystem": dest_filesystem,
        "sourceFilesystem": source_filesystem,
        "direction": direction,
        "startedAt": datetime.datetime.now().isoformat(),
    }
    try:
        with open(path, "w") as f:
            json.dump(state, f)
        dbg(f"Wrote pending full send state: {state}")
    except Exception as e:
        print(f"WARNING: could not write pending full send state: {e}")


def _read_pending_full_send(task_name: str):
    """Read pending full send state. Returns dict or None."""
    if not task_name:
        return None
    path = _pending_full_send_path(task_name)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        dbg(f"WARNING: could not read pending full send state: {e}")
        return None


def _clear_pending_full_send(task_name: str):
    """Remove the pending full send state file after successful completion."""
    if not task_name:
        return
    path = _pending_full_send_path(task_name)
    try:
        os.remove(path)
        dbg("Cleared pending full send state.")
    except FileNotFoundError:
        pass
    except Exception as e:
        dbg(f"WARNING: could not clear pending full send state: {e}")

