import subprocess
import sys
import os

def stop_task_now(unit_name):
    try:
        service = f'{unit_name}.service'
        # Stop the service AND reset its failure state so systemd won't
        # schedule any more automatic restarts (Restart=on-failure).
        subprocess.run(['sudo', 'systemctl', 'stop', service], check=True)
        subprocess.run(['sudo', 'systemctl', 'reset-failed', service],
                       check=False)  # non-fatal if not in failed state

    except subprocess.CalledProcessError as e:
        print(f"Failed to stop task: {e}")
        sys.exit(1)
        
def check_for_service_file(unit_name):
    system_dir = '/etc/systemd/system/'
    prefix = "houston_scheduler_"
    suffix = '.service'
    
    for file in os.listdir(system_dir):
        if file.startswith(prefix) and file.endswith(suffix):
            base_name = file[:file.rfind('.')]
            if base_name == unit_name:
                return True
    return False

def main():
    unit_name = sys.argv[1]
    
    if check_for_service_file(unit_name):
        stop_task_now(unit_name)
    else:
        print(f'error: could not find task service file')
    
if __name__ == "__main__":
    main()