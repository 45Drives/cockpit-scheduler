import subprocess
import argparse
import os

def run_task_now(unit_name):
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    # Start the service 
    subprocess.run(['sudo', 'systemctl', 'start', f'{unit_name}.service'], check=True)

def check_for_service_file(unit_name):
    system_dir = '/etc/systemd/system/'
    prefix = "houston_scheduler_"
    suffix = '.service'
    
    # Check for service file presence
    for file in os.listdir(system_dir):
        if file.startswith(prefix) and file.endswith(suffix):
            base_name = file[:file.rfind('.')]
            if base_name == unit_name:
                return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Run task service file ad hoc")
    parser.add_argument('-u', '--unit', type=str, help='full task filename / service filename')
    args = parser.parse_args()
    unit_name = args.unit
    
    if check_for_service_file(unit_name):
        run_task_now(unit_name)
    else:
        print(f'error: could not find task service file')
    
    
if __name__ == "__main__":
    main()