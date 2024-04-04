def generate_calendar_expression(schedule):
    pattern = schedule['pattern']
    expression = ''

    # Handle yearly pattern
    if pattern == 'yearly':
        expression = 'yearly'

    # Handle monthly pattern
    elif pattern == 'monthly':
        day = schedule.get('day', '*')
        expression = f'monthly {day}'

    # Handle weekly pattern
    elif pattern == 'weekly':
        dayOfWeek = schedule['dayOfWeek']
        expression = f'weekly {dayOfWeek}'

    # Handle daily pattern
    elif pattern == 'daily':
        hour = schedule.get('hour', '08')
        minute = schedule.get('minute', '00')
        second = schedule.get('second', '00')
        expression = f'daily {hour}:{minute}:{second}'

    # Handle hourly pattern
    elif pattern == 'hourly':
        expression = 'hourly'

    # Handle custom patterns
    else:
        # Split the pattern string into parts
        pattern_parts = pattern.split()
        # First part of the pattern is the frequency
        frequency = pattern_parts[0]

        if frequency == 'monthly':
            day = schedule.get('day', '*')
            expression = f'monthly {day}'
        elif frequency == 'weekly':
            dayOfWeek = schedule['dayOfWeek']
            expression = f'weekly {dayOfWeek}'
        elif frequency == 'daily':
            hour = schedule.get('hour', '08')
            minute = schedule.get('minute', '00')
            second = schedule.get('second', '00')
            expression = f'daily {hour}:{minute}:{second}'
        elif frequency == 'hourly':
            expression = 'hourly'
        else:
            # Handle custom frequency pattern
            expression += frequency

        # Process the remaining parts of the pattern
            if '..' in pattern:
                # Handle range
                start, end = pattern.split('..')
                expression += f'{start}-{end}'
            elif '/' in pattern:
                # Handle step value
                value, step = pattern.split('/')
                expression += f'/{step}'
            elif ',' in pattern:
                # Handle list
                items = pattern.split(',')
                expression += ','.join(items)
            else:
                # Add single value
                expression += pattern

    print(f'OnCalendar Expression Generated: {expression}')
    return expression
