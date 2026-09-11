#!/usr/bin/env python3
"""
houston-scheduler-monitor
=========================
Watches systemd journal for Task Scheduler service completions and sends
alert notifications via the houston-notify D-Bus CLI.

Sends a "Failed — Retrying" notification on first failure when systemd
schedules a retry, then a final "Task Failed" notification when systemd
gives up retrying.
"""

import subprocess
import json
import re
import sys
import os
import signal
import time
import socket
from datetime import datetime, timezone

UNIT_PREFIX = "houston_scheduler_"
DBUS_SCRIPT = "/opt/45drives/houston/houston-notify"

# All task types now use the monitor for scheduler_task_failure/success notifications.
SELF_NOTIFYING_TYPES = set()

TASK_TYPE_LABELS = {
    "ZfsReplicationTask": "ZFS Replication",
    "AutomatedSnapshotTask": "Automated Snapshot",
    "RsyncTask": "Rsync",
    "ScrubTask": "ZFS Scrub",
    "SmartTestTask": "SMART Test",
    "CloudSyncTask": "Cloud Sync",
    "CustomTask": "Custom Task",
}

# Ordered most-specific-first; the first match wins.
FAILURE_SIGNATURES = [
    (r"no space left on device", "The destination ran out of disk space."),
    (r"disk quota exceeded", "The destination disk quota was exceeded."),
    (r"read-only file system", "The destination is mounted read-only."),
    (r"out of space|would exceed (?:the )?quota|storage quota (?:exceeded|reached)", "The destination is out of available space or quota."),
    (r"host key verification failed", "SSH host key verification failed for the destination server."),
    (r"permission denied \(publickey", "The destination server rejected the SSH key."),
    (r"connection refused", "The destination server refused the connection."),
    (r"connection timed out|operation timed out|timed out waiting for", "The connection to the destination server timed out."),
    (r"no route to host|network is unreachable|could not resolve hostname|name or service not known", "The destination server could not be reached."),
    (r"connection (?:closed|reset) by", "The destination server closed the connection unexpectedly."),
    (r"change_dir .*failed: no such file or directory", "The source folder no longer exists."),
    (r"(?:mkdir|opendir|link_stat|send_files|write failed on|failed to open).*permission denied", "Permission was denied while reading or writing files."),
    (r"permission denied", "Permission was denied."),
    (r"no such file or directory", "A file or folder in the transfer no longer exists."),
    (r"dataset does not exist", "The ZFS dataset does not exist."),
    (r"destination .*has been modified", "The destination dataset changed since the last run, so the incremental send was refused."),
    (r"could not find any snapshots to send|no snapshots? (?:found|to send)", "There were no snapshots available to replicate."),
    (r"pool i/o failure|cannot receive", "The destination pool rejected the replication stream."),
    (r"401 unauthorized|403 forbidden|invalid credentials|authentication failed|accessdenied", "The cloud provider rejected the stored credentials."),
    (r"didn't find section in config file|could not find remote|unknown remote", "The cloud remote is missing from the rclone configuration."),
    (r"bucket .*does not exist|nosuchbucket", "The destination bucket does not exist."),
    (r"out of memory|killed process|oom-killer", "The task was killed because the server ran out of memory."),
    (r"input/output error", "A disk I/O error occurred - the underlying storage may be failing."),
]

RSYNC_EXIT_CODES = {
    1: "rsync reported a syntax or usage error.",
    2: "rsync protocol incompatibility with the destination.",
    3: "rsync could not select the requested files or directories.",
    5: "rsync failed to start the client-server protocol.",
    10: "rsync hit a socket I/O error.",
    11: "rsync hit a file I/O error.",
    12: "rsync hit an error in the data stream.",
    13: "rsync reported an error with program diagnostics.",
    22: "rsync failed to allocate memory.",
    23: "Some files could not be transferred.",
    24: "Some source files vanished before they could be copied.",
    30: "rsync timed out sending or receiving data.",
    35: "rsync timed out waiting for a connection.",
}

# Track units currently in a failure/retry cycle.
# unit -> {"retrying_notified": bool, "retry_count": int}
# Present in dict = we saw "Failed with result" and are waiting for outcome.
_pending_failures = {}

# Units recently finalized — prevents duplicate notifications from the
# cluster of messages systemd emits when giving up (e.g. "Failed with result"
# immediately followed by "Start request repeated too quickly" + "Failed to start").
# unit -> monotonic timestamp when finalized
_recently_finalized = {}


def _get_server_identity():
    """Return (hostname, ip) for email context."""
    hostname = socket.getfqdn()
    try:
        ip = socket.gethostbyname(hostname)
        if ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            finally:
                s.close()
    except Exception:
        ip = "unknown"
    return hostname, ip


def parse_unit_name(unit):
    """Extract (task_type, task_name) from a unit name like
    houston_scheduler_RsyncTask_MyBackup.service"""
    name = unit
    if name.endswith(".service"):
        name = name[: -len(".service")]
    if name.startswith(UNIT_PREFIX):
        name = name[len(UNIT_PREFIX):]
    idx = name.find("_")
    if idx > 0:
        return name[:idx], name[idx + 1:]
    return name, "unknown"


def get_service_result(unit):
    """Query systemctl for the finished service's result."""
    try:
        result = subprocess.run(
            [
                "systemctl", "show", unit,
                "-p", "Result,ExecMainStatus,ActiveEnterTimestamp,InactiveEnterTimestamp",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=5,
        )
        props = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
        return props
    except Exception as e:
        print(f"[scheduler-monitor] systemctl show failed: {e}", file=sys.stderr, flush=True)
        return {}


def get_journal_tail(unit, lines=30):
    """Get the last N lines of journal output for the unit."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", unit, "--no-pager", "-n", str(lines), "--output=cat"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def summarize_failure(log_tail):
    """Name the cause of a failure from journal output.

    systemd only reports the wrapper script's exit status, which is almost always 1 and
    tells the user nothing. The actual reason is a single line in the log.
    """
    if not log_tail:
        return None
    for pattern, summary in FAILURE_SIGNATURES:
        match = re.search(pattern, log_tail, re.IGNORECASE)
        if match:
            line = log_tail[log_tail.rfind("\n", 0, match.start()) + 1:]
            newline = line.find("\n")
            return summary, (line if newline == -1 else line[:newline]).strip()

    match = re.search(r"\b(rsync|rclone)\s+exited\s+with\s+code\s+(\d+)", log_tail, re.IGNORECASE)
    if match:
        tool, code = match.group(1).lower(), int(match.group(2))
        summary = RSYNC_EXIT_CODES.get(code) if tool == "rsync" else None
        return summary or f"{tool} exited with code {code}.", match.group(0)

    return None


def send_notification(payload):
    """Forward notification to houston-notify D-Bus CLI."""
    try:
        subprocess.run(
            ["python3", DBUS_SCRIPT, json.dumps(payload)],
            timeout=10,
        )
    except Exception as e:
        print(f"[scheduler-monitor] houston-notify failed: {e}", file=sys.stderr, flush=True)


def send_final_notification(unit, retry_count=0):
    """Send a final success or failure notification for a completed unit.
    This notification persists to the alerts DB and triggers email."""
    task_type, task_name = parse_unit_name(unit)
    if task_type in SELF_NOTIFYING_TYPES:
        return

    props = get_service_result(unit)
    result = props.get("Result", "unknown")
    exit_code = props.get("ExecMainStatus", "unknown")
    started = props.get("ActiveEnterTimestamp", "")
    finished = props.get("InactiveEnterTimestamp", "")

    type_label = TASK_TYPE_LABELS.get(task_type, task_type)
    timestamp = datetime.now(timezone.utc).isoformat()
    hostname, ip = _get_server_identity()

    if result == "success":
        event = "scheduler_task_success"
        subject = f"Task Completed: {type_label} - {task_name} ({hostname})"
        body = (
            f"Task '{task_name}' ({type_label}) completed successfully.\n\n"
            f"Server: {hostname} ({ip})\n"
            f"Started: {started}\n"
            f"Finished: {finished}\n"
        )
    else:
        event = "scheduler_task_failure"
        log_tail = get_journal_tail(unit)
        diagnosis = summarize_failure(log_tail)
        retry_info = f" after {retry_count} {'retry' if retry_count == 1 else 'retries'}" if retry_count > 0 else ""
        subject = f"Task Failed: {type_label} - {task_name} ({hostname})"
        if diagnosis:
            # Put the cause in the subject so it's readable without opening the mail.
            subject += f" - {diagnosis[0].rstrip('.')}"
        body = (
            f"Task '{task_name}' ({type_label}) has failed{retry_info}.\n\n"
        )
        if diagnosis:
            body += f"Reason: {diagnosis[0]}\n"
            if diagnosis[1]:
                body += f"Log line: {diagnosis[1]}\n"
            body += "\n"
        body += (
            f"Server: {hostname} ({ip})\n"
            f"Result: {result}\n"
            f"Exit Code: {exit_code}\n"
            f"Retries attempted: {retry_count}\n"
            f"Started: {started}\n"
            f"Finished: {finished}\n"
        )
        if log_tail:
            body += f"\n--- Last log output ---\n{log_tail}\n"

    if result == "success":
        errors = None
    else:
        detail = diagnosis[0] if diagnosis else f"Exit code: {exit_code}"
        errors = (
            f"{detail} (after {retry_count} {'retry' if retry_count == 1 else 'retries'})"
            if retry_count > 0 else detail
        )

    payload = {
        "timestamp": timestamp,
        "event": event,
        "taskName": task_name,
        "taskType": task_type,
        "severity": "error" if result != "success" else "info",
        "errors": errors,
        "subject": subject,
        "email_message": body,
        "retryCount": retry_count,
    }
    if result != "success" and diagnosis:
        payload["reason"] = diagnosis[0]
        if diagnosis[1]:
            payload["reasonDetail"] = diagnosis[1]

    send_notification(payload)
    print(f"[scheduler-monitor] Notification sent: {event} for {task_name} ({type_label}) retries={retry_count}", flush=True)


def send_retrying_notification(unit):
    """Log that a retry is happening. No houston-notify call — the UI handles
    the 'retrying' toast via its own status polling."""
    task_type, task_name = parse_unit_name(unit)
    type_label = TASK_TYPE_LABELS.get(task_type, task_type)
    print(f"[scheduler-monitor] Task retrying: {task_name} ({type_label})", flush=True)


def main():
    print("[scheduler-monitor] Starting Task Scheduler monitor daemon", flush=True)

    def _shutdown(signum, frame):
        print("[scheduler-monitor] Shutting down", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    proc = subprocess.Popen(
        [
            "journalctl", "-f", "-o", "json", "--no-pager",
            "SYSLOG_IDENTIFIER=systemd",
        ],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )

    try:
        for line in proc.stdout:
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            unit = entry.get("UNIT", "")
            message = entry.get("MESSAGE", "")

            if not unit.startswith(UNIT_PREFIX):
                continue
            if not unit.endswith(".service"):
                continue

            # --- Success: task completed normally ---
            if "Deactivated successfully" in message or "Succeeded." in message:
                _pending_failures.pop(unit, None)
                _recently_finalized[unit] = time.monotonic()
                time.sleep(0.5)
                try:
                    send_final_notification(unit)
                except Exception as e:
                    print(f"[scheduler-monitor] Error handling {unit}: {e}",
                          file=sys.stderr, flush=True)
                continue

            # --- Process failed (emitted on EVERY failure exit) ---
            if "Failed with result" in message:
                # Skip if this unit was just finalized (systemd emits multiple
                # messages in a burst when giving up on retries)
                finalized_at = _recently_finalized.get(unit, 0)
                if time.monotonic() - finalized_at < 5:
                    continue
                # Just record that this unit has failed. Don't send anything yet.
                if unit not in _pending_failures:
                    _pending_failures[unit] = {"retrying_notified": False, "retry_count": 0}
                continue

            # --- Systemd is scheduling a retry ---
            if "Scheduled restart job" in message:
                state = _pending_failures.get(unit)
                if state:
                    state["retry_count"] = state.get("retry_count", 0) + 1
                    if not state["retrying_notified"]:
                        state["retrying_notified"] = True
                        try:
                            send_retrying_notification(unit)
                        except Exception as e:
                            print(f"[scheduler-monitor] Error sending retry notif for {unit}: {e}",
                                  file=sys.stderr, flush=True)
                continue

            # --- Systemd gave up retrying (final failure) ---
            if "Start request repeated too quickly" in message or "Failed to start" in message:
                # Only send if we have pending state (prevents duplicates from
                # the burst of messages systemd emits)
                if unit not in _pending_failures:
                    continue
                retry_count = _pending_failures[unit].get("retry_count", 0)
                _pending_failures.pop(unit, None)
                _recently_finalized[unit] = time.monotonic()
                time.sleep(0.5)
                try:
                    send_final_notification(unit, retry_count=retry_count)
                except Exception as e:
                    print(f"[scheduler-monitor] Error handling final failure {unit}: {e}",
                          file=sys.stderr, flush=True)
                continue

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    main()
