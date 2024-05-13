import subprocess
import sys
import json

class TaskExecutionResult:
    def __init__(self, exit_code, output, start_date, finish_date):
        self.exit_code = exit_code
        self.output = output
        self.start_date = start_date
        self.finish_date = finish_date

def run_command(command):
    """Utility function to run a subprocess command."""
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if result.returncode != 0:
        raise Exception(f"Command failed: {result.stderr}")
    return result.stdout.strip()

def get_task_execution_result(service_name):
    # Fetch execution metadata using systemctl
    exec_info = run_command(['systemctl', 'show', service_name, '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp'])
    properties = dict(line.split('=', 1) for line in exec_info.decode().splitlines())
    
    exit_code = properties.get('ExecMainStatus', '0')
    start_time = properties.get('ExecMainStartTimestamp', '')
    finish_time = properties.get('ExecMainExitTimestamp', '')

    # Fetch logs using journalctl
    if start_time:
        output = run_command(['journalctl', '-r', '-u', service_name, '--since', start_time, '--no-pager']).decode()
    else:
        output = "No start time available."

    return TaskExecutionResult(exit_code, output, start_time, finish_time)

def main():
    unit_name = sys.argv[1]
    
    try:
        task_result = get_task_execution_result(unit_name)
        print(json.dumps(task_result.__dict__, indent=4, default=str))
    except Exception as e:
        print("Error:", str(e))
if __name__ == "__main__":
    main()