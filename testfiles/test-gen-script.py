import subprocess
import argparse
import re
import json
import os
import datetime

def read_template_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()


def extract_description(service_template_content):
    for line in service_template_content.split('\n'):
        if line.startswith('Description='):
            return line.split('=', 1)[1]
    return None


def parse_env_file(parameter_env_file_path):
    parameters = {}
    with open(parameter_env_file_path, "r") as f:
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
                    if flag == 'customName':
                        parameters['zfsRepConfig_sendOptions_customName'] = ""
        
    return parameters


def read_schedule_json(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file: {file_path}")
        return None


def interval_to_on_calendar(interval):
    parts = []
    
    # Handle dayOfWeek if present
    if 'dayOfWeek' in interval:
        day_of_week = ','.join(interval['dayOfWeek'])
        parts.append(day_of_week)
    
    # Initialize default values for date components
    year_part, month_part, day_part = '*', '*', '*'
    
    # Handle year, month, and day, including steps
    for unit in ['year', 'month', 'day']:
        if unit in interval:
            value = interval[unit]['value']
            step = interval[unit].get('step')
            if step:
                part = f'{value}/{step}'
            else:
                part = value
            
            if unit == 'year':
                year_part = part
            elif unit == 'month':
                month_part = part
            elif unit == 'day':
                day_part = part
    
    # Construct the date part
    date_part = f'{year_part}-{month_part}-{day_part}'
    parts.append(date_part)
    
    # Handle hour and minute, including steps
    hour = interval.get('hour', {}).get('value', '*')
    minute = interval.get('minute', {}).get('value', '0')
    time_part = f'{hour}:{minute}'
    
    # Apply steps to time components if present
    for unit in ['hour', 'minute']:
        if unit in interval and 'step' in interval[unit]:
            step = interval[unit]['step']
            if unit == 'hour':
                time_part = f'{hour}/{step}:{minute}'
            elif unit == 'minute':
                time_part = f'{hour}:{minute}/{step}'
    
    parts.append(time_part)
    
    return 'OnCalendar=' + ' '.join(parts)


def replace_service_placeholders(service_template_content, parameters):
    for key, value in parameters.items():
        placeholder = "{" + key + "}"
        service_template_content = service_template_content.replace(placeholder, value)
    return service_template_content

def generate_concrete_file(template_content, output_file_path):
    with open(output_file_path, 'w') as file:
        file.write(template_content)
    
    

def main():
    # parser = argparse.ArgumentParser(description='Generate Service + Timer Files from Template + Env Files')
    # parser.add_argument('-t', '--template', type=str, nargs=1, help='template service file path')
    # parser.add_argument('-e', '--env', type=str, nargs=1, help='env file path')
    
    # parser.add_argument('-s', '--schedule', type=str, nargs='?', help='schedule json')
    
    # args = parser.parse_args()
    # template_path = args.template
    # param_env_path = args.env
    # schedule_json_path = args.schedule
    
    # param_env_filename = param_env_path.split('/')[-1]
    # id_number = param_env_filename.split('_')[1]
    # task_name = template_path.split('/')[-1].split('.')[0]
    # output_path_service = f"/etc/systemd/system/{task_name}_{id_number}.service"
    # output_path_timer = f"/etc/systemd/system/{task_name}_{id_number}.timer"
    # schedule = read_schedule_json(schedule_json_path)
    # service_template_content = read_template_file(template_service_file_path)
    # timer_template_content = read_template_file(template_timer_file_path)
    # task_name = extract_description(service_template_content)
    
    
    # Define file paths (testing)
    template_service_file_path = "/opt/45drives/houston/scheduler/templates/ZfsReplicationTask.service"
    template_timer_file_path = "/opt/45drives/houston/scheduler/templates/Schedule.timer"
    
    parameter_env_file_path = "/etc/systemd/system/houston_scheduler_ZfsReplicationTask_0.env"
    schedule_json_file_path = "/etc/systemd/system/houston_scheduler_ZfsReplicatonTask_0.json"
    
    # dynamically create these paths
    service_output_file_path = "/etc/systemd/system/houston_scheduler_ZfsReplicationTask_0.service"
    timer_output_file_path = "/etc/systemd/system/houston_scheduler_ZfsReplicationTask_0.timer"
    
    service_template_content = read_template_file(template_service_file_path)
    timer_template_content = read_template_file(template_timer_file_path)

    schedule_data = read_schedule_json(schedule_json_file_path)
    
    task_name = extract_description(service_template_content)
    
    # Parse keys/values from environment file
    parameters = parse_env_file(parameter_env_file_path)

    # Replace placeholders in service file template with environment variables
    service_template_content = replace_service_placeholders(service_template_content, parameters)
    service_template_content = service_template_content.replace("{param_env_path}", parameter_env_file_path)

    # Generate concrete service file
    generate_concrete_file(service_template_content, service_output_file_path)
    print(service_template_content)
    print("Concrete service file generated successfully.")
    
    on_calendar_lines = [interval_to_on_calendar(interval) for interval in schedule_data['intervals']]
    on_calendar_lines_str = "\n".join(on_calendar_lines)
    timer_template_content = timer_template_content.replace("{{description}}", "Timer for " + task_name).replace("{{on_calendar_lines}}", on_calendar_lines_str)
    
    # Generate concrete timer file
    generate_concrete_file(timer_template_content, timer_output_file_path)
    print(timer_template_content)
    print("Concrete timer file generated successfully.")
    
    
    
    # os.symlink(template_service_file_path, service_output_file_path)
    # print(f"Symlink created: {service_output_file_path} -> {template_service_file_path}")
    
    
if __name__ == "__main__":
	main()