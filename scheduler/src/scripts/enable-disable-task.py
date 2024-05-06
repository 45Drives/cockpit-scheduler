import subprocess
import argparse
import json

class TaskInstance:
    def __init__(self, name, template, parameters, schedule):
        self.name = name
        self.template = template
        self.parameters = parameters
        self.schedule = schedule.__dict__

def restart_timer(unit_name):
	subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
	subprocess.run(['sudo', 'systemctl', 'enable', f'{unit_name}'], check=True)
	subprocess.run(['sudo', 'systemctl', 'restart', f'{unit_name}'], check=True)
	print(f'{unit_name} has been restarted')



# full_schedule_filename = houston_scheduler_<TEMPLATE_NAME>_<TASK_NAME>.timer

def enable_task_timer(full_schedule_filename):
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    
    # Enable the timer
    subprocess.run(['sudo', 'systemctl', 'enable', f'{full_schedule_filename}'], check=True)
    
    # Start the timer
    subprocess.run(['sudo', 'systemctl', 'start', f'{full_schedule_filename}'], check=True)
    
    # Optionally, check the status of the timer
    # subprocess.run(['sudo', 'systemctl', 'status', f'{full_schedule_filename}'], check=True)

def disable_task_timer(full_schedule_filename):
    # Stop the timer
    subprocess.run(['sudo', 'systemctl', 'stop', f'{full_schedule_filename}'], check=True)
    
    # Disable the timer
    subprocess.run(['sudo', 'systemctl', 'disable', f'{full_schedule_filename}'], check=True)
    
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)