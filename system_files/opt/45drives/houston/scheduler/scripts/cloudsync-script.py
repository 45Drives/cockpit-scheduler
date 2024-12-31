import subprocess
import sys
import os
import json
import configparser
from datetime import datetime, timedelta, timezone
import requests

RCLONE_CONF_PATH = '/root/.config/rclone/rclone.conf'
# SERVER_URL = 'https://trusted-strangely-baboon.ngrok-free.app'
SERVER_URL = 'http://192.168.123.5:1337'

OAUTH_TYPES = {
    "drive": "drive",
    "google cloud storage": "cloud",
    "dropbox": "dropbox",
    # "onedrive": "onedrive",
}

def load_rclone_config():
    """
    Load and parse the rclone configuration file.
    """
    config = configparser.ConfigParser()
    config.read(RCLONE_CONF_PATH)
    return config

def get_remote_details(config, remote_name):
    """
    Retrieve remote details (type and token) from the rclone configuration.
    """
    if not config.has_section(remote_name):
        print(f"ERROR: Remote '{remote_name}' not found in rclone.conf")
        raise ValueError(f"Remote '{remote_name}' not found in rclone.conf")

    remote_type = config.get(remote_name, "type", fallback=None)

    if not remote_type:
        print(f"ERROR: No type found for remote '{remote_name}'")
        raise ValueError(f"No type found for remote '{remote_name}'")

    token = config.get(remote_name, "token", fallback=None)

    # Return token as None if it's not an OAuth type
    if remote_type.lower() not in OAUTH_TYPES:
        print(f"INFO: Remote '{remote_name}' is not an OAuth type. Type: {remote_type.lower()}, Token: None")
        return remote_type.lower(), None

    if not token:
        print(f"ERROR: No token found for OAuth remote '{remote_name}'")
        raise ValueError(f"No token found for OAuth remote '{remote_name}'")

    try:
        parsed_token = json.loads(token)
        return remote_type.lower(), parsed_token

    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON token for remote '{remote_name}': {token}")
        raise ValueError(f"Invalid JSON token for remote '{remote_name}': {token}") from e


def normalize_to_utc(expiry):
    """
    Normalize a timezone-offset datetime string to a UTC timezone-aware datetime object.
    """
    if '+' in expiry:
        dt_part, offset_part = expiry.split('+')
        sign = 1
    elif '-' in expiry and not expiry.endswith('Z'):
        dt_part, offset_part = expiry.split('-')
        sign = -1
    else:
        # Already in UTC
        return datetime.strptime(expiry, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)

    # Parse the main datetime part
    dt = datetime.strptime(dt_part, '%Y-%m-%dT%H:%M:%S.%f')

    # Parse the offset into hours and minutes
    offset_hours, offset_minutes = map(int, offset_part.split(':'))
    offset = timedelta(hours=offset_hours, minutes=offset_minutes)

    # Adjust the datetime to UTC
    dt_utc = dt - sign * offset

    # Return as timezone-aware datetime
    return dt_utc.replace(tzinfo=timezone.utc)

def normalize_to_utc(expiry):
    """
    Normalize a timezone-offset datetime string to a UTC timezone-aware datetime object.
    """
    if not isinstance(expiry, str):
        raise ValueError(f"Expiry must be a string, got {type(expiry)}: {expiry}")

    try:
        # Check for offset and split accordingly
        if '+' in expiry:
            dt_part, offset_part = expiry.split('+', maxsplit=1)
            sign = 1
        elif '-' in expiry and not expiry.endswith('Z'):
            dt_part, offset_part = expiry.rsplit('-', maxsplit=1)
            sign = -1
        else:
            # Handle UTC format without offset
            return datetime.strptime(expiry, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)

        # Truncate fractional seconds to six digits if present
        if '.' in dt_part:
            base, frac = dt_part.split('.')
            dt_part = f"{base}.{frac[:6]}"

        # Parse datetime and offset
        dt = datetime.strptime(dt_part, '%Y-%m-%dT%H:%M:%S.%f')
        offset_hours, offset_minutes = map(int, offset_part.split(':'))
        offset = timedelta(hours=offset_hours, minutes=offset_minutes)

        # Adjust datetime to UTC
        return (dt - sign * offset).replace(tzinfo=timezone.utc)

    except Exception as e:
        raise ValueError(f"Failed to normalize expiry '{expiry}' to UTC: {e}")


def is_token_expired(token_data):
    """
    Check if the token is expired based on the expiry time.
    """
    expiry = token_data.get("expiry")
    
    if not expiry:
        raise ValueError("No expiry information found in token")

    # Normalize the expiry to a UTC-aware datetime
    expiry_datetime = normalize_to_utc(expiry)
    # print(f'Token expiry: {expiry_datetime} vs now: {datetime.now(timezone.utc)}')
    
    # Compare with the current UTC time
    return datetime.now(timezone.utc) >= expiry_datetime

def refresh_token_via_server(config, remote_name, remote_type, token_data):
    """
    Refresh the token for the given remote using the Express server.
    """
    if remote_type not in OAUTH_TYPES:
        print(f"Remote type '{remote_type}' for '{remote_name}' does not support token refresh. Skipping.")
        return

    endpoint = OAUTH_TYPES[remote_type]
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise ValueError(f"No refresh token found for remote '{remote_name}'")

    try:
        response = requests.post(
            f"{SERVER_URL}/auth/refresh-token/{endpoint}",
            json={"refreshToken": refresh_token}
        )
        if response.status_code == 200:
            new_token_data = response.json()
            token_data["access_token"] = new_token_data["accessToken"]
            token_data["expiry"] = new_token_data["expiry"]

            # Update the rclone.conf file
            config.set(remote_name, "token", json.dumps(token_data))
            with open(RCLONE_CONF_PATH, "w") as conf_file:
                config.write(conf_file)

            print(f"Token refreshed and updated for remote '{remote_name}'")
        else:
            raise Exception(f"Failed to refresh token: {response.text}")
    except Exception as e:
        print(f"Error refreshing token for remote '{remote_name}': {e}")
        raise

def validate_and_refresh_token(config, remote_name):
    """
    Validate the token for the remote and refresh it if expired, skipping non-OAuth remotes.
    """
    remote_type, token_data = get_remote_details(config, remote_name)

    # Skip token validation for non-OAuth remotes
    if remote_type not in OAUTH_TYPES:
        print(f"Remote '{remote_name}' of type '{remote_type}' does not require OAuth token validation. Skipping.")
        return

    # Validate and refresh the token if needed
    if is_token_expired(token_data):
        print(f'Access token expired... Refreshing token...')
        refresh_token_via_server(config, remote_name, remote_type, token_data)

def build_rclone_command(options):
    """
    Construct the rclone command based on options.
    """
    command = ['rclone', options['type'], '-v']

    option_flags = {
        'check_first_flag': '--check-first',
        'checksum_flag': '--checksum',
        'update_flag': '--update',
        'ignore_existing_flag': '--ignore-existing',
        'dry_run_flag': '--dry-run',
        'ignore_size_flag': '--ignore-size',
        'inplace_flag': '--inplace',
        'no_traverse_flag': '--no-traverse',
    }

    for key, flag in option_flags.items():
        if options.get(key):
            command.append(flag)

    if int(options['bandwidth_limit_kbps']) > 0:
        command.append(f'--bwlimit={options["bandwidth_limit_kbps"]}')

    if options['include_pattern']:
        include_patterns = options['include_pattern'].split(',')
        for pattern in include_patterns:
            command.append(f'--include={pattern.strip()}')

    if options['exclude_pattern']:
        exclude_patterns = options['exclude_pattern'].split(',')
        for pattern in exclude_patterns:
            command.append(f'--exclude={pattern.strip()}')

    if options['multithread_chunk_size'] > 0:
        command.append(f'--multi-thread-chunk-size={options["multithread_chunk_size"]}{options["multithread_chunk_size_unit"]}')
    if options['multithread_cutoff'] > 0:
        command.append(f'--multi-thread-cutoff={options["multithread_cutoff"]}{options["multithread_cutoff_unit"]}')
    if options['multithread_streams'] > 0:
        command.append(f'--multi-thread-streams={options["multithread_streams"]}')
    if options['multithread_write_buffer_size'] > 0:
        command.append(f'--buffer-size={options["multithread_write_buffer_size"]}{options["multithread_write_buffer_size_unit"]}')
    if options['include_from_path']:
        command.append(f'--include-from={options["include_from_path"]}')
    if options['exclude_from_path']:
        command.append(f'--exclude-from={options["exclude_from_path"]}')
    if options['max_transfer_size'] > 0:
        command.append(f'--max-transfer={options["max_transfer_size"]}{options["max_transfer_size_unit"]}')
    if options['cutoff_mode']:
        command.append(f'--cutoff-mode={options["cutoff_mode"].upper()}')

    return command

def construct_paths(localPath, direction, targetPath):
    """
    Construct source and destination paths for rclone.
    """
    return (localPath, targetPath) if direction == 'push' else (targetPath, localPath)

def execute_command(command, src, dest):
    """
    Execute the constructed rclone command.
    """
    command.extend([src, dest])
    print(f"Executing command: {' '.join(command)}")

    process = subprocess.Popen(
        command,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        print(f"Error: {stderr}")
        sys.exit(1)
    else:
        print(stdout)

def execute_rclone(options):
    """
    Validate token, refresh if necessary, and execute rclone task.
    """
    try:
        config = load_rclone_config()
        remote_name = options.get('rclone_remote')
        if not remote_name:
            raise ValueError("No remote name specified in options")

        # print("Starting token validation...")
        validate_and_refresh_token(config, remote_name)
        # print("Finished token validation.")

        command = build_rclone_command(options)
        src, dest = construct_paths(options['local_path'], options['direction'], options['target_path'])
        # print(f"Source: {src}, Destination: {dest}")
        execute_command(command, src, dest)
    except Exception as e:
        print(f"Execution error: {e}")
        sys.exit(1)

def parse_arguments():
    """
    Parse environment variables into options.
    """
    return {
        'local_path': os.environ.get('cloudSyncConfig_local_path', ''),
        'direction': os.environ.get('cloudSyncConfig_direction', 'push'),
        'target_path': os.environ.get('cloudSyncConfig_target_path', ''),
        'type': os.environ.get('cloudSyncConfig_type', 'copy'),
        'rclone_remote': os.environ.get('cloudSyncConfig_rclone_remote', ''),
        'check_first_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_check_first_flag', 'False')),
        'checksum_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_checksum_flag', 'False')),
        'update_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_update_flag', 'False')),
        'ignore_existing_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_ignore_existing_flag', 'False')),
        'dry_run_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_dry_run_flag', 'False')),
        'transfers': int(os.environ.get('cloudSyncConfig_rcloneOptions_transfers', 0)),
        'include_pattern': os.environ.get('cloudSyncConfig_rcloneOptions_include_pattern', ''),
        'exclude_pattern': os.environ.get('cloudSyncConfig_rcloneOptions_exclude_pattern', ''),
        'custom_args': os.environ.get('cloudSyncConfig_rcloneOptions_custom_args', ''),
        'bandwidth_limit_kbps': int(os.environ.get('cloudSyncConfig_rcloneOptions_bandwidth_limit_kbps', 0)),
        'ignore_size_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_ignore_size_flag', 'False')),
        'inplace_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_inplace_flag', 'False')),
        'multithread_chunk_size': int(os.environ.get('cloudSyncConfig_rcloneOptions_multithread_chunk_size', 0)),
        'multithread_chunk_size_unit': os.environ.get('cloudSyncConfig_rcloneOptions_multithread_chunk_size_unit', 'MiB'),
        'multithread_cutoff': int(os.environ.get('cloudSyncConfig_rcloneOptions_multithread_cutoff', 0)),
        'multithread_cutoff_unit': os.environ.get('cloudSyncConfig_rcloneOptions_multithread_cutoff_unit', 'MiB'),
        'multithread_streams': int(os.environ.get('cloudSyncConfig_rcloneOptions_multithread_streams', 0)),
        'multithread_write_buffer_size': int(os.environ.get('cloudSyncConfig_rcloneOptions_multithread_write_buffer_size', 0)),
        'multithread_write_buffer_size_unit': os.environ.get('cloudSyncConfig_rcloneOptions_multithread_write_buffer_size_unit', 'KiB'),
        'include_from_path': os.environ.get('cloudSyncConfig_rcloneOptions_include_from_path', ''),
        'exclude_from_path': os.environ.get('cloudSyncConfig_rcloneOptions_exclude_from_path', ''),
        'max_transfer_size': int(os.environ.get('cloudSyncConfig_rcloneOptions_max_transfer_size', 0)),
        'max_transfer_size_unit': os.environ.get('cloudSyncConfig_rcloneOptions_max_transfer_size_unit', 'MiB'),
        'cutoff_mode': os.environ.get('cloudSyncConfig_rcloneOptions_cutoff_mode', 'HARD').lower(),
        'no_traverse_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_no_traverse_flag', 'False')),
    }

def str_to_bool(value):
    return str(value).lower() in ('true', '1', 't', 'yes', 'y')

def main():
    """
    Main execution entry point.
    """
    print("Starting rclone script...")
    # print('env:', os.environ)
    options = parse_arguments()
    # print(f"Options: {options}")
    execute_rclone(options)
    print("Rclone task execution completed.")

if __name__ == '__main__':
    main()
