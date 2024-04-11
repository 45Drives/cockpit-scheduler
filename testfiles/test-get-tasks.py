import os
import re
import json

# def read_template_service_file(template_path):
#     with open(template_path, 'r') as template_file:
#         return template_file.read()

# def read_env_file(env_path):
#     parameters = {}
#     with open(env_path, 'r') as env_file:
#         for line in env_file:
#             match = re.match(r'^([^=]+)=(.*)$', line.strip())
#             if match:
#                 key, value = match.groups()
#                 parameters[key.strip()] = value.strip()
#     return parameters

# def find_matching_files(directory):
#     file_dict = {}
#     for file in os.listdir(directory):
#         if file.endswith(('.service', '.timer', '.env')):
#             base_name = os.path.splitext(file)[0]
#             if base_name not in file_dict:
#                 file_dict[base_name] = {}
#             file_dict[base_name][os.path.splitext(file)[1][1:]] = os.path.join(directory, file)
#     return file_dict

# def compare_files(template_path, file_dict):
#     template_content = read_template_service_file(template_path)
#     for base_name, files in file_dict.items():
#         if 'service' in files and 'env' in files:
#             env_params = read_env_file(files['env'])
#             # Replace placeholders in the template with actual values from the env file
#             service_content = template_content.format({env_params})
#             print(f"Service file for {base_name}:")
#             print(service_content)
#             print("\n")

# def main():
#     template_path = '/opt/45drives/houston/scheduler/templates/ZfsReplicationTask.service'
#     directory = '/etc/systemd/system'
#     file_dict = find_matching_files(directory)
#     compare_files(template_path, file_dict)

# if __name__ == "__main__":
#     main()


# def parse_file(file_path):
#     """
#     Function to parse data from a file into an object.
#     Modify this function according to your file format.
#     """
#     with open(file_path, 'r') as file:
#         data = json.load(file)
#         return data

# def process_directory(directory_path):
#     """
#     Function to process files in a directory.
#     """
#     data_objects = []
    
#     # Check if the directory exists
#     if not os.path.isdir(directory_path):
#         print(f"Error: {directory_path} is not a valid directory.")
#         return data_objects
    
#     # Iterate through files in the directory
#     for filename in os.listdir(directory_path):
#         file_path = os.path.join(directory_path, filename)
        
#         # Check if the file is a regular file
#         if os.path.isfile(file_path):
#             # Parse file data into an object
#             data = parse_file(file_path)
#             # Append the object to the list
#             data_objects.append(data)
    
#     return data_objects

# def main():
#     directory_path = '/path/to/your/directory'  # Change this to your directory path
#     objects = process_directory(directory_path)
    
#     # Do something with the objects, for example, print them
#     for obj in objects:
#         print(obj)

# if __name__ == "__main__":
#     main()

def extract_data_from_env(env_file):
    # Function to extract data from env file and return as a dictionary
    data = {}
    with open(env_file, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=')
                data[key] = value
    return data

def main():
    systemd_dir = '/etc/systemd/system/'
    template_dir = '/opt/45drives/houston/scheduler/templates/'
    
    # List files in systemd directory
    systemd_files = os.listdir(systemd_dir)
    
    # List files in template directory
    template_files = os.listdir(template_dir)
    
    # Filter files by extensions
    service_files = [file for file in systemd_files if file.endswith('.service')]
    timer_files = [file for file in systemd_files if file.endswith('.timer')]
    env_files = [file for file in systemd_files if file.endswith('.env')]
    
    # Create a dictionary to store extracted data
    extracted_data = {}
    
    # Iterate over env files and extract data
    for env_file in env_files:
        service_name = env_file.split('.')[0]
        data = extract_data_from_env(os.path.join(systemd_dir, env_file))
        extracted_data[service_name] = data
    
    # Iterate over service and timer files
    for service_file in service_files:
        service_name = service_file.split('.')[0]
        for template_file in template_files:
            if service_name in template_file:
                extracted_data[service_name]['template'] = template_file
    
    # Save extracted data to a JSON file
    with open('extracted_data.json', 'w') as f:
        json.dump(extracted_data, f, indent=4)

if __name__ == "__main__":
    main()
