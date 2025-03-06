#!/usr/bin/env python3
import argparse
import configparser
import json

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'

def save_remote_to_conf(remote):
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
