import os
import subprocess
import sys

def delete_task_files(unit_name):
    system_dir = '/etc/systemd/system/'
    
    prefix = "houston_scheduler_"
    suffixes = ['.env', '.json', '.service', '.timer','.txt']
    deleted_count = 0
    
    # Iterate through each file in the system directory
    for file in os.listdir(system_dir):
        # Check if the file matches the pattern for task files
        if file.startswith(prefix) and file.endswith(tuple(suffixes)):
            base_name = file[:file.rfind('.')]
            if base_name == unit_name:
                # If it matches the task name/unit, delete the file
                full_path = os.path.join(system_dir, file)
                os.remove(full_path)
                deleted_count += 1
                print(f"Deleted file: {full_path}")

def check_for_timer_file(unit_name):
    system_dir = '/etc/systemd/system/'
    prefix = "houston_scheduler_"
    suffix = '.timer'
    
    # Check for timer file presence
    for file in os.listdir(system_dir):
        print(f"Checking file: {file}")  # Debugging output
        if file.startswith(prefix) and file.endswith(suffix):
            base_name = file[:file.rfind('.')]
            print(f"Found timer file with base_name: {base_name}")  # Debugging output
            if base_name == unit_name:
                print(f"Timer file for unit {unit_name} exists.")  # Debugging output
                return True

    return False

def stop_systemd_timer(unit_name):
    # Stop the timer
    subprocess.run(['sudo', 'systemctl', 'stop', f'{unit_name}.timer'], check=True)
    # Disable the timer
    subprocess.run(['sudo', 'systemctl', 'disable', f'{unit_name}.timer'], check=True)
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'reset-failed'], check=True)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)

def remove_systemd_service(unit_name):
    # Stop the service
    subprocess.run(['sudo', 'systemctl', 'stop', f'{unit_name}.service'], check=True)
    # Disable the service
    subprocess.run(['sudo', 'systemctl', 'disable', f'{unit_name}.service'], check=True)
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)

def main():
    unit_name = sys.argv[1]
    
    if check_for_timer_file(unit_name):
        stop_systemd_timer(unit_name)
    remove_systemd_service(unit_name)
    delete_task_files(unit_name)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    
if __name__ == "__main__":
    main()
    
    
    