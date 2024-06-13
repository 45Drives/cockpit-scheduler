import subprocess
import sys
import os

def run_task_now(unit_name):
    try:
        # Reload systemd to recognize new or changed units
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        # Start the service 
        subprocess.run(['sudo', 'systemctl', 'start', f'{unit_name}.service'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to run task: {e}")
        sys.exit(1)
        
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
    unit_name = sys.argv[1]
    
    if check_for_service_file(unit_name):
        run_task_now(unit_name)
    else:
        print(f'error: could not find task service file')
    
if __name__ == "__main__":
    main()