import os

def read_template_service_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()

def parse_env_file(env_file_path):
    parameters = {}
    with open(env_file_path, "r") as f:
        for line in f:
            key, value = line.strip().split('=')
            parameters[key] = value
                
        # Check if flag values exist and are set to 'true'
        flags = ['raw', 'compressed', 'recursive']
        for flag in flags:
            if f'zfsRepConfig_sendOptions_{flag}' in parameters and parameters[f'zfsRepConfig_sendOptions_{flag}'].lower() == 'true':
                parameters[f'{flag}_flag'] = f"--{flag}"
            else:
                parameters[f'{flag}_flag'] = ""

        # Handle customName flag
        if 'zfsRepConfig_sendOptions_customName' in parameters and parameters['zfsRepConfig_sendOptions_customName']:
            parameters['customName_flag'] = f"--cn {parameters['zfsRepConfig_sendOptions_customName']}"
        else:
            parameters['customName_flag'] = ""
        
    return parameters

def replace_placeholders(template_content, parameters):
    for key, value in parameters.items():
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
