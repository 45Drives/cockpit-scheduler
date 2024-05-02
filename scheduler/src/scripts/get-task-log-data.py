import subprocess
import json
from datetime import datetime

# TEST CODE

class TaskExecutionResult:
    def __init__(self, exit_code, output, start_date, finish_date):
        self.exit_code = exit_code
        self.output = output
        self.start_date = start_date.isoformat()  # Convert datetime to ISO 8601 string
        self.finish_date = finish_date.isoformat()

def fetch_logs(service_name):
    command = f"journalctl -u {service_name} -o json --since today"
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print("Error fetching logs:", stderr.decode())
            return []
        return [json.loads(line) for line in stdout.decode().splitlines()]
    except Exception as e:
        print("An error occurred:", str(e))
        return []

def parse_logs(log_entries):
    results = []
    for entry in log_entries:
        start_date = datetime.fromtimestamp(float(entry['__REALTIME_TIMESTAMP']) / 1e6)
        exit_code = int(entry.get('_EXIT_STATUS', 0))
        output = entry.get('MESSAGE', '')
        finish_date = start_date  # This needs proper handling based on actual log data
        result = TaskExecutionResult(exit_code, output, start_date, finish_date)
        results.append(vars(result))  # Convert object to dictionary here
    return results

def main():
    service_name = "houston_scheduler_ZfsReplicationTask_test123.service"
    logs = fetch_logs(service_name)
    results = parse_logs(logs)
    print(json.dumps(results, indent=4))  # Print as JSON

if __name__ == "__main__":
    main()
