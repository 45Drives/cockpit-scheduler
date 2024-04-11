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
        self.template = template  # This could be further expanded as needed
        self.parameters = parameters
        self.schedule = schedule.__dict__
    
    def to_json(self):
        # Convert the TaskInstance to a dictionary, then to a JSON string
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


# def read_template_service_file(template_path):
#     with open(template_path, 'r') as template_file:
#         return template_file.read()

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

def normalize_base_name(file_name):
    # Remove 'houston_scheduler_' prefix and numeric suffixes before the file extension
    core_name = re.sub(r'^houston_scheduler_', '', file_name)
    core_name = re.sub(r'_[0-9]+(?=\..*$)', '', core_name)
    return os.path.splitext(core_name)[0]  # Remove file extension and return

def find_service_basenames(template_dir):
    base_names = {}
    for file in os.listdir(template_dir):
        if file.endswith('.service'):
            base_name = normalize_base_name(file)
            base_names[base_name] = None  # Using None as a placeholder
    return base_names

def find_matching_system_files(system_dir, template_basenames):
    matching_files = {}
    for file in os.listdir(system_dir):
        # print(f"Found file: {file}")  # Diagnostic print
        full_base_name = re.sub(r'^houston_scheduler_', '', file)
        base_name, suffix = os.path.splitext(full_base_name)[0], os.path.splitext(full_base_name)[1]
        base_name = re.sub(r'_[0-9]+$', '', base_name)
        if base_name in template_basenames and suffix in ['.env', '.json']:
            file_type = 'env' if suffix == '.env' else 'json'
            if base_name not in matching_files:
                matching_files[base_name] = {'env': [], 'json': []}
            matching_files[base_name][file_type].append(os.path.join(system_dir, file))
    return matching_files

def create_task_instances(system_files):
    task_instances = []
    for template_name, file_groups in system_files.items():
        env_files = file_groups['env']
        json_files = file_groups['json']
        
        # Assuming the number of .env and .json files are the same and correspond to each other
        for i, (env_file, json_file) in enumerate(zip(env_files, json_files)):
            # Extract the specific task suffix from the file name
            # Assuming file naming convention to extract task index/suffix
            task_suffix_match = re.search(r'_(\d+)\.', os.path.basename(env_file))
            task_suffix = task_suffix_match.group(1) if task_suffix_match else str(i)
            
            task_name = f"{template_name}_{task_suffix}"  # Construct the task name
            parameters = read_env_parameters(env_file)
            schedule_data = read_json_schedule(json_file)
            schedule = TaskSchedule(schedule_data['enabled'], schedule_data['intervals'])
            task_instance = TaskInstance(task_name, template_name, parameters, schedule)
            task_instances.append(task_instance.__dict__)  # Collect dictionary representation

    return json.dumps(task_instances, indent=4)  # Serialize the entire list to JSON
    # return task_instances

def main():
    
    # Example usage
    template_dir = '/opt/45drives/houston/scheduler/templates/'
    system_dir = '/etc/systemd/system/'

    # Store basenames of .service files in a dict from the templates directory
    template_basenames = find_service_basenames(template_dir)

    # Check files in the system directory for those containing any of those basenames
    matching_system_files = find_matching_system_files(system_dir, template_basenames)
    
    task_instances = create_task_instances(matching_system_files)
    print(task_instances)
    # print(json.dumps(task_instances, indent=4))  # Serialize the entire list to JSON
    
    
if __name__ == "__main__":
	main()