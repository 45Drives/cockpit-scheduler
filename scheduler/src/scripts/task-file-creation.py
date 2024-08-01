import re
import subprocess
import argparse
import json
import os
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def read_template_file(template_file_path):
    logging.debug(f'Reading template file: {template_file_path}')
    with open(template_file_path, 'r') as file:
        content = file.read()
    logging.debug('Template file read successfully')
    return content

def parse_env_file(parameter_env_file_path):
    logging.debug(f'Parsing env file: {parameter_env_file_path}')
    parameters = {}
    with open(parameter_env_file_path, "r") as f:
        for line in f:
            key, value = line.strip().split('=')
            parameters[key] = value
        
    logging.debug('Env file parsed successfully')
    return parameters

def selectParameterOptions(templateName):
    if templateName == 'ZfsReplicationTask':
        return [
            "${zfsRepConfig_sourceDataset_dataset}",
            "${zfsRepConfig_sendOptions_recursive_flag}",
            "${zfsRepConfig_sendOptions_customName_flag}", 
            "${zfsRepConfig_sendOptions_customName}", 
            "${zfsRepConfig_sendOptions_compressed_flag}", 
            "${zfsRepConfig_sendOptions_raw_flag}", 
            "--root ${zfsRepConfig_destDataset_pool}", 
            "--path ${zfsRepConfig_destDataset_dataset}",
            "--user ${zfsRepConfig_destDataset_user}",
            "--host ${zfsRepConfig_destDataset_host}",
            "--port ${zfsRepConfig_destDataset_port}",
            "--mbuffsize ${zfsRepConfig_sendOptions_mbufferSize}",
            "--mbuffunit ${zfsRepConfig_sendOptions_mbufferUnit}",
            "--snapsToKeepSrc ${zfsRepConfig_snapRetention_source}",
            "--snapsToKeepDest ${zfsRepConfig_snapRetention_destination}",
        ]
    elif templateName == 'AutomatedSnapshotTask':
        return [
            "${autoSnapConfig_filesystem_dataset}",
            "${autoSnapConfig_recursive_flag}",
            "${autoSnapConfig_customName_flag}",
            "${autoSnapConfig_customName}",
            "--snapsToKeep ${autoSnapConfig_snapRetention}",
        ]
    elif templateName == 'RsyncTask':
        return [
            "--source ${rsyncConfig_local_path}",
            "--direction ${rsyncConfig_direction}",
            "--host=${rsyncConfig_target_info_host}",
            "--port=${rsyncConfig_target_info_port}",
            "--user=${rsyncConfig_target_info_user}",
            "--target ${rsyncConfig_target_info_path}",
            "${rsyncConfig_rsyncOptions_archive_flag}",
            "${rsyncConfig_rsyncOptions_recursive_flag}",
            "${rsyncConfig_rsyncOptions_compressed_flag}",
            "${rsyncConfig_rsyncOptions_delete_flag}",
            "${rsyncConfig_rsyncOptions_quiet_flag}",
            "${rsyncConfig_rsyncOptions_times_flag}",
            "${rsyncConfig_rsyncOptions_hardlinks_flag}",
            "${rsyncConfig_rsyncOptions_permissions_flag}",
            "${rsyncConfig_rsyncOptions_xattr_flag}",
            "--bandwidth=${rsyncConfig_rsyncOptions_bandwidth_limit_kbps}",
            "--include=${rsyncConfig_rsyncOptions_include_pattern}",
            "--exclude=${rsyncConfig_rsyncOptions_exclude_pattern}",
            "${rsyncConfig_rsyncOptions_parallel_flag}",
            "--threads=${rsyncConfig_rsyncOptions_parallel_threads}",
            "${rsyncConfig_rsyncOptions_custom_args}"
        ]
    elif templateName == 'SmartTest':
        return [
            "--disks ${smartTestConfig_disks}",
            "--type ${smartTestConfig_testType}"
        ]
    elif templateName == 'ScrubTask':
        return [
            "${scrubConfig_pool_pool}"
        ]
    # elif templateName == 'CloudSyncTask':
    #     return [
            
    #     ]
    # elif templateName == 'CronJobTask':
    #     return [
            
    #     ]
    else:
        return []

def generate_exec_start(templateName, parameters, scriptPath):
    base_python_command = f"python3 {scriptPath}"
    options = selectParameterOptions(templateName)
    
    exec_start = []
    if templateName == 'ScrubTask':
        exec_start.append('zpool scrub')   
    else:
        exec_start.append(base_python_command)
        
    for option in options:
        # Use regex to extract the placeholder name from ${placeholder}
        match = re.search(r'\$\{(.+?)\}', option)
        if match:
            placeholder = match.group(1)
            if placeholder in parameters and parameters[placeholder]:
                exec_start.append(option)
    return " ".join(exec_start)

def read_schedule_json(file_path):
    logging.debug(f'Reading schedule JSON file: {file_path}')
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            logging.debug('Schedule JSON file read successfully')
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error reading JSON from file {file_path}: {e}")
        return None

def interval_to_on_calendar(interval):
    logging.debug(f'Converting interval to OnCalendar format: {interval}')
    parts = []
    
    if 'dayOfWeek' in interval and interval['dayOfWeek']:
        day_of_week = ','.join(interval['dayOfWeek'])
        parts.append(day_of_week)
    
    year_part = interval.get('year', {}).get('value', '*')
    month_part = interval.get('month', {}).get('value', '*')
    day_part = interval.get('day', {}).get('value', '*')
    
    # Modify the parts if they contain a slash and the base is not an asterisk
    if '/' in day_part:
        base, step = day_part.split('/')
        if base == '*':
            base = '1'  # Default to starting from the 1st day if base is '*'
        day_part = f'{base}/{step}'
    
    date_part = f'{year_part}-{month_part}-{day_part}'
    parts.append(date_part)
    
    hour = interval.get('hour', {}).get('value', '*')
    minute = interval.get('minute', {}).get('value', '*')
    second = interval.get('second', {}).get('value', '0')
    
    # Modify the parts if they contain a slash
    if '/' in hour:
        base, step = hour.split('/')
        if base == '*':
            base = '0'  # Default to starting from 0 if base is '*'
        hour = f'{base}/{step}'
    
    if '/' in minute:
        base, step = minute.split('/')
        if base == '*':
            base = '0'  # Default to starting from 0 if base is '*'
        minute = f'{base}/{step}'
    
    time_part = f'{hour}:{minute}:{second}'
    parts.append(time_part)
    
    on_calendar_value = ' '.join(parts)
    
    return 'OnCalendar=' + on_calendar_value

def replace_placeholders(template_content, parameters):
    logging.debug('Replacing placeholders in the template')
    for key, value in parameters.items():
        placeholder = "{" + key + "}"
        template_content = template_content.replace(placeholder, value)
    return template_content

def generate_concrete_file(template_content, output_file_path):
    logging.debug(f'Generating concrete file at: {output_file_path}')
    with open(output_file_path, 'w') as file:
        file.write(template_content)
    logging.debug('Concrete file generated successfully')

def manage_service(unit_name, action):
    logging.debug(f'Managing service: {unit_name} with action: {action}')
    try:
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        subprocess.run(['sudo', 'systemctl', action, unit_name], check=True)
        logging.debug(f'{unit_name} has been {action}d')
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to {action} {unit_name}: {e}")

def start_timer(timer_name):
    logging.debug(f'Starting timer: {timer_name}')
    try:
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)

        result = subprocess.run(['sudo', 'systemctl', 'is-enabled', timer_name], universal_newlines=True, stdout=subprocess.PIPE)
        
        if result.stdout.strip() == 'enabled':
            logging.debug(f'Timer {timer_name} is active, restarting it')
            subprocess.run(['sudo', 'systemctl', 'restart', timer_name], check=True)
            logging.debug(f'{timer_name} has been restarted')
        else:
            logging.debug(f'Timer {timer_name} is inactive, starting it')
            subprocess.run(['sudo', 'systemctl', 'start', timer_name], check=True)
            logging.debug(f'{timer_name} has been started')
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to start {timer_name}: {e}")

def create_task(template_name, script_path, param_env_path):
    logging.debug(f'Creating task with service template: {template_name} and env file: {param_env_path}')
    param_env_filename = os.path.basename(param_env_path)
    parts = param_env_filename.split('_')
    task_instance_name = '_'.join(parts[2:]).split('.env')[0]
    service_file_name = f'houston_scheduler_{task_instance_name}.service'
    output_path_service = f'/etc/systemd/system/{service_file_name}'
    
    service_template_content = read_template_file('/opt/45drives/houston/scheduler/templates/ServiceTemplate.service')
    parameters = parse_env_file(param_env_path)
    exec_start_command = generate_exec_start(template_name, parameters, script_path)
    service_template_content = service_template_content.replace("{task_name}", task_instance_name)
    service_template_content = service_template_content.replace("{env_path}", param_env_path)
    service_template_content = service_template_content.replace("{ExecStart}", exec_start_command)
    
    generate_concrete_file(service_template_content, output_path_service)
    logging.debug("Standalone concrete service file generated successfully.")

def create_schedule(schedule_json_path, timer_template_path, full_unit_name):
    logging.debug(f'Creating schedule with timer template: {timer_template_path} and schedule file: {schedule_json_path}')
    output_path_timer = f"/etc/systemd/system/{full_unit_name}.timer"
    schedule_data = read_schedule_json(schedule_json_path)
    
    if not schedule_data:
        logging.error("Invalid schedule data.")
        return

    timer_template_content = read_template_file(timer_template_path)
    on_calendar_lines = [interval_to_on_calendar(interval) for interval in schedule_data['intervals']]
    on_calendar_lines_str = "\n".join(on_calendar_lines)
    timer_template_content = timer_template_content.replace("{description}", f"Timer for {full_unit_name}").replace("{on_calendar_lines}", on_calendar_lines_str)
    
    generate_concrete_file(timer_template_content, output_path_timer)
    logging.debug("Concrete timer file generated successfully.")
    
    manage_service(full_unit_name + '.timer', 'enable')
    start_timer(full_unit_name + '.timer')

def main():
    logging.debug('Starting main function')
    parser = argparse.ArgumentParser(description='Manage Service and Timer Files')
    parser.add_argument('-tN', '--templateName', type=str, help='Task Template Name')
    parser.add_argument('-t', '--type', type=str, choices=['create-task', 'create-schedule', 'create-task-schedule'], required=True, help='Type of operation to perform')
    parser.add_argument('-sP', '--scriptPath', type=str, help='Script Path')
    parser.add_argument('-e', '--env', type=str, help='Env file path')
    parser.add_argument('-tt', '--timerTemplate', type=str, help='Template timer file path')
    parser.add_argument('-s', '--schedule', type=str, help='Schedule JSON file path')
    parser.add_argument('-n', '--name', type=str, help='Full task/unit name (required for schedule)')
    
    args = parser.parse_args()

    if args.type == 'create-task':
        if not args.templateName or not args.scriptPath or not args.env:
            parser.error("the following arguments are required for create-task: -tN/--templateName, -sP/--scriptPath, -e/--env")
        create_task(args.templateName, args.scriptPath, args.env)
    elif args.type == 'create-schedule':
        if not args.timerTemplate or not args.schedule or not args.name:
            parser.error("the following arguments are required for create-schedule: -tt/--timerTemplate, -s/--schedule, -n/--name")
        create_schedule(args.schedule, args.timerTemplate, args.name)
    elif args.type == 'create-task-schedule':
        if not args.templateName or not args.scriptPath or not args.env or not args.timerTemplate or not args.schedule:
            parser.error("the following arguments are required for create-task-schedule: -tN/--templateName, -sP/--scriptPath, -e/--env, -tt/--timerTemplate, -s/--schedule")
        
        create_task(args.templateName, args.scriptPath, args.env)
        
        param_env_filename = os.path.basename(args.env)
        parts = param_env_filename.split('_')
        task_instance_name = '_'.join(parts[2:]).split('.env')[0]
        full_unit_name = f"houston_scheduler_{task_instance_name}"
        
        create_schedule(args.schedule, args.timerTemplate, full_unit_name)
    logging.debug('Main function execution completed')
        
if __name__ == "__main__":
    main()
