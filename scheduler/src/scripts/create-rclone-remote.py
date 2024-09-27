#!/usr/bin/env python3
import configparser

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf' 

def save_remote_to_conf(name: str, remote_type: str, params: dict):
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)
    
    if config.has_section(name):
        raise ValueError(f"Remote {name} already exists")

    config.add_section(name)
    config.set(name, 'type', remote_type)
    
    for key, value in params.items():
        config.set(name, key, str(value))
    
    with open(RCLONE_CONF_PATH, 'w') as configfile:
        config.write(configfile)

if __name__ == "__main__":
    new_remote_params = {
        "account": "myaccount",
        "token": "{}",
        "scope": "drive"
    }
    try:
        save_remote_to_conf("My Google Drive", "drive", new_remote_params)
        print("Remote successfully created.")
    except ValueError as e:
        print(e)
