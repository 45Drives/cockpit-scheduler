#!/usr/bin/env bash
set -euo pipefail

# Installs the system-wide runtime required by the user-local scheduler-test UI.
# Package and remote installation paths intentionally do not call this script.

RESTART_COCKPIT="${1:-0}"
DESTDIR="${DESTDIR:-/}"

if [[ "$DESTDIR" != "/" ]]; then
    echo "install-local does not support DESTDIR; use make DESTDIR=<path> install for staged installs." >&2
    exit 1
fi

SUDO=()
if [[ "$(id -u)" -ne 0 ]]; then
    SUDO=(sudo)
fi

install_packages() {
    local package_manager="$1"
    shift

    "${SUDO[@]}" "$package_manager" install -y "$@"
}

if [[ -r /etc/os-release ]]; then
    . /etc/os-release
fi

case "${ID:-}" in
    debian)
        "${SUDO[@]}" apt-get update
        install_packages apt-get \
            cockpit-ws cockpit-bridge cockpit-system cockpit-storaged cockpit-packagekit \
            python3 rsync findutils smartmontools mbuffer pv rclone netcat-openbsd
        ;;
    ubuntu)
        "${SUDO[@]}" apt-get update
        install_packages apt-get \
            cockpit python3 rsync findutils smartmontools mbuffer pv rclone netcat-openbsd
        ;;
    rocky|rhel|centos|almalinux)
        if command -v dnf >/dev/null 2>&1; then
            install_packages dnf \
                cockpit python3 rsync findutils smartmontools mbuffer pv rclone netcat
        elif command -v yum >/dev/null 2>&1; then
            install_packages yum \
                cockpit python3 rsync findutils smartmontools mbuffer pv rclone netcat
        else
            echo "No supported RPM package manager found." >&2
            exit 1
        fi
        ;;
    *)
        echo "Unsupported distribution '${ID:-unknown}'. Install the dependencies from manifest.json, then install system_files/ manually." >&2
        exit 1
        ;;
esac

for command_name in python3 rsync find smartctl mbuffer pv rclone nc; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "Required command '$command_name' is unavailable after dependency installation." >&2
        exit 1
    fi
done

rclone_version="$(rclone version | awk 'NR == 1 { sub(/^rclone v/, ""); print $1 }')"
if [[ -z "$rclone_version" ]] || [[ "$(printf '%s\n%s\n' "1.59" "$rclone_version" | sort -V | head -n 1)" != "1.59" ]]; then
    echo "rclone 1.59 or newer is required; found '${rclone_version:-unknown}'." >&2
    exit 1
fi

echo "Installing scheduler system files..."
"${SUDO[@]}" cp -af system_files/* /

migrate_script="/opt/45drives/houston/scheduler/scripts/migrate-task-services.py"
if [[ -f "$migrate_script" ]]; then
    "${SUDO[@]}" python3 "$migrate_script" || true
fi

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable houston-scheduler-monitor.service
"${SUDO[@]}" systemctl restart houston-scheduler-monitor.service
"${SUDO[@]}" systemctl is-active --quiet houston-scheduler-monitor.service

if [[ "$RESTART_COCKPIT" == "1" ]]; then
    "${SUDO[@]}" systemctl restart cockpit.socket
fi

echo "Scheduler local runtime installation complete."