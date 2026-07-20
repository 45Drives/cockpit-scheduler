"""Set a one-shot flag in a task's env file and optionally start the task.

Usage:
    python3 -c <script> <unit_name> <key> <value>

Example:
    python3 -c <script> houston_scheduler_ZfsReplicationTask_MyTask zfsRepConfig_sendOptions_dryRun true
"""
import subprocess
import sys
import os

def set_env_flag(unit_name, key, value):
    env_path = f"/etc/systemd/system/{unit_name}.env"
    if not os.path.isfile(env_path):
        print(f"error: env file not found: {env_path}", file=sys.stderr)
        sys.exit(1)

    with open(env_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        # Ensure we start on a new line if the file doesn't end with one
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    subprocess.run(["systemctl", "daemon-reload"], timeout=30)
    print(f"Set {key}={value} in {env_path}")


def main():
    if len(sys.argv) < 4:
        print("Usage: <script> <unit_name> <key> <value>", file=sys.stderr)
        sys.exit(1)

    unit_name = sys.argv[1]
    key = sys.argv[2]
    value = sys.argv[3]

    set_env_flag(unit_name, key, value)


if __name__ == "__main__":
    main()
