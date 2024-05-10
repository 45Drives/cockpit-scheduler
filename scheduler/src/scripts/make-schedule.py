import subprocess
import argparse
import json

def read_template_file(template_file_path):
    with open(template_file_path, 'r') as file:
        return file.read()
    

def read_schedule_json(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file: {file_path}")
        return None

def interval_to_on_calendar(interval):
    parts = []
    
    # Handle dayOfWeek if present
    if 'dayOfWeek' in interval:
        day_of_week = ','.join(interval['dayOfWeek'])
        parts.append(day_of_week)
    
    # Initialize default values for date components
    year_part, month_part, day_part = '*', '*', '*'
    
    # Handle year, month, and day
    for unit in ['year', 'month', 'day']:
        if unit in interval:
            value = interval[unit]['value']
            if unit == 'year':
                year_part = value
            elif unit == 'month':
                month_part = value
            elif unit == 'day':
                day_part = value
    
    # Construct the date part
    date_part = f'{year_part}-{month_part}-{day_part}'
    parts.append(date_part)
    
    # Handle hour, minute, and second
    hour = interval.get('hour', {}).get('value', '*')
    minute = interval.get('minute', {}).get('value', '*')
    second = interval.get('second', {}).get('value', '0')
    time_part = f'{hour}:{minute}:{second}'
    
    parts.append(time_part)
    
    return 'OnCalendar=' + ' '.join(parts)

def generate_concrete_file(template_content, output_file_path):
    with open(output_file_path, 'w') as file:
        file.write(template_content)
    
def restart_timer(unit_name):
    subprocess.run(['sudo', 'systemctl', 'reset-failed'], check=True)
    subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
    subprocess.run(['sudo', 'systemctl', 'enable', f'{unit_name}'], check=True)
    subprocess.run(['sudo', 'systemctl', 'restart', f'{unit_name}'], check=True)
    print(f'{unit_name} has been restarted')


def main():
    parser = argparse.ArgumentParser(description='Generate Timer File from Template + JSON Files')
    parser.add_argument('-n', '--name', type=str, help='full task/unit name')
    parser.add_argument('-tt', '--timerTemplate', type=str, help='template timer file path')
    parser.add_argument('-s', '--schedule', type=str, help='schedule json')
    
    args = parser.parse_args()

    full_unit_name = args.name
    template_timer_path = args.timerTemplate
    schedule_json_path = args.schedule
    
    
    name_parts = full_unit_name.split('_')
    prefix = name_parts[:1]
    template_name = name_parts[2]
    task_name = '_'.join(name_parts[3:])
    
    output_path_timer = f"/etc/systemd/system/{full_unit_name}.timer"
    schedule_data = read_schedule_json(schedule_json_path)
    timer_template_content = read_template_file(template_timer_path)
    on_calendar_lines = [interval_to_on_calendar(interval) for interval in schedule_data['intervals']]
    on_calendar_lines_str = "\n".join(on_calendar_lines)
    timer_template_content = timer_template_content.replace("{description}", "Timer for " + template_name + "_" + task_name).replace("{on_calendar_lines}", on_calendar_lines_str)
    
    # Generate concrete timer file
    generate_concrete_file(timer_template_content, output_path_timer)
    print(timer_template_content)
    print("Concrete timer file generated successfully.")
    
    restart_timer(full_unit_name)
    
if __name__ == "__main__":
	main()