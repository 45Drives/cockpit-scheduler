import subprocess
import argparse
from datetime import datetime
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

def get_task_logs_until(service_name, until_time):
    # Fetch logs using journalctl
    if until_time:
        output = run_command(['journalctl', '-r', '-u', service_name, '--until', until_time, '--no-pager']).decode()
    else:
        output = "No until time available."

    return output

def main():
    parser = argparse.ArgumentParser(description="Get last task logs until time provided")
    parser.add_argument('-u', '--unit', type=str, required=True, help='Full task filename / service filename')
    parser.add_argument('-t', '--timestamp', type=str, required=True, help='timestamp to get logs until')
    args = parser.parse_args()
    
    unit_name = args.unit
    timestamp = args.timestamp
    
    try:
        task_result = get_task_logs_until(unit_name, timestamp)
        print(task_result)
    except Exception as e:
        print("Error:", str(e))
if __name__ == "__main__":
    main()

