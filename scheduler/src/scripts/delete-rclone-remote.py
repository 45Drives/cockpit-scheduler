#!/usr/bin/env python3
import configparser
import sys
import os

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'

def delete_remote(remote_name):
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)

    # Check if the remote exists in the config
    if remote_name not in config.sections():
        print(f"Remote '{remote_name}' not found.")
        return
    
    # Remove the section for the remote
    config.remove_section(remote_name)
    
    # Write the updated config back to file
    with open(RCLONE_CONF_PATH, 'w') as configfile:
        config.write(configfile)
    print(f"Remote '{remote_name}' deleted successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: delete_remote.py <remote_name>")
        sys.exit(1)
    
    remote_name = sys.argv[1]
    delete_remote(remote_name)
