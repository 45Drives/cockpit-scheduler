import argparse
import subprocess
import datetime
import os

def generate_service_file(action_script, params, file_name):
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
    service_file_path = f'/etc/systemd/system/{file_name}.service'

    with open(service_file_path, 'w') as service_file:
        service_file.write(service_content)
    
    print(f'Service file generated: {service_file_path}')

def generate_timer_file(action, params, file_name):
    # schedule = ''
    # if 'pattern' in params:
    #     schedule += f"{params['pattern']} "
    # if 'seconds' in params:
    #     schedule += f"{int(params['seconds']):02d}"
    # else

    schedule = generate_on_calendar(params)
    print(f"schedule: {schedule}")

    timer_content = f"""[Unit]
Description={action} timer

[Timer]
OnCalendar={schedule}
Persistent=true

[Install]
WantedBy=timers.target
"""

    timer_file_path = f'/etc/systemd/system/{file_name}.timer'
    with open(timer_file_path, 'w') as timer_file:
        timer_file.write(timer_content)
    
    print(f'Timer file generated: {timer_file_path}')


def generate_on_calendar(schedule):
    expression = ""

    # Handle pattern or dayOfWeek
    if 'pattern' in schedule:
        if schedule['pattern'] in ['hourly', 'daily', 'weekly', 'monthly', 'yearly']:
            expression += schedule['pattern']
        elif 'dayOfWeek' in schedule:
            expression += schedule['dayOfWeek']

    # Handle year, month, day
    if 'year' in schedule:
        expression += f" {schedule['year']}"
    else:
        expression += " *"

    if 'month' in schedule:
        expression += f"-{schedule['month']}"
    else:
        expression += "-*"

    if 'day' in schedule:
        expression += f"-{schedule['day']}"
    else:
        expression += "-*"

    # Handle hour, minute, second
    if 'hour' in schedule:
        expression += f" {schedule['hour']}"
    else:
        expression += " *"

    if 'minute' in schedule:
        expression += f":{schedule['minute']}"
    else:
        expression += ":*"

    if 'second' in schedule:
        expression += f":{schedule['second']}"
    else:
        expression += ":*"

    return expression.strip()

def main():
  
    service_args = {
        'path':'usr/local/bin/create-snapshot.py',
        'filesystem':'tank/dozer',
        'recursive': False,
        'action':'create_snapshot',
    }

    timer_args = {
        # pattern can be any of: [hourly, daily, weekly, monthly, yearly], [Mon...Fri], [Mon, Wed], [15,30,45] 
        'minute': '*',
        'second': '00'
    }

    action_script = service_args['path'] + ' ' + service_args['filesystem']

    if service_args.get('recursive', False):
        action_script += "--r"

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    file_name = f'{service_args["action"]}_{timestamp}'

    generate_service_file(action_script, service_args, file_name)
    generate_timer_file(service_args['action'], timer_args, file_name)

if __name__ == "__main__":
    main()