import os
import re
import json
import subprocess

currentTaskTemplates = ['ZfsReplicationTask', 'AutomatedSnapshotTask', 'ScrubTask', 'RsyncTask', 'SmartTest', 'CustomTask', 'CloudSyncTask']


class TaskScheduleInterval:
    def __init__(self, interval_data):
        self.__dict__ = interval_data

class TaskSchedule:
    def __init__(self, enabled, intervals):
        self.enabled = enabled
        self.intervals = [TaskScheduleInterval(interval).__dict__ for interval in intervals]

class TaskInstance:
    def __init__(self, name, template, parameters, schedule, notes):
        self.name = name
        self.template = template
        self.parameters = parameters
        self.schedule = schedule.__dict__
        self.notes = notes
        

def check_task_status(full_unit_name):
    # check the status of the timer
    subprocess.run(['sudo', 'systemctl', 'status', f'{full_unit_name}.timer'], check=True)


def read_env_parameters(env_path):
    parameters = {}
    with open(env_path, 'r') as env_file:
        for line in env_file:
            match = re.match(r'^([^=]+)=(.*)$', line.strip())
            if match:
                key, value = match.groups()
                parameters[key.strip()] = value.strip()
    return parameters

def read_json_schedule(json_path):
    with open(json_path, 'r') as json_file:
        return json.load(json_file)

def read_txt_notes(txt_path):
    with open(txt_path, 'r') as txt_file:
        return txt_file.read() 

def find_template_basenames(template_dir):
    base_names = {}
    for file in os.listdir(template_dir):
        if file.endswith('.service'):
            base_name = os.path.splitext(file)[0]
            base_names[base_name] = None  # Using None as a placeholder
            
            # print(f"Loaded template basename: {base_name}")  # Debug: Check loaded template names
            
    return base_names


def find_valid_task_data_files(system_dir, template_basenames):
    valid_files = {}
    # Adjusted regex to match up to the last dot before extension
    file_regex = re.compile(r"^houston_scheduler_([^_]+)_(.*)\.(env|json|txt)$")

    for file in os.listdir(system_dir):
        match = file_regex.match(file)
        if match:
            template_name, task_name_with_suffix, suffix = match.groups()
            # Extract the task name correctly before appending the file to the list
            if template_name in template_basenames:
                if template_name not in valid_files:
                    valid_files[template_name] = []
                # Include the correct file format with the suffix
                valid_files[template_name].append(file)

    return valid_files

def create_task_instances(system_dir, valid_files):
    task_instances = []

    for template, files in valid_files.items():
        paired_files = {}

        for file in files:
            full_base_name, ext = os.path.splitext(file)
            # Remove the prefix and then split properly
            task_name = full_base_name[len("houston_scheduler_" + template + "_"):]  # This strips the prefix and template

            if task_name not in paired_files:
                paired_files[task_name] = {}
            paired_files[task_name][ext] = file

        for task_name, file_dict in paired_files.items():
            if '.env' in file_dict:
                env_file_name = file_dict['.env']
                parameters = read_env_parameters(os.path.join(system_dir, env_file_name))
                
                if '.json' in file_dict:
                    json_file_name = file_dict['.json']
                    schedule_data = read_json_schedule(os.path.join(system_dir, json_file_name))
                    schedule = TaskSchedule(schedule_data['enabled'], schedule_data['intervals'])
                else:
                    schedule = TaskSchedule(False, [])
                
                if '.txt' in file_dict:
                    notes_file_name = file_dict['.txt']
                    notes_file_path = os.path.join(system_dir, notes_file_name)
                    notes = read_txt_notes(notes_file_path)  # Read the notes from the .txt file
                else:
                    # notes = json.dumps(file_dict, indent=4)  # Convert dict to JSON string for readability
                    notes = "" 

            task_instance = TaskInstance(task_name, template, parameters, schedule, notes)
            task_instances.append(task_instance)

    return json.dumps([instance.__dict__ for instance in task_instances], indent=4)

def main():
    system_dir = '/etc/systemd/system/'

    # Check files in the system directory for those containing any of the task template names
    valid_task_data_files = find_valid_task_data_files(system_dir, currentTaskTemplates)
    
    task_instances = create_task_instances(system_dir, valid_task_data_files)
    print(task_instances)   
    
if __name__ == "__main__":
	main()