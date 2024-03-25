import argparse
import subprocess
import datetime
import os

def generate_service_file(params):
    action_script = params['path'] + ' ' + params['filesystem']

    if params.get('recursive', False):
        action_script += "--r"
    # if 'name' in params:
    #     action_script += f"--custom-name {params['name']}"

    service_content = f"""[Unit]
Description={params['action']} service

[Service]
Type=oneshot
ExecStart=python3 {action_script}
Restart=on-failure
RestartSec=10
StartLimitBurst=5
StartLimitInterval=10s

[Install]
WantedBy=multi-user.target
"""
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    service_file_name = f'{params["action"]}_{timestamp}.service'
    service_file_path = f'/etc/systemd/system/{service_file_name}'

    with open(service_file_path, 'w') as service_file:
        service_file.write(service_content)
    
    print(f'Service file generated: {service_file_path}')

def main():
    args = {
        'path':'usr/local/bin/create-snapshot.py',
        'filesystem':'tank/dozer',
        'recursive': False,
        'action':'create_snapshot',
    }

    generate_service_file(args)

if __name__ == "__main__":
    main()
    