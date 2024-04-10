import subprocess
import argparse
import re
import json
import os
import datetime

def read_template_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()


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
    

def manage_systemd_service(timer_file_name):
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    
    # Enable the timer
    subprocess.run(['sudo', 'systemctl', 'enable', f'houston_scheduler_{timer_file_name}'], check=True)
    
    # Start the timer
    subprocess.run(['sudo', 'systemctl', 'start', f'houston_scheduler_{timer_file_name}'], check=True)
    
    # Optionally, check the status of the timer
    subprocess.run(['sudo', 'systemctl', 'status', f'houston_scheduler_{timer_file_name}'], check=True)


def main():
    parser = argparse.ArgumentParser(description='Generate Service + Timer Files from Template + Env Files')
    parser.add_argument('-st', '--serviceTemplate', type=str, help='template service file path')
    parser.add_argument('-e', '--env', type=str, help='env file path')
    parser.add_argument('-tt', '--timerTemplate', type=str, help='template timer file path')
    parser.add_argument('-s', '--schedule', type=str, help='schedule json')
    
    args = parser.parse_args()
    template_service_path = args.serviceTemplate
    param_env_path = args.env
    template_timer_path = args.timerTemplate
    schedule_json_path = args.schedule
    
    param_env_filename = param_env_path.split('/')[-1]
    
    id_number = param_env_filename.split('_')[-1].split('.')[0]
    
    task_template_name = template_service_path.split('/')[-1].split('.')[0]
    task_instance_name = task_template_name + '_' + id_number
    
    service_file_name = task_instance_name + '.service'
    timer_file_name = task_instance_name + '.timer'
        
    output_path_service = f"/etc/systemd/system/houston_scheduler_{service_file_name}"
    output_path_timer = f"/etc/systemd/system/houston_scheduler_{timer_file_name}"
    
    service_template_content = read_template_file(template_service_path)
    timer_template_content = read_template_file(template_timer_path)
    
    # Parse keys/values from environment file
    parameters = parse_env_file(param_env_path)

    # Replace placeholders in service file template with environment variables
    service_template_content = replace_service_placeholders(service_template_content, parameters)
    service_template_content = service_template_content.replace("{env_path}", param_env_path)

    # Generate concrete service file
    generate_concrete_file(service_template_content, output_path_service)
    print(service_template_content)
    print("Concrete service file generated successfully.")
    
    schedule_data = read_schedule_json(schedule_json_path)
    # print(schedule_data)
    
    on_calendar_lines = [interval_to_on_calendar(interval) for interval in schedule_data['intervals']]
    on_calendar_lines_str = "\n".join(on_calendar_lines)
    
    # on_calendar_lines = []
    # for interval in schedule_data['intervals']:
    #     print(interval)  # Inspect each interval
    #     try:
    #         on_calendar_line = interval_to_on_calendar(interval)
    #         on_calendar_lines.append(on_calendar_line)
    #     except TypeError as e:
    #         print(f"Error processing interval: {interval}. Error: {e}")
            
    timer_template_content = timer_template_content.replace("{description}", "Timer for " + task_instance_name).replace("{on_calendar_lines}", on_calendar_lines_str)
    
    # Generate concrete timer file
    generate_concrete_file(timer_template_content, output_path_timer)
    print(timer_template_content)
    print("Concrete timer file generated successfully.")
    
    manage_systemd_service(timer_file_name)
    
if __name__ == "__main__":
	main()