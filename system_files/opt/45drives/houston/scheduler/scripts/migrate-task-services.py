#!/usr/bin/env python3
"""
Migration script: regenerates all houston_scheduler .service files
to pick up the latest ExecStart logic (scrub script fix, custom task wrapper, etc.)

Usage:
    sudo python3 /opt/45drives/houston/scheduler/scripts/migrate-task-services.py [--dry-run]
"""
import glob
import os
import re
import subprocess
import sys

SYSTEMD_DIR = "/etc/systemd/system"
ENV_GLOB = os.path.join(SYSTEMD_DIR, "houston_scheduler_*.env")
SCRIPTS_DIR = "/opt/45drives/houston/scheduler/scripts"
TASK_FILE_CREATION = os.path.join(SCRIPTS_DIR, "task-file-creation.py")
SERVICE_TEMPLATE = "/opt/45drives/houston/scheduler/templates/Task.service"

# Same mapping as Scheduler.ts getScriptFromTemplateName()
TEMPLATE_TO_SCRIPT = {
    "ZfsReplicationTask": "replication-script.py",
    "AutomatedSnapshotTask": "autosnap-script.py",
    "RsyncTask": "rsync-script.py",
    "SmartTest": "smart-test-script.py",
    "ScrubTask": "scrub-script.py",
    "CloudSyncTask": "cloudsync-script.py",
    "CustomTask": "run-custom-task.py",  # wrapper handles custom commands
}

# Filename pattern: houston_scheduler_{TemplateName}_{TaskInstanceName}.env
# TemplateName is one of the keys above (PascalCase, no underscores in it)
ENV_RE = re.compile(
    r"^houston_scheduler_("
    + "|".join(re.escape(k) for k in TEMPLATE_TO_SCRIPT)
    + r")_(.+)\.env$"
)


def get_template_and_task(env_filename):
    """Extract (templateName, taskInstanceName) from an env filename."""
    m = ENV_RE.match(env_filename)
    if m:
        return m.group(1), m.group(2)
    return None, None


def main():
    dry_run = "--dry-run" in sys.argv

    env_files = sorted(glob.glob(ENV_GLOB))
    if not env_files:
        print("No houston_scheduler env files found. Nothing to migrate.")
        return

    migrated = []
    skipped = []
    errors = []

    for env_path in env_files:
        env_filename = os.path.basename(env_path)
        template_name, task_name = get_template_and_task(env_filename)

        if not template_name:
            skipped.append((env_filename, "could not parse template name from filename"))
            continue

        script_file = TEMPLATE_TO_SCRIPT.get(template_name)
        if not script_file:
            skipped.append((env_filename, f"unknown template '{template_name}'"))
            continue

        script_path = os.path.join(SCRIPTS_DIR, script_file)
        service_name = f"houston_scheduler_{template_name}_{task_name}.service"
        service_path = os.path.join(SYSTEMD_DIR, service_name)

        if not os.path.exists(service_path):
            skipped.append((env_filename, f"no matching service file ({service_name})"))
            continue

        print(f"{'[DRY RUN] ' if dry_run else ''}Migrating: {service_name}")
        print(f"  template={template_name}  script={script_file}")

        if dry_run:
            migrated.append(service_name)
            continue

        # Re-run task-file-creation.py to regenerate the .service file
        cmd = [
            "python3", TASK_FILE_CREATION,
            "-t", "create-task",
            "-tN", template_name,
            "-sP", script_path,
            "-e", env_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err_msg = result.stderr.strip() or result.stdout.strip()
            errors.append((service_name, err_msg))
            print(f"  ERROR: {err_msg}")
        else:
            migrated.append(service_name)
            print(f"  OK")

    # daemon-reload once after all service files are updated
    if migrated and not dry_run:
        print("\nRunning systemctl daemon-reload...")
        subprocess.run(["systemctl", "daemon-reload"], check=True)

    # Summary
    print(f"\n{'=== DRY RUN Summary ===' if dry_run else '=== Migration Summary ==='}")
    print(f"  Migrated: {len(migrated)}")
    for name in migrated:
        print(f"    {name}")
    if skipped:
        print(f"  Skipped:  {len(skipped)}")
        for name, reason in skipped:
            print(f"    {name}: {reason}")
    if errors:
        print(f"  Errors:   {len(errors)}")
        for name, err in errors:
            print(f"    {name}: {err}")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
