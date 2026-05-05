#!/usr/bin/env python3
"""
houston-scheduler-monitor
=========================
Watches systemd journal for Task Scheduler service completions and sends
alert notifications via the houston-notify D-Bus CLI.

Task types that already send their own houston-notify notifications
(ZfsReplicationTask, AutomatedSnapshotTask) are skipped to avoid
duplicate alerts.
"""

import subprocess
import json
import sys
import os
import signal
import time
import socket
from datetime import datetime, timezone

UNIT_PREFIX = "houston_scheduler_"
DBUS_SCRIPT = "/opt/45drives/houston/houston-notify"

# Task types whose scripts already call houston-notify internally
SELF_NOTIFYING_TYPES = {"ZfsReplicationTask", "AutomatedSnapshotTask"}

TASK_TYPE_LABELS = {
    "ZfsReplicationTask": "ZFS Replication",
    "AutomatedSnapshotTask": "Automated Snapshot",
    "RsyncTask": "Rsync",
    "ScrubTask": "ZFS Scrub",
    "SmartTestTask": "SMART Test",
    "CloudSyncTask": "Cloud Sync",
    "CustomTask": "Custom Task",
}


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
            capture_output=True, text=True, timeout=5,
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
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def send_notification(payload):
    """Forward notification to houston-notify D-Bus CLI."""
    try:
        subprocess.run(
            ["python3", DBUS_SCRIPT, json.dumps(payload)],
            timeout=10,
        )
    except Exception as e:
        print(f"[scheduler-monitor] houston-notify failed: {e}", file=sys.stderr, flush=True)


def handle_unit_completion(unit):
    """Process a scheduler unit that has finished (success or final failure)."""
    task_type, task_name = parse_unit_name(unit)

    # Skip types that already send their own notifications
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
        subject = f"Task Failed: {type_label} - {task_name} ({hostname})"
        body = (
            f"Task '{task_name}' ({type_label}) failed.\n\n"
            f"Server: {hostname} ({ip})\n"
            f"Result: {result}\n"
            f"Exit Code: {exit_code}\n"
            f"Started: {started}\n"
            f"Finished: {finished}\n"
        )
        if log_tail:
            body += f"\n--- Last log output ---\n{log_tail}\n"

    payload = {
        "timestamp": timestamp,
        "event": event,
        "taskName": task_name,
        "taskType": task_type,
        "severity": "error" if result != "success" else "info",
        "errors": f"Exit code: {exit_code}" if result != "success" else None,
        "subject": subject,
        "email_message": body,
    }

    send_notification(payload)
    print(f"[scheduler-monitor] Notification sent: {event} for {task_name} ({type_label})", flush=True)


def main():
    print("[scheduler-monitor] Starting Task Scheduler monitor daemon", flush=True)

    # Graceful shutdown on SIGTERM/SIGINT
    def _shutdown(signum, frame):
        print("[scheduler-monitor] Shutting down", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Follow the full journal in JSON format and filter in Python.
    # We look for systemd (PID 1) messages about our scheduler units
    # transitioning to "Deactivated successfully" or "Failed with result".
    proc = subprocess.Popen(
        [
            "journalctl", "-f", "-o", "json", "--no-pager",
            "SYSLOG_IDENTIFIER=systemd",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )

    # Triggers that indicate a unit has reached its final state
    # (not an intermediate restart — "Failed with result" is only emitted when
    # systemd gives up restarting)
    FINAL_TRIGGERS = (
        "Deactivated successfully",
        "Failed with result",
        "Succeeded.",
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

            if any(trigger in message for trigger in FINAL_TRIGGERS):
                # Small delay to let systemd finish recording result properties
                time.sleep(0.5)
                try:
                    handle_unit_completion(unit)
                except Exception as e:
                    print(
                        f"[scheduler-monitor] Error handling {unit}: {e}",
                        file=sys.stderr, flush=True,
                    )
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
