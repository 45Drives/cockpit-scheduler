import subprocess
import argparse
   
def check_is_enabled(unit_name):
    try:
        # Running the systemctl command to check if the service is enabled
        result = subprocess.run(['sudo', 'systemctl', 'is-enabled', unit_name],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        # Processing the output
        output = result.stdout.decode().strip()  # Use strip() to clean up any leading/trailing whitespace
       
        return output
    except subprocess.CalledProcessError as e:
        # Handling the error (e.g., service not found)
        print(f"Error checking status of {unit_name}: {e}")
        
def main():
    parser = argparse.ArgumentParser(description='toggle task schedule/timer on or off')
    parser.add_argument('-u', '--unit', type=str, help='unit name')
    
    args = parser.parse_args()
    unit_name = args.unit
    timer_name = unit_name + '.timer'
    
    print(check_is_enabled(timer_name))

if __name__ == "__main__":
	main()