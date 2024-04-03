import subprocess
import argparse
import re
import json
import os
import datetime

def read_template_service_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()

def parse_env_file(env_file_path):
    parameters = {}
    with open(env_file_path, "r") as f:
        for line in f:
            key, value = line.strip().split('=')
            parameters[key] = value
        
        # special parsing for zfsRepConfig
        if key.split('_')[0] == 'zfsRepConfig':
            flags = ['recursive', 'customName']
            for flag in flags:
                if f'zfsRepConfig_sendOptions_{flag}_flag' in parameters and parameters[f'zfsRepConfig_sendOptions_{flag}_flag'].lower() == 'true':
                    parameters[f'zfsRepConfig_sendOptions_{flag}_flag'] = f"--{flag}"
                else:
                    parameters[f'zfsRepConfig_sendOptions_{flag}_flag'] = ""
                    
            if 'zfsRepConfig_sendOptions_compression_type' in parameters:
                compression_type = parameters['zfsRepConfig_sendOptions_compression_type'].strip().lower()
                if compression_type in ['compressed', 'raw']:
                    parameters['zfsRepConfig_sendOptions_compression_type'] = f"--{compression_type}"
                else:
                    parameters['zfsRepConfig_sendOptions_compression_type'] = ""
        
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
    parser = argparse.ArgumentParser(description='Generate Service + Timer Files from Template + Env Files')
    parser.add_argument('-t', '--template', type=str, nargs=1, help='template service file path')
    parser.add_argument('-e', '--env', type=str, nargs=1, help='env file path')
    args = parser.parse_args()
    template_path = args.template
    env_path = args.env
    env_filename = env_path.split('/')[-1]
    id_number = env_filename.split('_')[1]
    task_name = template_path.split('/')[-1].split('.')[0]
    output_path_service = f"/etc/systemd/system/{task_name}_{id_number}.service"
    output_path_timer = f"/etc/systemd/system/{task_name}_{id_number}.timer"
    
    
    
    
    
    # Define file paths
    template_file_path = "/opt/45drives/houston/scheduler/templates/ZfsReplicationTask.service"
    env_file_path = "/etc/systemd/system/ZfsReplicationTask_0.env"
    output_file_path = "/etc/systemd/system/ZfsReplicationTask_0.service"

    # Read template service file
    template_content = read_template_service_file(template_file_path)
    print("Template content:")
    print(template_content)

    # Parse keys/values from environment file
    parameters = parse_env_file(env_file_path)
    print("Parsed parameters:")
    print(parameters)

    # Replace placeholders in template with environment variables
    template_content = replace_placeholders(template_content, parameters)
    # Replace {env_path} placeholder with env_file_path
    template_content = template_content.replace("{env_path}", env_file_path)
    print("Modified template content:")
    print(template_content)

    # Generate concrete service file
    generate_concrete_service_file(template_content, output_file_path)
    print("Concrete service file generated successfully.")
    
    
if __name__ == "__main__":
	main()