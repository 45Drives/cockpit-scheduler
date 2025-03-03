#!/usr/bin/env python3
import argparse
import configparser
import json

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'

def edit_remote_in_conf(old_name, updated_remote):
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)

    new_name = updated_remote["name"]
    remote_type = updated_remote["type"]
    auth_params = updated_remote["authParams"]

    # Check if the old remote exists
    if not config.has_section(old_name):
        raise ValueError(f"Remote '{old_name}' not found")

    # Rename the section if the name has changed
    if old_name != new_name:
        config[new_name] = config[old_name]
        config.remove_section(old_name)

    # Set the type of the remote
    config.set(new_name, 'type', remote_type)

    # Process and set each parameter from authParams, skipping empty values
    for key, value in auth_params.items():
        if isinstance(value, dict):
            value = value.get("value", "")
        if value:  # Skip empty values
            config.set(new_name, key, str(value))

    # Write changes to the config file
    with open(RCLONE_CONF_PATH, 'w') as configfile:
        config.write(configfile)

    print(f"Remote '{old_name}' successfully edited and saved as '{new_name}' in {RCLONE_CONF_PATH}")

def main():
    parser = argparse.ArgumentParser(description="Edit an existing CloudSyncRemote in rclone.conf")
    parser.add_argument('--old_name', type=str, required=True, help="Existing remote name to be edited")
    parser.add_argument('--data', type=str, required=True, help="JSON string of updated CloudSyncRemote data")

    args = parser.parse_args()
    try:
        updated_remote_data = json.loads(args.data)  # Parse JSON string to dictionary
        edit_remote_in_conf(args.old_name, updated_remote_data)
    except ValueError as e:
        print(e)
    except json.JSONDecodeError:
        print("Invalid JSON format for --data argument")

if __name__ == "__main__":
    main()
