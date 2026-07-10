import subprocess
import sys
import os
import json
import configparser
from datetime import datetime, timedelta, timezone
import requests
import shlex
import re
import traceback
import time
from notify import get_notifier


class SafeStream:
    """Wrap stdout/stderr so broken pipes don't crash the script."""
    def __init__(self, stream):
        self._stream = stream
    def write(self, data):
        try:
            return self._stream.write(data)
        except Exception:
            return 0
    def flush(self):
        try:
            return self._stream.flush()
        except Exception:
            return None
    def isatty(self):
        try:
            return self._stream.isatty()
        except Exception:
            return False
    def fileno(self):
        try:
            return self._stream.fileno()
        except Exception:
            return -1
    def __getattr__(self, name):
        return getattr(self._stream, name)

sys.stdout = SafeStream(sys.stdout)
sys.stderr = SafeStream(sys.stderr)

notifier = get_notifier()

DEBUG_LOG = os.environ.get("CLOUDSYNC_DEBUG_LOG", "/tmp/cloudsync_debug.log")
DEBUG_ENABLED = os.environ.get("CLOUDSYNC_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")

def dbg(msg: str):
    if not DEBUG_ENABLED:
        return
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass

def int_from_env(name, default):
    return int_from_value(os.environ.get(name, str(default)), default)

def int_from_value(value, default):
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def stats_interval_from_value(value, default):
    value = str(value or "").strip()
    if not value:
        return default
    if not re.match(r'^\d+(?:ms|s|m|h)$', value):
        return default
    return value

PROGRESS_RE = re.compile(r'(\d+(?:\.\d+)?)%')
BYTE_PROGRESS_RE = re.compile(
    r'(?P<done>\d+(?:\.\d+)?)\s*(?P<done_unit>[KMGTPE]?i?B|[KMGTPE]?B|B)\s*/\s*'
    r'(?P<total>\d+(?:\.\d+)?)\s*(?P<total_unit>[KMGTPE]?i?B|[KMGTPE]?B|B)',
    re.IGNORECASE,
)
COUNT_PROGRESS_RE = re.compile(r'\b(?:Checks|Deleted|Renamed|Transferred):\s*(\d+)\s*/\s*(\d+)\b', re.IGNORECASE)
DEFAULT_STATS_INTERVAL = os.environ.get("CLOUDSYNC_RCLONE_STATS_INTERVAL", "10s")
DEFAULT_STALL_TIMEOUT_SECONDS = int_from_env("CLOUDSYNC_STALL_TIMEOUT_SECONDS", 3600)
DEFAULT_PROGRESS_LOG_HEARTBEAT_SECONDS = int_from_env("CLOUDSYNC_PROGRESS_LOG_HEARTBEAT_SECONDS", 60)
PROCESS_ACTIVITY_CPU_TICKS = 20
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
    
ISO_WITH_OFFSET_RE = re.compile(
    r'^(?P<date>\d{4}-\d{2}-\d{2})T'
    r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})'
    r'(?P<fraction>\.\d+)?'
    r'(?P<tz>Z|[+-]\d{2}:\d{2})$'
)

def normalize_to_utc(expiry: str) -> datetime:
    if not isinstance(expiry, str):
        raise ValueError(f"Expiry must be a string, got {type(expiry)}: {expiry}")

    s = expiry.strip()
    m = ISO_WITH_OFFSET_RE.match(s)
    if not m:
        raise ValueError(f"Failed to parse expiry '{expiry}' as ISO8601: unsupported format")

    parts = m.groupdict()

    # Fractional seconds → microseconds (pad or trim to 6 digits)
    frac = parts["fraction"] or ""
    if frac:
        micros = int((frac[1:] + "000000")[:6])  # drop the dot and normalize length
    else:
        micros = 0

    # Base naive datetime
    dt = datetime(
        int(parts["date"][0:4]),
        int(parts["date"][5:7]),
        int(parts["date"][8:10]),
        int(parts["hour"]),
        int(parts["minute"]),
        int(parts["second"]),
        micros,
    )

    tz_str = parts["tz"]
    if tz_str == "Z":
        tzinfo = timezone.utc
    else:
        # tz like +HH:MM or -HH:MM
        sign = 1 if tz_str[0] == "+" else -1
        offset_hours = int(tz_str[1:3])
        offset_minutes = int(tz_str[4:6])
        delta = timedelta(hours=sign * offset_hours, minutes=sign * offset_minutes)
        tzinfo = timezone(delta)

    dt = dt.replace(tzinfo=tzinfo)
    return dt.astimezone(timezone.utc)


def is_token_expired(token_data):
    """
    Check if the token is expired based on the expiry time.
    """
    expiry = token_data.get("expiry")
    if not expiry:
        raise ValueError("No expiry information found in token")

    expiry_datetime = normalize_to_utc(expiry)
    now = datetime.now(timezone.utc)
    print(f"Token expiry: {expiry_datetime.isoformat()} | now: {now.isoformat()}")
    return now >= expiry_datetime

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
    command = ['rclone', f'--config={RCLONE_CONF_PATH}', options['type']]

    # Parse custom args first so we can inspect them
    extra = options.get('custom_args') or ''
    extra_parts = []
    if extra.strip():
        for chunk in extra.split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            extra_parts.extend(shlex.split(chunk))

    # Does user already control log level?
    def is_log_flag(arg: str) -> bool:
        if arg in ('-q', '-v', '-vv', '-vvv', '--quiet', '--verbose'):
            return True
        if arg == '--log-level':
            return True
        if arg.startswith('--log-level='):
            return True
        return False

    has_log_flag = any(is_log_flag(p) for p in extra_parts)

    # Default verbosity if user didn’t specify
    if not has_log_flag:
        command.append('-v')
        
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
        
    def has_flag(parts, *names):
        return any(arg in names or any(arg.startswith(f"{name}=") for name in names) for arg in parts)

    # Show periodic transfer stats for the UI, but do not force the old 1s
    # cadence. That flooded journald/Cockpit with identical rclone lines during
    # long sync checks and Dropbox finalization.
    all_parts = command + extra_parts
    if not has_flag(all_parts, '--stats-one-line', '--stats-one-line-date'):
        command.append('--stats-one-line')
    if not has_flag(all_parts, '--stats'):
        command.append(f'--stats={stats_interval_from_value(options.get("stats_interval"), DEFAULT_STATS_INTERVAL)}')
        
    command.extend(extra_parts)
        
    return command

def construct_paths(localPath, direction, targetPath):
    """
    Construct source and destination paths for rclone.
    """
    return (localPath, targetPath) if direction == 'push' else (targetPath, localPath)

def progress_fingerprint(line, pct):
    """
    Return a compact marker for rclone's reported work. Repeated 0 B / 0 B
    stats produce the same marker, while bytes, checks, deletes, or percent
    changes produce a new one.
    """
    markers = []
    if pct is not None:
        markers.append(("pct", pct))

    byte_match = BYTE_PROGRESS_RE.search(line)
    if byte_match:
        markers.append((
            "bytes",
            byte_match.group("done"),
            byte_match.group("done_unit").lower(),
            byte_match.group("total"),
            byte_match.group("total_unit").lower(),
        ))

    counters = COUNT_PROGRESS_RE.findall(line)
    if counters:
        markers.extend(("counter", done, total) for done, total in counters)

    return tuple(markers) if markers else None

def process_activity_fingerprint(pid):
    """
    Capture cheap process-level activity counters. This helps avoid false
    stall detection during quiet rclone phases that are still burning CPU or
    issuing syscalls while visible transfer stats remain unchanged.
    """
    if not pid:
        return None

    stat_fingerprint = None
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            stat = f.read()
        close_paren = stat.rfind(")")
        fields = stat[close_paren + 2:].split()
        if len(fields) >= 15:
            stat_fingerprint = (int(fields[11]), int(fields[12]))
    except Exception:
        pass

    io_fingerprint = None
    try:
        io_values = {}
        with open(f"/proc/{pid}/io", "r") as f:
            for raw in f:
                key, _, value = raw.partition(":")
                if key in ("syscr", "read_bytes"):
                    io_values[key] = int(value.strip())
        io_fingerprint = tuple(io_values.get(key, 0) for key in ("syscr", "read_bytes"))
    except Exception:
        pass

    if stat_fingerprint is None and io_fingerprint is None:
        return None
    return (stat_fingerprint, io_fingerprint)

def process_activity_changed(previous, current):
    if previous is None or current is None:
        return False

    previous_stat, previous_io = previous
    current_stat, current_io = current

    if previous_io is not None and current_io is not None:
        if current_io != previous_io:
            return True

    if previous_stat is not None and current_stat is not None:
        previous_ticks = sum(previous_stat)
        current_ticks = sum(current_stat)
        if current_ticks - previous_ticks >= PROCESS_ACTIVITY_CPU_TICKS:
            return True

    return False

def abort_process(process, reason):
    print(f"ERROR: {reason}")
    notifier.notify(f"STATUS={reason}")

    try:
        process.terminate()
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass

def execute_command(
    command,
    src,
    dest,
    log_file_path=None,
    stall_timeout_seconds=DEFAULT_STALL_TIMEOUT_SECONDS,
    progress_log_heartbeat_seconds=DEFAULT_PROGRESS_LOG_HEARTBEAT_SECONDS,
):
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
    last_journal_percent = None
    last_progress_log_time = 0.0
    last_meaningful_progress_time = time.monotonic()
    last_progress_fingerprint = None
    last_process_activity_fingerprint = process_activity_fingerprint(process.pid)
    stalled_reason = None
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
            # simple percent parse: first "<digits>%"
            m = PROGRESS_RE.search(line)
            pct = float(m.group(1)) if m else None
            fingerprint = progress_fingerprint(line, pct)

            if fingerprint is not None and fingerprint != last_progress_fingerprint:
                last_progress_fingerprint = fingerprint
                last_meaningful_progress_time = time.monotonic()
            elif fingerprint is not None:
                activity = process_activity_fingerprint(process.pid)
                if process_activity_changed(last_process_activity_fingerprint, activity):
                    last_process_activity_fingerprint = activity
                    last_meaningful_progress_time = time.monotonic()
            elif fingerprint is None and line.strip():
                # Non-stats rclone output usually means active work, retries, or
                # a concrete error message. Count it as activity so very large
                # listings/check phases are not killed while they are talking.
                last_meaningful_progress_time = time.monotonic()
                last_process_activity_fingerprint = process_activity_fingerprint(process.pid)

            # Keep full detail in the debug log, but avoid repeating the same
            # transfer percentage in journald/user logs every stats interval.
            write_progress_line = True
            if pct is not None:
                now = time.monotonic()
                write_progress_line = (
                    pct != last_journal_percent or
                    now - last_progress_log_time >= progress_log_heartbeat_seconds
                )
                if write_progress_line:
                    last_journal_percent = pct
                    last_progress_log_time = now

            dbg(line.rstrip('\n'))

            if pct is None or write_progress_line:
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

            if m:
                if pct != last_percent:
                    last_percent = pct
                    if pct >= 100:
                        notifier.notify("STATUS=Finalizing transfer...")
                    else:
                        notifier.notify(f"STATUS=Transferring... {pct:.1f}% complete")

            if stall_timeout_seconds > 0:
                stalled_for = time.monotonic() - last_meaningful_progress_time
                if stalled_for >= stall_timeout_seconds:
                    stalled_reason = f"Transfer stalled for {int(stalled_for)}s with no progress"
                    abort_process(
                        process,
                        stalled_reason
                    )
                    break

        if stalled_reason is None:
            process.wait()
    finally:
        if log_fh:
            try:
                log_fh.close()
            except Exception:
                pass

        if stalled_reason is not None:
            notifier.notify("STATUS=Transfer stalled")
        elif process.returncode == 0:
            notifier.notify("STATUS=Finishing up…")
        else:
            notifier.notify("STATUS=Transfer failed")

    if stalled_reason is not None:
        print(f"Error: {stalled_reason}")
        sys.exit(124)

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
        execute_command(
            command,
            src,
            dest,
            options.get('log_file_path') or None,
            options.get('stall_timeout_seconds', DEFAULT_STALL_TIMEOUT_SECONDS),
            options.get('progress_log_heartbeat_seconds', DEFAULT_PROGRESS_LOG_HEARTBEAT_SECONDS),
        )
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
        'stats_interval': stats_interval_from_value(
            os.environ.get('cloudSyncConfig_rcloneOptions_stats_interval'),
            DEFAULT_STATS_INTERVAL,
        ),
        'stall_timeout_seconds': int_from_value(
            os.environ.get('cloudSyncConfig_rcloneOptions_stall_timeout_seconds'),
            DEFAULT_STALL_TIMEOUT_SECONDS,
        ),
        'progress_log_heartbeat_seconds': DEFAULT_PROGRESS_LOG_HEARTBEAT_SECONDS,
    }

def str_to_bool(value):
    return str(value).lower() in ('true', '1', 't', 'yes', 'y')

def main():
    """
    Main execution entry point.
    """
    try:
        dbg("=== cloudsync task start ===")
        options = parse_arguments()
        is_dry_run = options.get('dry_run_flag', False)

        mode_label = "Dry-run" if is_dry_run else "Transfer"
        dbg(f"mode={mode_label} remote={options.get('rclone_remote')} direction={options.get('direction')}")

        notifier.notify(f"STATUS=Starting {mode_label}…")
        notifier.notify("READY=1")
        notifier.notify(f"STATUS=Running {mode_label}…")
        print(f"Starting rclone script ({mode_label.lower()})...")

        execute_rclone(options)

        notifier.notify(f"STATUS={mode_label} completed successfully")
        # Give systemd time to process the final STATUS before we exit,
        # otherwise it may retain the stale progress percentage in StatusText.
        import time as _time
        _time.sleep(0.1)
        dbg("=== cloudsync task completed ===")

        # Persist last-run timestamp for UI display across disable/enable cycles
        try:
            import time as _time
            _task_name = os.environ.get("taskName", "").strip()
            if _task_name:
                _lr = f"/etc/systemd/system/houston_scheduler_CloudSyncTask_{_task_name}.lastrun"
                with open(_lr, "w") as f:
                    f.write(str(int(_time.time())))
        except Exception:
            pass
    except SystemExit:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        dbg(f"FATAL: {tb}")
        print(f"FATAL: {e}", file=sys.stderr)
        print(tb, file=sys.stderr)
        notifier.notify(f"STATUS=Cloud sync task failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    notifier.notify("STATUS=Starting task…")
    main()
