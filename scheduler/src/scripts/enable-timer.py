import subprocess
import sys

def enable_task_timer(unit_name):
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    subprocess.run(['sudo', 'systemctl', 'enable', f'{unit_name}'], check=True)
    subprocess.run(['sudo', 'systemctl', 'start', f'{unit_name}'], check=True)
    
    print(f"{unit_name} has been enabled")
        
def main():
    unit_name = sys.argv[1]
    timer_name = unit_name + '.timer'
    enable_task_timer(timer_name)

if __name__ == "__main__":
	main()