import subprocess
import argparse
import json
import os

def read_template_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()

def parse_env_file(parameter_env_file_path):
    parameters = {}
    with open(parameter_env_file_path, "r") as f:
        for line in f:
            key, value = line.strip().split('=')
            parameters[key] = value
        
        # Special parsing for zfsRepConfig and autoSnapConfig
        if key.startswith('zfsRepConfig'):
            if parameters.get(f'zfsRepConfig_sendOptions_raw_flag', 'false').lower() == 'true':
                parameters[f'zfsRepConfig_sendOptions_compressed_flag'] = ''
            elif parameters.get(f'zfsRepConfig_sendOptions_compressed_flag', 'false').lower() == 'true':
                parameters[f'zfsRepConfig_sendOptions_raw_flag'] = ''
                
            flags = ['recursive', 'customName', 'raw', 'compressed']
            for flag in flags:
                flag_key = f'zfsRepConfig_sendOptions_{flag}_flag'
                if parameters.get(flag_key, 'false').lower() == 'true':
                    parameters[flag_key] = f"--{flag}"
                else:
                    parameters[flag_key] = ''
                    if flag == 'customName':
                        parameters['zfsRepConfig_sendOptions_customName'] = ''
                        
        elif key.startswith('autoSnapConfig'):
            flags = ['recursive', 'customName']
            for flag in flags:
                flag_key = f'autoSnapConfig_{flag}_flag'
                if parameters.get(flag_key, 'false').lower() == 'true':
                    parameters[flag_key] = f"--{flag}"
                else:
                    parameters[flag_key] = ''
                    if flag == 'customName':
                        parameters['autoSnapConfig_customName'] = ''
        
    return parameters

def read_schedule_json(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading JSON from file {file_path}: {e}")
        return None

def interval_to_on_calendar(interval):
    parts = []
    
    if 'dayOfWeek' in interval:
        day_of_week = ','.join(interval['dayOfWeek'])
        parts.append(day_of_week)
    
    year_part = interval.get('year', {}).get('value', '*')
    month_part = interval.get('month', {}).get('value', '*')
    day_part = interval.get('day', {}).get('value', '*')
    date_part = f'{year_part}-{month_part}-{day_part}'
    parts.append(date_part)
    
    hour = interval.get('hour', {}).get('value', '*')
    minute = interval.get('minute', {}).get('value', '*')
    second = interval.get('second', {}).get('value', '0')
    time_part = f'{hour}:{minute}:{second}'
    parts.append(time_part)
    
    return 'OnCalendar=' + ' '.join(parts)

def replace_placeholders(template_content, parameters):
    for key, value in parameters.items():
        placeholder = "{" + key + "}"
        template_content = template_content.replace(placeholder, value)
    return template_content

def generate_concrete_file(template_content, output_file_path):
    with open(output_file_path, 'w') as file:
        file.write(template_content)

def manage_service(unit_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        subprocess.run(['sudo', 'systemctl', 'enable', f'{unit_name}'], check=True)
        subprocess.run(['sudo', 'systemctl', 'start', f'{unit_name}'], check=True)
        print(f'{unit_name} has been started')
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart {unit_name}: {e}")

def restart_service(unit_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'reset-failed'], check=True)
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        subprocess.run(['sudo', 'systemctl', 'enable', f'{unit_name}'], check=True)
        subprocess.run(['sudo', 'systemctl', 'restart', f'{unit_name}'], check=True)
        print(f'{unit_name} has been restarted')
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart {unit_name}: {e}")

def create_task(service_template_path, param_env_path, isStandalone):
    param_env_filename = os.path.basename(param_env_path)
    parts = param_env_filename.split('_')
    task_instance_name = '_'.join(parts[2:]).split('.env')[0]
    service_file_name = f'houston_scheduler_{task_instance_name}.service'
    output_path_service = f'/etc/systemd/system/{service_file_name}'
    
    service_template_content = read_template_file(service_template_path)
    parameters = parse_env_file(param_env_path)
    service_template_content = replace_placeholders(service_template_content, parameters)
    service_template_content = service_template_content.replace("{task_name}", task_instance_name)
    service_template_content = service_template_content.replace("{env_path}", param_env_path)
    
    generate_concrete_file(service_template_content, output_path_service)
    print("Standalone concrete service file generated successfully.")
    if (isStandalone):
        manage_service(service_file_name)
    else:
        restart_service(service_file_name)

def create_schedule(schedule_json_path, timer_template_path, full_unit_name, isStandalone):
    output_path_timer = f"/etc/systemd/system/{full_unit_name}.timer"
    schedule_data = read_schedule_json(schedule_json_path)
    
    if not schedule_data:
        print("Invalid schedule data.")
        return

    timer_template_content = read_template_file(timer_template_path)
    on_calendar_lines = [interval_to_on_calendar(interval) for interval in schedule_data['intervals']]
    on_calendar_lines_str = "\n".join(on_calendar_lines)
    timer_template_content = timer_template_content.replace("{description}", f"Timer for {full_unit_name}").replace("{on_calendar_lines}", on_calendar_lines_str)
    
    generate_concrete_file(timer_template_content, output_path_timer)
    print("Concrete timer file generated successfully.")
    
    if (isStandalone):
        manage_service(full_unit_name + '.timer')
    else:
        restart_service(full_unit_name)

def main():
    parser = argparse.ArgumentParser(description='Manage Service and Timer Files')
    parser.add_argument('-t', '--type', type=str, choices=['create-task', 'create-schedule', 'create-task-schedule'], required=True, help='Type of operation to perform')
    parser.add_argument('-st', '--serviceTemplate', type=str, help='Template service file path')
    parser.add_argument('-e', '--env', type=str, help='Env file path')
    parser.add_argument('-tt', '--timerTemplate', type=str, help='Template timer file path')
    parser.add_argument('-s', '--schedule', type=str, help='Schedule JSON file path')
    parser.add_argument('-n', '--name', type=str, help='Full task/unit name (required for schedule)')
    
    args = parser.parse_args()

    if args.type == 'create-task':
        if not args.serviceTemplate or not args.env:
            parser.error("the following arguments are required for create-task: -st/--serviceTemplate, -e/--env")
        create_task(args.serviceTemplate, args.env, True)
    elif args.type == 'create-schedule':
        if not args.timerTemplate or not args.schedule or not args.name:
            parser.error("the following arguments are required for create-schedule: -tt/--timerTemplate, -s/--schedule, -n/--name")
        create_schedule(args.schedule, args.timerTemplate, args.name, True)
    elif args.type == 'create-task-schedule':
        if not args.serviceTemplate or not args.env or not args.timerTemplate or not args.schedule:
            parser.error("the following arguments are required for create-task-schedule: -st/--serviceTemplate, -e/--env, -tt/--timerTemplate, -s/--schedule")
        
        create_task(args.serviceTemplate, args.env, False)
        
        param_env_filename = os.path.basename(args.env)
        parts = param_env_filename.split('_')
        task_instance_name = '_'.join(parts[2:]).split('.env')[0]
        full_unit_name = f"houston_scheduler_{task_instance_name}"
        
        create_schedule(args.schedule, args.timerTemplate, full_unit_name, False)
        manage_service(full_unit_name + '.timer')

if __name__ == "__main__":
    main()
