import subprocess
import sys
import re

def get_unit_status(unit_name):
    # Command to run systemctl status with '.timer' suffix added
    command = ['systemctl', 'status', unit_name + '.timer', '--no-pager', '--output=cat']
    
    # Execute the command
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    
    # Check if the command executed successfully
    if result.returncode != 0:
        print("Error running systemctl:", result.stderr.decode())
        return None
    
    # Parse the output to find the active status
    # Regex updated to extract just the immediate status portion, excluding timestamps or other details
    active_status_match = re.search(r'^\s*Active:\s*(active \([^)]+\))', result.stdout.decode(), re.MULTILINE)
    
    if active_status_match:
        # Return the matched group which contains the specific active status
        return active_status_match.group(1)
    else:
        print("Active status not found in the systemctl output.")
        return None

def main():
    unit_name = sys.argv[1]
    status = get_unit_status(unit_name)
    if status is not None:
        print(status)

if __name__ == "__main__":
    main()