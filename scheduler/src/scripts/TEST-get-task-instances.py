import os
import json
import re

def extract_env_data(env_file_path):
    env_data = {}
    with open(env_file_path, 'r') as env_file:
        for line in env_file:
            if line.strip() and '=' in line:
                key, value = line.strip().split('=', 1)
                keys = key.split('_')
                current_node = env_data
                for k in keys[:-1]:
                    current_node = current_node.setdefault(k, {})
                current_node[keys[-1]] = value
    return env_data

def compare_files(system_dir, templates_dir):
    systemd_files = os.listdir(system_dir)
    template_files = os.listdir(templates_dir)
    
    service_files = [file for file in systemd_files if file.endswith('.service')]
    timer_files = [file for file in systemd_files if file.endswith('.timer')]
    env_files = [file for file in systemd_files if file.endswith('.env')]
        
    extracted_data = {}
    
    # Iterate over env files and extract data
    for env_file in env_files:
        service_name = env_file.split('.')[0]
        data = extract_env_data(os.path.join(system_dir, env_file))
        
    