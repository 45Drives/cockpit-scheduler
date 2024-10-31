#!/usr/bin/env python3

import configparser
import sys
import json

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'

def update_rclone_remote(old_name, new_name, new_type, new_params):
    # Load the existing rclone config
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)

    # Check if the old_name exists in the config
    if old_name not in config:
        print(f"Remote '{old_name}' not found in {RCLONE_CONF_PATH}")
        return False

    # Remove the old section if the name has changed
    if old_name != new_name:
        config.remove_section(old_name)

    # Add or update the section with new name
    config[new_name] = {
        'type': new_type
    }
    # Update with new parameters
    for key, value in new_params.items():
        config[new_name][key] = json.dumps(value) if isinstance(value, dict) else str(value)

    # Write changes back to rclone.conf
    with open(RCLONE_CONF_PATH, 'w') as configfile:
        config.write(configfile)

    print(f"Remote '{old_name}' updated successfully as '{new_name}' in {RCLONE_CONF_PATH}")
    return True

def parse_arguments():
    if len(sys.argv) < 5:
        print("Usage: update_rclone_remote.py <old_name> <new_name> <new_type> <json_data>")
        sys.exit(1)
    old_name = sys.argv[1]
    new_name = sys.argv[2]
    new_type = sys.argv[3]
    new_params = json.loads(sys.argv[4])  # Use json.loads to convert JSON string to dictionary
    return old_name, new_name, new_type, new_params

if __name__ == "__main__":
    old_name, new_name, new_type, new_params = parse_arguments()
    update_rclone_remote(old_name, new_name, new_type, new_params)
