import subprocess
import argparse

def disable_task_timer(unit_name):
    subprocess.run(['sudo', 'systemctl', 'stop', f'{unit_name}'], check=True)
    subprocess.run(['sudo', 'systemctl', 'disable', f'{unit_name}'], check=True)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    
    print(f"{unit_name} has been disabled")

def main():
    parser = argparse.ArgumentParser(description='toggle task schedule/timer on or off')
    parser.add_argument('-u', '--unit', type=str, help='unit name')
    
    args = parser.parse_args()
    unit_name = args.unit
    timer_name = unit_name + '.timer'
    disable_task_timer(timer_name)

if __name__ == "__main__":
	main()