#!/usr/bin/env python3
import configparser

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'

def edit_remote_in_conf(name: str, updated_params: dict):
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)
    
    if not config.has_section(name):
        raise ValueError(f"Remote {name} does not exist")
    
    for key, value in updated_params.items():
        config.set(name, key, str(value))
    
    with open(RCLONE_CONF_PATH, 'w') as configfile:
        config.write(configfile)

if __name__ == "__main__":
    updated_params = {
        "token": '{"access_token":"new_token"}',
        "scope": "drive"
    }
    try:
        edit_remote_in_conf("My Google Drive", updated_params)
        print("Remote successfully updated.")
    except ValueError as e:
        print(e)
