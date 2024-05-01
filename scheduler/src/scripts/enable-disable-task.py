import subprocess
import argparse
import json

class TaskInstance:
    def __init__(self, name, template, parameters, schedule):
        self.name = name
        self.template = template
        self.parameters = parameters
        self.schedule = schedule.__dict__






def manage_systemd_service(timer_file_name):
    # Reload systemd to recognize new or changed units
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    
    # Enable the timer
    subprocess.run(['sudo', 'systemctl', 'enable', f'houston_scheduler_{timer_file_name}'], check=True)
    
    # Start the timer
    subprocess.run(['sudo', 'systemctl', 'start', f'houston_scheduler_{timer_file_name}'], check=True)
    
    # Optionally, check the status of the timer
    subprocess.run(['sudo', 'systemctl', 'status', f'houston_scheduler_{timer_file_name}'], check=True)

