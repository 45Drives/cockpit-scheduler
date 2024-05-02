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
    

def main():
    parser = argparse.ArgumentParser(description='Generate Timer File from Template + JSON Files')
    parser.add_argument('-n', '--name', type=str, help='full task name')
    parser.add_argument('-tt', '--timerTemplate', type=str, help='template timer file path')
    parser.add_argument('-s', '--schedule', type=str, help='schedule json')
    
    args = parser.parse_args()

    param_name = args.name
    template_timer_path = args.timerTemplate
    schedule_json_path = args.schedule
    
    # param_json_filename = schedule_json_path.split('/')[-1]
    # task_instance_name = param_json_filename.split('_')[3].split('.')[0]
    name_parts = param_name.split('_')
    prefix = name_parts[0]
    template_name = name_parts[1]
    task_name = name_parts[-1]
    
    timer_file_name = param_name + '.timer'
    output_path_timer = f"/etc/systemd/system/{timer_file_name}"
    schedule_data = read_schedule_json(schedule_json_path)
    timer_template_content = read_template_file(template_timer_path)
    on_calendar_lines = [interval_to_on_calendar(interval) for interval in schedule_data['intervals']]
    on_calendar_lines_str = "\n".join(on_calendar_lines)
    timer_template_content = timer_template_content.replace("{description}", "Timer for " + task_name + " (" + template_name + ")").replace("{on_calendar_lines}", on_calendar_lines_str)
    
    # Generate concrete timer file
    generate_concrete_file(timer_template_content, output_path_timer)
    print(timer_template_content)
    print("Concrete timer file generated successfully.")
    
if __name__ == "__main__":
	main()