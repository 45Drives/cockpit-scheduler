import subprocess
import argparse
import os
import re
import json

def write_env_file(parameters, parameter_env_file_path):
    with open(parameter_env_file_path, "w") as f:
        if isinstance(parameters, str):
            # Split the string into lines assuming newline characters
            parameters = parameters.split('\n')
        for line in parameters:
            # Strip leading/trailing whitespace and remove all quotation marks
            clean_line = line.strip().replace('"', '')
            if clean_line:  # This will avoid writing empty lines
                f.write(clean_line + '\n')

def get_env_file_name(task_template, task_name):
    env_prefix = 'houston_scheduler_'
    full_task_name = env_prefix + task_template + '_' + task_name + '.env'
    return full_task_name

def main():
    parser = argparse.ArgumentParser(description='Generate env parameter file for houston scheduler task')
    parser.add_argument('-t', '--template', type=str, help='name of task template')
    parser.add_argument('-n', '--name', type=str, help='name of task')
    parser.add_argument('-p', '--parameters', type=str, help='parameters from UI component')
    
    args = parser.parse_args()
    template = args.template
    task_name = args.name
    parameters = args.parameters
    
    env_dir = '/etc/systemd/system/'
   
    final_path = env_dir + get_env_file_name(template, task_name)
    
    write_env_file(parameters, final_path)
    print('env file generated')
    
if __name__ == "__main__":
    main()