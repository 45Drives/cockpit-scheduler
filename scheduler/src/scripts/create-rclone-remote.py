#!/usr/bin/env python3
import argparse
import configparser
import json
from pathlib import Path

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'
CLIENT_CREDS_PATH = '/etc/45drives/houston/cloud-sync-client-creds.json'

def load_client_creds():
    path = Path(CLIENT_CREDS_PATH)
    if not path.exists():
        return {}
    try:
        with path.open('r') as f:
            return json.load(f)
    except Exception:
        # Fail soft: if creds file is broken, just act as if no defaults
        return {}
    
def save_remote_to_conf(remote):
    config_path = Path(RCLONE_CONF_PATH)

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the file if it does not exist
    if not config_path.exists():
        # Touch the file (empty file is fine; configparser will overwrite later)
        config_path.touch()
        print(f'Rclone conf file created at {config_path}')
    else:
        print(f'Rclone conf file exists at {config_path}')
        
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)

    name = remote["name"]
    remote_type = remote["type"]
    auth_params = remote["authParams"]

    if config.has_section(name):
        raise ValueError(f"Remote '{name}' already exists")

    # Add new remote section
    config.add_section(name)
    config.set(name, 'type', remote_type)

    for key, value in auth_params.items():
        if isinstance(value, dict):
            # Convert dictionary to JSON string
            value = json.dumps(value)
        if value:  # Skip empty values
            config.set(name, key, str(value))

    # Write changes to the config file in write mode to avoid duplication
    with open(RCLONE_CONF_PATH, 'w') as configfile:
        config.write(configfile)

    print(f"Remote '{name}' successfully created and saved to {RCLONE_CONF_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Save a CloudSyncRemote to rclone.conf")
    parser.add_argument('--data', type=str, required=True, help="JSON string of CloudSyncRemote data")

    args = parser.parse_args()
    try:
        remote_data = json.loads(args.data)  # Parse JSON string to dictionary
        save_remote_to_conf(remote_data)
    except ValueError as e:
        print(e)
    except json.JSONDecodeError:
        print("Invalid JSON format for --data argument")

if __name__ == "__main__":
    main()
