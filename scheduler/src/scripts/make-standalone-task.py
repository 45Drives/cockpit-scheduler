import argparse
import subprocess

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
                        
        if key.split('_')[0] == 'autoSnapConfig':
            flags = ['recursive', 'customName']
            for flag in flags:
                if f'autoSnapConfig_{flag}_flag' in parameters and parameters[f'autoSnapConfig_{flag}_flag'].lower() == 'true':
                    parameters[f'autoSnapConfig_{flag}_flag'] = f"--{flag}"
                else:
                    parameters[f'autoSnapConfig_{flag}_flag'] = ""
                    if flag == 'customName':
                        parameters['autoSnapConfig_customName'] = ""
        
    return parameters

def replace_service_placeholders(service_template_content, parameters):
    for key, value in parameters.items():
        placeholder = "{" + key + "}"
        service_template_content = service_template_content.replace(placeholder, value)
    return service_template_content

def generate_concrete_file(template_content, output_file_path):
    with open(output_file_path, 'w') as file:
        file.write(template_content)
        
    
def restart_timer(unit_name):
    subprocess.run(['sudo', 'systemctl', 'reset-failed'], check=True)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    subprocess.run(['sudo', 'systemctl', 'enable', f'{unit_name}'], check=True)
    subprocess.run(['sudo', 'systemctl', 'restart', f'{unit_name}'], check=True)
    print(f'{unit_name} has been restarted')


def main():
    parser = argparse.ArgumentParser(description='Generate Service File from Template + Env File')
    parser.add_argument('-st', '--serviceTemplate', type=str, help='template service file path')
    parser.add_argument('-e', '--env', type=str, help='env file path')
    
    args = parser.parse_args()
    template_service_path = args.serviceTemplate
    param_env_path = args.env
    
    param_env_filename = param_env_path.split('/')[-1]
    
    # Correctly split the filename and rejoin parts to form the full task name
    # This will ignore the first two components ('houston' and 'scheduler') and join the rest.
    parts = param_env_filename.split('_')
    task_instance_name = '_'.join(parts[2:])  # Join from the third element to the end
    task_instance_name = task_instance_name.split('.env')[0]  # Remove the file extension

    service_file_name = f'houston_scheduler_{task_instance_name}.service'
    output_path_service = f'/etc/systemd/system/{service_file_name}'
    
    service_template_content = read_template_file(template_service_path)
    
    # Parse keys/values from environment file
    parameters = parse_env_file(param_env_path)

    # Replace placeholders in service file template with environment variables
    service_template_content = replace_service_placeholders(service_template_content, parameters)
    service_template_content = service_template_content.replace("{task_name}", task_instance_name)
    service_template_content = service_template_content.replace("{env_path}", param_env_path)

    # Generate concrete service file
    generate_concrete_file(service_template_content, output_path_service)
    print(service_template_content)
    print("Standalone concrete service file generated successfully.")
    restart_timer(service_file_name)
    
if __name__ == "__main__":
	main()