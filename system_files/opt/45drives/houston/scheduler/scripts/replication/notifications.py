"""Houston notification integration."""

import json
import subprocess

def send_houston_notification(payload):
    try:
        dbus_script = "/opt/45drives/houston/houston-notify"
        debug_log = "/tmp/zfs_replication_debug.log"
        with open(debug_log, "a") as log_fh:
            subprocess.run(
                ["python3", dbus_script, json.dumps(payload)],
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )
    except Exception as notify_error:
        print(f"Failed to send D-Bus notification: {notify_error}")

