#!/usr/bin/env python3
"""
migrate-retry-settings.py
==========================
Reads retry settings from scheduler.conf and patches all existing
houston_scheduler_*.service files in /etc/systemd/system/.

Also supports reading/writing the config file as JSON for the UI.

Usage:
  python3 migrate-retry-settings.py --migrate
  python3 migrate-retry-settings.py --get
  python3 migrate-retry-settings.py --set '{"restart_sec":5,"start_limit_burst":2,"start_limit_interval_sec":15}'
"""

import argparse
import configparser
import glob
import json
import os
import re
import subprocess
import sys

CONF_PATH = "/opt/45drives/houston/scheduler/scheduler.conf"
SERVICE_GLOB = "/etc/systemd/system/houston_scheduler_*.service"

DEFAULTS = {
    "restart_sec": 5,
    "start_limit_burst": 3,
    "ui_status_poll_ms": 5000,
    "ui_progress_poll_ms": 10000,
}


def read_config():
    """Read retry settings from scheduler.conf, falling back to defaults.
    StartLimitIntervalSec is auto-calculated."""
    config = configparser.ConfigParser()
    if os.path.exists(CONF_PATH):
        config.read(CONF_PATH)

    section = "retry"
    restart_sec = config.getint(section, "restart_sec", fallback=DEFAULTS["restart_sec"])
    start_limit_burst = config.getint(section, "start_limit_burst", fallback=DEFAULTS["start_limit_burst"])
    # Auto-calculate: window must be large enough to contain all burst attempts
    start_limit_interval_sec = (start_limit_burst + 1) * restart_sec
    ui_status_poll_ms = config.getint("ui", "status_poll_ms", fallback=DEFAULTS["ui_status_poll_ms"])
    ui_progress_poll_ms = config.getint("ui", "progress_poll_ms", fallback=DEFAULTS["ui_progress_poll_ms"])

    # Clamp to sane minima to avoid accidental UI overload.
    ui_status_poll_ms = max(1000, ui_status_poll_ms)
    ui_progress_poll_ms = max(1000, ui_progress_poll_ms)

    return {
        "restart_sec": restart_sec,
        "start_limit_burst": start_limit_burst,
        "start_limit_interval_sec": start_limit_interval_sec,
        "ui_status_poll_ms": ui_status_poll_ms,
        "ui_progress_poll_ms": ui_progress_poll_ms,
    }


def write_config(settings):
    """Write retry settings to scheduler.conf (only restart_sec and start_limit_burst)."""
    config = configparser.ConfigParser()
    if os.path.exists(CONF_PATH):
        config.read(CONF_PATH)

    if not config.has_section("retry"):
        config.add_section("retry")
    if not config.has_section("ui"):
        config.add_section("ui")

    config.set("retry", "restart_sec", str(settings["restart_sec"]))
    config.set("retry", "start_limit_burst", str(settings["start_limit_burst"]))
    config.set("ui", "status_poll_ms", str(settings["ui_status_poll_ms"]))
    config.set("ui", "progress_poll_ms", str(settings["ui_progress_poll_ms"]))
    # Remove stale start_limit_interval_sec if present (now auto-calculated)
    if config.has_option("retry", "start_limit_interval_sec"):
        config.remove_option("retry", "start_limit_interval_sec")

    os.makedirs(os.path.dirname(CONF_PATH), exist_ok=True)
    with open(CONF_PATH, "w") as f:
        f.write("# Houston Scheduler Global Settings\n\n")
        config.write(f)


def patch_service_file(path, settings):
    """Patch a single .service file with the new retry settings."""
    with open(path, "r") as f:
        content = f.read()

    original = content

    # Patch StartLimitBurst
    content = re.sub(
        r"^StartLimitBurst=.*$",
        f"StartLimitBurst={settings['start_limit_burst']}",
        content,
        flags=re.MULTILINE,
    )

    # Patch StartLimitIntervalSec
    content = re.sub(
        r"^StartLimitIntervalSec=.*$",
        f"StartLimitIntervalSec={settings['start_limit_interval_sec']}",
        content,
        flags=re.MULTILINE,
    )

    # Patch RestartSec
    content = re.sub(
        r"^RestartSec=.*$",
        f"RestartSec={settings['restart_sec']}sec",
        content,
        flags=re.MULTILINE,
    )

    if content != original:
        with open(path, "w") as f:
            f.write(content)
        return True
    return False


def migrate_all(settings):
    """Patch all existing scheduler service files and reload systemd."""
    files = glob.glob(SERVICE_GLOB)
    patched = 0
    for path in files:
        if patch_service_file(path, settings):
            patched += 1

    if patched > 0:
        subprocess.run(["systemctl", "daemon-reload"], check=True)

    return {"patched": patched, "total": len(files)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true", help="Migrate all existing service files")
    parser.add_argument("--get", action="store_true", help="Print current settings as JSON")
    parser.add_argument("--set", type=str, help="Set retry settings from JSON string")
    args = parser.parse_args()

    if args.get:
        print(json.dumps(read_config()))
    elif args.set:
        incoming = json.loads(args.set)
        settings = read_config()
        # Merge incoming values so partial UI saves don't reset retry settings, and vice versa.
        for key, value in incoming.items():
            settings[key] = value

        # Validate retry values
        settings["restart_sec"] = max(1, int(settings.get("restart_sec", DEFAULTS["restart_sec"])))
        settings["start_limit_burst"] = max(1, int(settings.get("start_limit_burst", DEFAULTS["start_limit_burst"])))

        # Validate UI polling values
        settings["ui_status_poll_ms"] = max(1000, int(settings.get("ui_status_poll_ms", DEFAULTS["ui_status_poll_ms"])))
        settings["ui_progress_poll_ms"] = max(1000, int(settings.get("ui_progress_poll_ms", DEFAULTS["ui_progress_poll_ms"])))

        # Auto-calculate interval
        settings["start_limit_interval_sec"] = (settings["start_limit_burst"] + 1) * settings["restart_sec"]
        write_config(settings)
        print(json.dumps({"success": True, "settings": settings}))
    elif args.migrate:
        settings = read_config()
        result = migrate_all(settings)
        print(json.dumps({"success": True, **result, "settings": settings}))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
