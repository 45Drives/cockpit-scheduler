import argparse
import subprocess
import json
from datetime import datetime

class TaskExecutionResult:
    def __init__(self, exit_code, output, start_date, finish_date):
        self.exit_code = exit_code
        self.output = output
        self.start_date = start_date
        self.finish_date = finish_date

def run_systemctl_command(service_name):
    # Run systemctl command to fetch service information
    command = ['systemctl', 'show', service_name, '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp']
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if result.returncode != 0:
        raise Exception("Failed to execute systemctl command")

    # Parse the output
    lines = result.stdout.decode().strip().split('\n')
    exit_code = lines[2].split('=')[1]
    start_time = lines[0].split('=')[1]
    finish_time = lines[1].split('=')[1]
    
    return exit_code, start_time, finish_time


def run_journalctl_command(service_name, start_time):
    try:
        # Remove the day name and timezone since strptime does not handle timezones
        start_time_clean = ' '.join(start_time.split()[1:3])
        formatted_start_time = datetime.strptime(start_time_clean, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        print("Date formatting error:", e)
        return None

    # Run journalctl command to fetch logs since the start time
    command = ['journalctl', '-u', service_name, '--since', formatted_start_time, '--no-pager']
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if result.returncode != 0:
        raise Exception("Failed to execute journalctl command")

    return result.stdout.decode()


def get_task_execution_result(service_name):
    exit_code, start_time, finish_time = run_systemctl_command(service_name)
    output = run_journalctl_command(service_name, start_time)
    return TaskExecutionResult(exit_code, output, start_time, finish_time)


def main():
    parser = argparse.ArgumentParser(description="Get last task execution result")
    parser.add_argument('-u', '--unit', type=str, help='Full task filename / service filename')
    args = parser.parse_args()
    
    if args.unit:
        service_name = args.unit
        task_result = get_task_execution_result(service_name)
        
        task_result_json = json.dumps(task_result.__dict__, indent=4, default=str)
        print(task_result_json)
    else:
        print("Please provide a unit name with the -u option.")

if __name__ == "__main__":
    main()
