import subprocess
import argparse
import re
import json
import os
import datetime

""" def extract_env_data(env_file_path):
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
        
     """


def read_template_service_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()


def extract_description(template_content):
    for line in template_content.split('\n'):
        if line.startswith('Description='):
            return line.split('=', 1)[1]
    return None


def parse_env_file(env_file_path):
    parameters = {}
    with open(env_file_path, "r") as f:
        for line in f:
            key, value = line.strip().split('=')
            parameters[key] = value
        
        # special parsing for zfsRepConfig
        if key.split('_')[0] == 'zfsRepConfig':
            if parameters[f'zfsRepConfig_sendOptions_raw_flag'] == True:
                    parameters[f'zfsRepConfig_sendOptions_compressed_flag'] = False
            elif parameters[f'zfsRepConfig_sendOptions_compressed_flag'] == True:
                parameters[f'zfsRepConfig_sendOptions_raw_flag'] = False
                
            flags = ['recursive', 'customName', 'raw', 'compressed']
            for flag in flags:
                if f'zfsRepConfig_sendOptions_{flag}_flag' in parameters and parameters[f'zfsRepConfig_sendOptions_{flag}_flag'].lower() == 'true':
                    parameters[f'zfsRepConfig_sendOptions_{flag}_flag'] = f"--{flag}"
                else:
                    parameters[f'zfsRepConfig_sendOptions_{flag}_flag'] = ""
        
    return parameters


def replace_placeholders(template_content, parameters):
    for key, value in parameters.items():
        placeholder = "{" + key + "}"
        template_content = template_content.replace(placeholder, value)
    return template_content


def generate_concrete_service_file(template_content, output_file_path):
    with open(output_file_path, 'w') as file:
        file.write(template_content)

def main():
    # parser = argparse.ArgumentParser(description='Generate Service + Timer Files from Template + Env Files')
    # parser.add_argument('-t', '--template', type=str, nargs=1, help='template service file path')
    # parser.add_argument('-e', '--env', type=str, nargs=1, help='env file path')
    # parser.add_argument('schedule', type=str, nargs='?', help='schedule object as string')
    # args = parser.parse_args()
    # template_path = args.template
    # env_path = args.env
    # schedule_string = args.schedule
    # env_filename = env_path.split('/')[-1]
    # id_number = env_filename.split('_')[1]
    # task_name = template_path.split('/')[-1].split('.')[0]
    # output_path_service = f"/etc/systemd/system/{task_name}_{id_number}.service"
    # output_path_timer = f"/etc/systemd/system/{task_name}_{id_number}.timer"
    # schedule = parse_task_schedule_from_string(schedule_string)
    # template_content = read_template_service_file(template_file_path)
    # task_name = extract_description(template_content)
    
    
    # Define file paths (testing)
    template_file_path = "/opt/45drives/houston/scheduler/templates/ZfsReplicationTask.service"
    env_file_path = "/etc/systemd/system/houston_scheduler_ZfsReplicationTask_0.env"
    output_file_path = "/etc/systemd/system/houston_scheduler_ZfsReplicationTask_0.service"
    template_content = read_template_service_file(template_file_path)

    # Parse keys/values from environment file
    parameters = parse_env_file(env_file_path)

    # Replace placeholders in service file template with environment variables
    template_content = replace_placeholders(template_content, parameters)
    template_content = template_content.replace("{env_path}", env_file_path)

    # Generate concrete service file
    generate_concrete_service_file(template_content, output_file_path)
    print(template_content)
    print("Concrete service file generated successfully.")

    
if __name__ == "__main__":
	main()