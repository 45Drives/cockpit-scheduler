import subprocess
import sys

def disable_task_timer(unit_name):
    subprocess.run(['sudo', 'systemctl', 'stop', f'{unit_name}'], check=True)
    subprocess.run(['sudo', 'systemctl', 'disable', f'{unit_name}'], check=True)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    
    print(f"{unit_name} has been disabled")

def main():
    unit_name = sys.argv[1]
    timer_name = unit_name + '.timer'
    disable_task_timer(timer_name)

if __name__ == "__main__":
	main()