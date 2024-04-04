import subprocess
import argparse
import re
import json
import os
import datetime

# class TaskScheduleInterval:
#     def __init__(self, value: int, unit: str):
#         self.value = value
#         self.unit = unit

# class TaskSchedule:
#     def __init__(self, enabled: bool, intervals: list[TaskScheduleInterval]):
#         self.enabled = enabled
#         self.intervals = intervals


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
                    
               
                    
            # if 'zfsRepConfig_sendOptions_compression_type' in parameters:
            #     compression_type = parameters['zfsRepConfig_sendOptions_compression_type'].strip().lower()
            #     if compression_type in ['compressed', 'raw']:
            #         parameters['zfsRepConfig_sendOptions_compression_type'] = f"--{compression_type}"
            #     else:
            #         parameters['zfsRepConfig_sendOptions_compression_type'] = ""   
        
    return parameters


# def parse_task_schedule_from_string(schedule_string):
#     # Parse the JSON string to convert it into a dictionary
#     schedule_data = json.loads(schedule_string)

#     # Extract the enabled flag and intervals from the dictionary
#     enabled = schedule_data.get("enabled", False)  # Default to False if "enabled" key is missing
#     intervals_data = schedule_data.get("intervals", [])

#     # Create TaskScheduleInterval objects from intervals data
#     intervals = [TaskScheduleInterval(interval["value"], interval["unit"]) for interval in intervals_data]

#     # Create and return the TaskSchedule object
#     return TaskSchedule(enabled, intervals)


def replace_placeholders(template_content, parameters):
    for key, value in parameters.items():
        placeholder = "{" + key + "}"
        template_content = template_content.replace(placeholder, value)
    return template_content

# def generate_on_calendar(schedule):
#     intervals = []
    
#     # Convert intervals to OnCalendar format
#     for interval in schedule.intervals:
#         if interval.unit == 'seconds':
#             intervals.append(f'*-*-* *:*:{interval.value}')
#         elif interval.unit == 'minutes':
#             intervals.append(f'*-*-* *:{interval.value}:00')
#         elif interval.unit == 'hours':
#             intervals.append(f'*-*-* {interval.value}:00:00')
#         elif interval.unit == 'days':
#             intervals.append(f'*-*-{interval.value} *:*:00')
#         elif interval.unit == 'weeks':
#             intervals.append(f'*-*-* {interval.value} 00:00:00')
#         elif interval.unit == 'months':
#             intervals.append(f'*-*-01 {interval.value} *:00:00')
#         elif interval.unit == 'years':
#             intervals.append(f'*-01-01 {interval.value} *:00:00')
        
#     return ','.join(intervals)

def generate_concrete_service_file(template_content, output_file_path):
    with open(output_file_path, 'w') as file:
        file.write(template_content)

# def generate_timer_file(task_name, schedule, output_file_path):
    
#     schedule = generate_on_calendar(schedule)
#     # need to have separate onCalendar= for each interval
    
#     timer_content = f"""[Unit]
# Description={task_name} timer

# [Timer]
# OnCalendar={schedule}
# Persistent=true

# [Install]
# WantedBy=timers.target
# """
    
    
    
#     with open(output_file_path, 'w') as file:
#         file.write(timer_content)
      
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
    env_file_path = "/etc/systemd/system/ZfsReplicationTask_0.env"
    output_file_path = "/etc/systemd/system/ZfsReplicationTask_0.service"
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