# import os

# def generate_timer_file(dataset, schedule):
#     timer_content = f"""[Unit]
# Description=Scheduler Timer for {dataset}

# [Timer]
# OnCalendar={schedule}
# Persistent=true

# [Install]
# WantedBy=timers.target
# """

#     timer_file_path = f'/etc/systemd/system/{dataset}_scheduler.timer'
#     with open(timer_file_path, 'w') as timer_file:
#         timer_file.write(timer_content)
    
#     print(f'Timer file generated: {timer_file_path}')

# def main():
#     dataset = input('Enter dataset name: ')
#     action_script = input('Enter path to action script: ')
#     schedule = input('Enter schedule (e.g., "daily", "hourly", "*-*-* 00:00:00", etc.): ')

#     generate_service_file(dataset, action_script)
#     generate_timer_file(dataset, schedule)

# if __name__ == "__main__":
#     main()
