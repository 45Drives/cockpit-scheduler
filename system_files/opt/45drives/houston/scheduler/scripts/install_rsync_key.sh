#!/bin/bash
set -e

KEY_PATH="/etc/45drives/houston/scheduler/ssh/rsync_key"
USER_HOST="$1"

if [ -z "$USER_HOST" ]; then
    echo "Usage: $0 user@host"
    exit 1
fi

if ! command -v ssh-keygen >/dev/null 2>&1; then
    echo "Error: ssh-keygen not found. Install OpenSSH client tools."
    exit 1
fi

if ! command -v ssh-copy-id >/dev/null 2>&1; then
    echo "Error: ssh-copy-id not found. Install OpenSSH client tools."
    exit 1
fi

if [ ! -f "$KEY_PATH.pub" ]; then
    echo "Scheduler key not found at $KEY_PATH.pub, generating..."
    mkdir -p "$(dirname "$KEY_PATH")"
    chmod 700 "$(dirname "$KEY_PATH")"
    ssh-keygen -t ed25519 -f "$KEY_PATH" -N ''
else
    echo "Scheduler key already exists at $KEY_PATH.pub"
fi

echo "Installing scheduler rsync key to $USER_HOST..."
ssh-copy-id -i "$KEY_PATH.pub" "$USER_HOST"
