import subprocess
import sys
import os
import json
import configparser
from datetime import datetime, timedelta, timezone
import requests
import shlex
import re
from notify import get_notifier

notifier = get_notifier()

PROGRESS_RE = re.compile(r'(\d+)%')
DEFAULT_RCLONE_CONF = '/root/.config/rclone/rclone.conf'
SERVER_URL = 'https://cloud-sync.45d.io'

OAUTH_TYPES = {
    "drive": "drive",
    "google cloud storage": "cloud",
    "dropbox": "dropbox",
    # "onedrive": "onedrive",
}

def resolve_rclone_conf_path() -> str:
    # 1) explicit from task env (you can add it into the .env file)
    p = os.environ.get('cloudSyncConfig_rclone_config_path')
    if p:
        return p

    # 2) standard env that rclone understands
    p = os.environ.get('RCLONE_CONFIG')
    if p:
        return p

    # 3) user config (works for systemd --user units)
    home = os.path.expanduser('~')
    xdg = os.environ.get('XDG_CONFIG_HOME') or os.path.join(home, '.config')
    user_conf = os.path.join(xdg, 'rclone', 'rclone.conf')
    if os.path.isfile(user_conf):
        return user_conf

    # 4) legacy root fallback (keeps old/system tasks working)
    return DEFAULT_RCLONE_CONF

RCLONE_CONF_PATH = resolve_rclone_conf_path()

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

def normalize_to_utc(expiry: str) -> datetime:
    if not isinstance(expiry, str):
        raise ValueError(f"Expiry must be a string, got {type(expiry)}: {expiry}")

    s = expiry.strip()
    # Handle trailing Z
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'

    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"Failed to parse expiry '{expiry}' as ISO8601: {e}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt

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

            config.set(remote_name, "token", json.dumps(token_data))
            os.makedirs(os.path.dirname(RCLONE_CONF_PATH), exist_ok=True)
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
    command = ['rclone', f'--config={RCLONE_CONF_PATH}', options['type'], '-v']

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
    if options.get('transfers', 0) > 0:
        command.append(f'--transfers={options["transfers"]}')
        
    if '--stats-one-line' not in command:
        command.extend(['--stats-one-line', '--stats=1s'])
        
    extra = options.get('custom_args') or ''
    if extra.strip():
        parts = []
        for chunk in extra.split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts.extend(shlex.split(chunk))
        command.extend(parts)
        
    return command

def construct_paths(localPath, direction, targetPath):
    """
    Construct source and destination paths for rclone.
    """
    return (localPath, targetPath) if direction == 'push' else (targetPath, localPath)

def execute_command(command, src, dest, log_file_path=None):
    """
    Execute the constructed rclone command with streaming output and
    send progress updates to systemd via sd_notify. If log_file_path is
    set, tee the output into that file as well.
    """
    command.extend([src, dest])
    print(f"Executing command: {' '.join(command)}")

    # Let systemd know we’ve started the real work
    notifier.notify("STATUS=Starting transfer…")

    process = subprocess.Popen(
        command,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1
    )

    last_percent = None
    log_fh = None

    # Open the user log file if one was requested
    if log_file_path:
        try:
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        except Exception:
            # If dirname is empty or invalid, just ignore; open() will fail if needed
            pass
        try:
            # line-buffered for immediate writes
            log_fh = open(log_file_path, 'a', buffering=1)
        except Exception as e:
            print(f"WARNING: Failed to open log file {log_file_path}: {e}")
            log_fh = None

    try:
        assert process.stdout is not None
        for line in process.stdout:
            # write to optional log file
            if log_fh:
                try:
                    log_fh.write(line)
                except Exception as e:
                    # Don't break the transfer if logging fails
                    print(f"WARNING: Failed to write to log file {log_file_path}: {e}")
                    log_fh = None

            # keep logs in journal
            sys.stdout.write(line)
            sys.stdout.flush()

            # simple percent parse: first "<digits>%"
            m = PROGRESS_RE.search(line)
            if m:
                pct = int(m.group(1))
                if pct != last_percent:
                    last_percent = pct
                    notifier.notify(f"STATUS=Transferring… {pct}% complete")

        process.wait()
    finally:
        if log_fh:
            try:
                log_fh.close()
            except Exception:
                pass

        if process.returncode == 0:
            notifier.notify("STATUS=Finishing up…")
        else:
            notifier.notify("STATUS=Transfer failed")

        if process.returncode != 0:
            print(f"Error: rclone exited with code {process.returncode}")
            sys.exit(process.returncode)
        else:
            print("Rclone task execution completed.")


def execute_rclone(options):
    """
    Validate token, refresh if necessary, and execute rclone task.
    """
    try:
        config = load_rclone_config()
        remote_name = options.get('rclone_remote')
        if not remote_name:
            raise ValueError("No remote name specified in options")

        validate_and_refresh_token(config, remote_name)

        command = build_rclone_command(options)
        src, dest = construct_paths(options['local_path'], options['direction'], options['target_path'])
        execute_command(command, src, dest, options.get('log_file_path') or None)
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
        'log_file_path': os.environ.get('cloudSyncConfig_rcloneOptions_log_file_path', ''),
    }

def str_to_bool(value):
    return str(value).lower() in ('true', '1', 't', 'yes', 'y')

def main():
    """
    Main execution entry point.
    """
    notifier.notify("STATUS=Starting task…")
    notifier.notify("READY=1")
    notifier.notify("STATUS=Running task…")
    print("Starting rclone script...")
    # print('env:', os.environ)
    options = parse_arguments()
    # print(f"Options: {options}")
    execute_rclone(options)
    notifier.notify("STATUS=Finishing up…")
    print("Rclone task execution completed.")
    


if __name__ == '__main__':
    notifier.notify("STATUS=Starting task…")
    main()
