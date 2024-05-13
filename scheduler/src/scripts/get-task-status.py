import subprocess
import sys
import re

def get_unit_status(unit_name):
    # Command to run systemctl status with '.timer' suffix added
    command = ['systemctl', 'status', unit_name + '.timer', '--no-pager', '--output=cat']
    
    # Execute the command
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Handle cases where the command did not execute successfully
    if result.returncode != 0:
        # Decode and analyze stderr to provide a meaningful error message
        error_message = result.stderr.decode()
        if "could not be found" in error_message:
            print("Error: The specified timer does not exist or is disabled.")
        # else:
        #     print("Error running systemctl:", error_message)
        return None
    
    # Parse the output to find the active status
    output = result.stdout.decode()
    active_status_match = re.search(r'^\s*Active:\s*(\w+\s*\([^)]*\))', output, re.MULTILINE)

    if active_status_match:
        # Return the entire active status description
        return active_status_match.group(1).strip()
    else:
        # Specific message when no active status is found
        if "Loaded: loaded" in output:
            return "Timer is loaded but inactive."
        return "Active status not found in the systemctl output."

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <unit_name>")
        return
    unit_name = sys.argv[1]
    status = get_unit_status(unit_name)
    if status is not None:
        print(status)
    else:
        print("Task is not scheduled.")

if __name__ == "__main__":
    main()
