def read_template_service_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()

def parse_env_file(env_file_path):
    parameters = {}
    with open(env_file_path, "r") as f:
        for line in f:
            key, value = line.strip().split('=')
            parameters[key] = value
                
        # Check if flag values exist and is set to 'true'
        if 'zfsRepConfig_sendOptions_raw' in parameters and parameters['zfsRepConfig_sendOptions_raw'].lower() == 'true':
            parameters['raw_flag'] = "--raw"
        else:
            parameters['raw_flag'] = ""

        if 'zfsRepConfig_sendOptions_compressed' in parameters and parameters['zfsRepConfig_sendOptions_compressed'].lower() == 'true':
            parameters['compressed_flag'] = "--compressed"
        else:
            parameters['compressed_flag'] = ""

        if 'zfsRepConfig_sendOptions_recursive' in parameters and parameters['zfsRepConfig_sendOptions_recursive'].lower() == 'true':
            parameters['recursive_flag'] = "--recursive"
        else:
            parameters['recursive_flag'] = ""
        
    return parameters

def replace_placeholders(template_content, parameters):
    for key, value in parameters.items():
        # Handle special keys for flags
        if key.endswith('_flag'):
            placeholder = "{" + key + "}"
            template_content = template_content.replace(placeholder, value)
        else:
            # Replace other placeholders normally
            placeholder = "{" + key + "}"
            template_content = template_content.replace(placeholder, value)
    return template_content


def generate_concrete_service_file(template_content, output_file_path):
    with open(output_file_path, 'w') as file:
        file.write(template_content)

# Define file paths
template_file_path = "/opt/45drives/houston/scheduler/templates/ZfsReplicationTask.service"
env_file_path = "/etc/systemd/system/ZfsReplicationTask_0.env"
output_file_path = "/etc/systemd/system/ZfsReplicationTask_0.service"

# Read template service file
template_content = read_template_service_file(template_file_path)
print("Template content:")
print(template_content)

# Parse keys/values from environment file
parameters = parse_env_file(env_file_path)
print("Parsed parameters:")
print(parameters)

# Replace placeholders in template with environment variables
template_content = replace_placeholders(template_content, parameters)
# Replace {env_path} placeholder with env_file_path
template_content = template_content.replace("{env_path}", env_file_path)
print("Modified template content:")
print(template_content)

# Generate concrete service file
generate_concrete_service_file(template_content, output_file_path)
print("Concrete service file generated successfully.")