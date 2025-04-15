#!/usr/bin/env python3
import configparser
import json

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'

class CloudSyncRemote:
    def __init__(self, name, type, parameters):
        self.name = name
        self.type = type
        self.parameters = parameters
    
    def __str__(self):
        params_str = '\n'.join([f"  {key}: {value}" for key, value in self.parameters.items()])
        return f"name: {self.name}\ntype: {self.type}\parameters:\n{params_str}\n"

def load_remotes_from_conf():
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)
    
    remotes = []
    
    for section in config.sections():
        type = config.get(section, 'type', fallback='unknown')
        parameters = {key: value for key, value in config.items(section) if key != 'type'}
        remote = CloudSyncRemote(name=section, type=type, parameters=parameters)
        remotes.append(remote)
    
    return json.dumps([remote.__dict__ for remote in remotes], indent=4)

def main():
    remotes = load_remotes_from_conf()
    print(remotes)

if __name__ == "__main__":
    main()