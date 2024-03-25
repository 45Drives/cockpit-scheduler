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

