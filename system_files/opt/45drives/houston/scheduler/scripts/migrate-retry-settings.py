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
    "start_limit_burst": 2,
    "start_limit_interval_sec": 15,
}


def read_config():
    """Read retry settings from scheduler.conf, falling back to defaults."""
    config = configparser.ConfigParser()
    if os.path.exists(CONF_PATH):
        config.read(CONF_PATH)

    section = "retry"
    return {
        "restart_sec": config.getint(section, "restart_sec", fallback=DEFAULTS["restart_sec"]),
        "start_limit_burst": config.getint(section, "start_limit_burst", fallback=DEFAULTS["start_limit_burst"]),
        "start_limit_interval_sec": config.getint(section, "start_limit_interval_sec", fallback=DEFAULTS["start_limit_interval_sec"]),
    }


def write_config(settings):
    """Write retry settings to scheduler.conf."""
    config = configparser.ConfigParser()
    if os.path.exists(CONF_PATH):
        config.read(CONF_PATH)

    if not config.has_section("retry"):
        config.add_section("retry")

    config.set("retry", "restart_sec", str(settings["restart_sec"]))
    config.set("retry", "start_limit_burst", str(settings["start_limit_burst"]))
    config.set("retry", "start_limit_interval_sec", str(settings["start_limit_interval_sec"]))

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
        settings = json.loads(args.set)
        # Validate
        for key in DEFAULTS:
            if key not in settings:
                settings[key] = DEFAULTS[key]
            settings[key] = max(1, int(settings[key]))
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
