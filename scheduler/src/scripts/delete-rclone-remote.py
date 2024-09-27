#!/usr/bin/env python3
import configparser

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'

def delete_remote_from_conf(name: str):
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)
    
    if config.has_section(name):
        config.remove_section(name)
    else:
        raise ValueError(f"Remote {name} does not exist")

    with open(RCLONE_CONF_PATH, 'w') as configfile:
        config.write(configfile)

if __name__ == "__main__":
    try:
        delete_remote_from_conf("My Google Drive")
        print("Remote successfully deleted.")
    except ValueError as e:
        print(e)
