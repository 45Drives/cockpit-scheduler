import os
import subprocess
import argparse

def delete_task_files(unit, system_dir='/etc/systemd/system/'):
    prefix = "houston_scheduler_"
    suffixes = ['.env', '.json', '.service', '.timer']
    deleted_count = 0
    
    # Iterate through each file in the system directory
    for file in os.listdir(system_dir):
        # Check if the file matches the pattern for task files
        if file.startswith(prefix) and file.endswith(tuple(suffixes)):
            base_name = file[:file.rfind('.')]
            if base_name == unit:
                # If it matches the task name/unit, delete the file
                full_path = os.path.join(system_dir, file)
                os.remove(full_path)
                deleted_count += 1
                print(f"Deleted file: {full_path}")
    
    return deleted_count

def stop_systemd_timer(unit_name):
    # Stop the timer
    subprocess.run(['sudo', 'systemctl', 'stop', f'{unit_name}.timer'], check=True)
    # Disable the timer
    subprocess.run(['sudo', 'systemctl', 'disable', f'{unit_name}.timer'], check=True)
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)

def main():
    parser = argparse.ArgumentParser(description='Remove task files from system')
    parser.add_argument('-u', '--unit', type=str, help='name of task to remove')
    args = parser.parse_args()
    unit_name = args.unit
    system_dir = '/etc/systemd/system/'
    
    stop_systemd_timer(unit_name)
    delete_task_files(unit_name, system_dir)
    
if __name__ == "__main__":
    main()
    
    
    