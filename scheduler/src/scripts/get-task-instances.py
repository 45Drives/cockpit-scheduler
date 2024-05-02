import os
import re
import json

class TaskScheduleInterval:
    def __init__(self, interval_data):
        self.__dict__ = interval_data

class TaskSchedule:
    def __init__(self, enabled, intervals):
        self.enabled = enabled
        self.intervals = [TaskScheduleInterval(interval).__dict__ for interval in intervals]

class TaskInstance:
    def __init__(self, name, template, parameters, schedule):
        self.name = name
        self.template = template
        self.parameters = parameters
        self.schedule = schedule.__dict__

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

    for file in os.listdir(system_dir):
        
        # print(f"Checking file: {file}")  # Debug: Check each file seen by os.listdir
        
        if file.startswith("houston_scheduler_"):
            # Correctly strip the prefix
            stripped_name = file[len("houston_scheduler"):]
            # Correctly split to get template name and task name before the last underscore
            name_parts = stripped_name.rsplit('_', 2)
            if len(name_parts) >= 3:
                template_name, remaining = name_parts[1], name_parts[2]
                # Properly handle the suffix
                task_name, suffix = os.path.splitext(remaining)

                # print(f"Extracted - Template: {template_name}, Task: {task_name}, Suffix: {suffix}")

                # Check if the suffix is either .env or .json
                if template_name in template_basenames and suffix in ['.env', '.json']:
                    if template_name not in valid_files:
                        valid_files[template_name] = []
                    valid_files[template_name].append(file)

    # print(f"Valid files found: {valid_files}")
    return valid_files


def create_task_instances(system_dir, valid_files):
    task_instances = []

    # Iterate through each template and its files
    for template, files in valid_files.items():
        paired_files = {}

        # Organize files by basename without the extension
        for file in files:
            full_base_name, ext = os.path.splitext(file)
            # Assume the structure is like 'houston_scheduler_TemplateName_TaskNameRest.env'
            parts = full_base_name.split('_')
            if len(parts) > 3:
                # Base name becomes the part after 'TemplateName'
                task_name = '_'.join(parts[3:])  # Join parts that may include additional underscores
            else:
                task_name = parts[-1]  # Fallback to the last part if not enough parts

            if task_name not in paired_files:
                paired_files[task_name] = {}
            paired_files[task_name][ext] = file

        # Process each pair of files
        for base_name, file_dict in paired_files.items():
            if '.env' in file_dict:
                env_file_name = file_dict['.env']
                parameters = read_env_parameters(os.path.join(system_dir, env_file_name))
                
                if '.json' in file_dict:
                    json_file_name = file_dict['.json']
                    schedule_data = read_json_schedule(os.path.join(system_dir, json_file_name))
                    schedule = TaskSchedule(schedule_data['enabled'], schedule_data['intervals'])
                else:
                    schedule = TaskSchedule(False, [])
                
            task_instance = TaskInstance(base_name, template, parameters, schedule)
            task_instances.append(task_instance)

    # Convert task_instances to JSON serializable format
    task_instances_json = [instance.__dict__ for instance in task_instances]
    return json.dumps(task_instances_json, indent=4)


def main():
    
    # Example usage
    template_dir = '/opt/45drives/houston/scheduler/templates/'
    system_dir = '/etc/systemd/system/'

    # Store basenames of .service files in a dict from the templates directory
    template_basenames = find_template_basenames(template_dir)

    # Check files in the system directory for those containing any of those basenames
    valid_task_data_files = find_valid_task_data_files(system_dir, template_basenames)
    
    task_instances = create_task_instances(system_dir, valid_task_data_files)
    print(task_instances)
    
    
if __name__ == "__main__":
	main()