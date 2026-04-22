import subprocess
import sys
import os
import re
import shlex
import traceback
import datetime as dt
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

DEBUG_LOG = os.environ.get("RSYNC_DEBUG_LOG", "/tmp/rsync_task_debug.log")
DEBUG_ENABLED = os.environ.get("RSYNC_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")

def dbg(msg: str):
    if not DEBUG_ENABLED:
        return
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{dt.datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass
PROGRESS_RE = re.compile(r'(\d+)%')

def shlex_join(argv):
    import shlex
    return " ".join(shlex.quote(str(a)) for a in argv)

def normalize_local_source_path(p):
    # If user/UI supplied a trailing slash but it's actually a file, strip it.
    if p and p.endswith('/'):
        probe = p.rstrip('/')
        try:
            if os.path.isfile(probe):
                return probe
        except OSError:
            pass
    return p

def normalize_dest_path_for_file_copy(dest_path):
    # Usually fine as-is; only sanitize accidental "file/" if it's a file on local filesystem.
    if dest_path and dest_path.endswith('/'):
        probe = dest_path.rstrip('/')
        try:
            if os.path.isfile(probe):
                return probe
        except OSError:
            pass
    return dest_path

def build_rsync_command(options):
    # Base rsync options: human-readable with progress
    command = ['rsync', '-h', '--progress', '--info=progress2', '--stats']

    custom = options.get('customArgs') or ''
    custom_parts = []

    if isinstance(custom, str):
        if custom.strip():
            for chunk in custom.split(','):
                chunk = chunk.strip()
                if not chunk:
                    continue
                custom_parts.extend(shlex.split(chunk))
    elif isinstance(custom, (list, tuple)):
        for arg in custom:
            if arg:
                custom_parts.append(str(arg))

    # ---- Detect if the user already controls verbosity ----
    def is_verbosity_flag(arg: str) -> bool:
        if arg in ('-q', '-v', '-vv', '-vvv', '--quiet', '--verbose'):
            return True
        if arg.startswith('--info='):
            # rsync's --info controls how chatty it is, including progress detail
            return True
        return False

    user_has_verbosity = any(is_verbosity_flag(a) for a in custom_parts)

    # ---- Decide quiet vs verbose default ----
    is_quiet = options.get('isQuiet')
    if is_quiet:
        # User explicitly chose quiet mode via the UI/env flag
        command.append('-q')
    elif not user_has_verbosity:
        # Default to verbose + itemize for detailed debug-level logging
        command.append('-v')
        command.append('-i')

    option_flags = {
        'isArchive': '-a',
        'isRecursive': '-r',
        'isCompressed': '-z',
        'isDelete': '--delete',
        'preserveTimes': '-t',
        'preserveHardLinks': '-H',
        'preservePerms': '-p',
        'preserveXattrs': '-X',
    }

    for key, flag in option_flags.items():
        if options.get(key):
            command.append(flag)

    if int(options['bandwidthLimit']) > 0:
        command.append(f'--bwlimit={options["bandwidthLimit"]}')

    if options['includePattern']:
        include_patterns = options['includePattern'].split(',')
        for pattern in include_patterns:
            command.append(f'--include={pattern.strip()}')

    if options['excludePattern']:
        exclude_patterns = options['excludePattern'].split(',')
        for pattern in exclude_patterns:
            command.append(f'--exclude={pattern.strip()}')

    if options['targetHost']:
        if options['targetPort'] and int(options['targetPort']) != 22:
            remote_command = f"ssh -p {options['targetPort']}"
            command.append(f"-e {remote_command}")
        else:
            command.append("-e ssh")

    if options['targetHost'] and options['direction'] == 'push':
        remote_parent = os.path.dirname(options['targetPath'].rstrip('/'))
        rsync_path_cmd = f"mkdir -p '{remote_parent}' && rsync"
        command.append(f"--rsync-path={rsync_path_cmd}")

    command.extend(custom_parts)

    return command


def construct_paths(localPath, direction, targetPath, targetHost, targetUser):
    if targetHost:
        if direction == 'push':
            src = localPath
            dest = f'{targetUser}@{targetHost}:{targetPath}'
        elif direction == 'pull':
            src = f'{targetUser}@{targetHost}:{targetPath}'
            dest = localPath
    else:
        if direction == 'push':
            src = localPath
            dest = targetPath
        elif direction == 'pull':
            src = targetPath
            dest = localPath
    return src, dest


def execute_command(command, src, dest, isParallel=False, parallelThreads=0, log_file_path=None):
    """
    Run rsync, stream its output, send progress updates to systemd
    and optionally tee all output into a user-specified log file.
    """
    notifier.notify("STATUS=Starting transfer…")

    log_fh = None
    if log_file_path:
        try:
            d = os.path.dirname(log_file_path)
            if d:
                os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        try:
            # line-buffered for immediate writes
            log_fh = open(log_file_path, 'a', buffering=1)
        except Exception as e:
            print(f"WARNING: Failed to open log file {log_file_path}: {e}")
            log_fh = None

    if isParallel and int(parallelThreads) > 0:
        # Parallel mode only supports local directory sources
        if ':' in src:
            print("Error: Parallel mode is not supported for remote sources.")
            sys.exit(2)
        if not os.path.isdir(src.rstrip('/')):
            print("Error: Parallel mode requires the source to be a directory.")
            sys.exit(2)
            
        print(f'Transferring using {parallelThreads} parallel threads from {src} to {dest}')
        rsync_command = " ".join(command)
        parallel_command = f'ls -1 {src} | xargs -I {{}} -P {parallelThreads} -n 1 {rsync_command} {src} {dest}'

        print(f'Executing command: {parallel_command}')

        process = subprocess.Popen(
            parallel_command,
            shell=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
    else:
        command.extend([src, dest])

        
        print("Executing rsync command:")
        print("  " + shlex_join(command))

        process = subprocess.Popen(
            command,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )

    # Regex to detect rsync itemized-changes lines (e.g. ">f+++++++++ path/to/file")
    ITEMIZE_RE = re.compile(r'^[<>ch.*][fdLDS][c.+?][s.+?][t.+?][p.+?][o.+?][g.+?][u.+?][a.+?][x.+?] ')

    last_percent = None

    try:
        assert process.stdout is not None
        for line in process.stdout:
            is_itemized = bool(ITEMIZE_RE.match(line))

            # Always write to debug log (detailed)
            dbg(line.rstrip('\n'))

            # User log file: skip noisy itemized lines
            if log_fh and not is_itemized:
                try:
                    log_fh.write(line)
                except Exception as e:
                    print(f"WARNING: Failed to write to log file {log_file_path}: {e}")
                    log_fh = None

            # Journal/stdout: skip noisy itemized lines
            if not is_itemized:
                sys.stdout.write(line)
                sys.stdout.flush()

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
        print(f"Error: rsync exited with code {process.returncode}")
        sys.exit(process.returncode)
    else:
        print("Rsync task execution completed.")


def execute_rsync(options):
    try:
        command = build_rsync_command(options)
        src, dest = construct_paths(
            options['localPath'],
            options['direction'],
            options['targetPath'],
            options['targetHost'],
            options['targetUser'],
        )
        log_path = options.get('logFilePath') or None

        if options['isParallel']:
            execute_command(
                command,
                src,
                dest,
                isParallel=True,
                parallelThreads=options['parallelThreads'],
                log_file_path=log_path,
            )
        else:
            execute_command(
                command,
                src,
                dest,
                isParallel=False,
                parallelThreads=0,
                log_file_path=log_path,
            )
    except Exception as e:
        print(f"send error: {e}")
        sys.exit(1)


def str_to_bool(value):
    return str(value).lower() in ('true', '1', 't', 'yes', 'y')


def parse_arguments():
    return {
        'localPath': os.environ.get('rsyncConfig_local_path', ''),
        'direction': os.environ.get('rsyncConfig_direction', 'push'),
        'targetHost': os.environ.get('rsyncConfig_target_info_host', ''),
        'targetPort': int(os.environ.get('rsyncConfig_target_info_port', 22)),
        'targetUser': os.environ.get('rsyncConfig_target_info_user', 'root'),
        'targetPath': os.environ.get('rsyncConfig_target_info_path', ''),
        'isArchive': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_archive_flag', 'True')),
        'isRecursive': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_recursive_flag', 'False')),
        'isCompressed': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_compressed_flag', 'False')),
        'isDelete': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_delete_flag', 'False')),
        'isQuiet': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_quiet_flag', 'False')),
        'preserveTimes': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_times_flag', 'False')),
        'preserveHardLinks': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_hardLinks_flag', 'False')),
        'preservePerms': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_permissions_flag', 'False')),
        'preserveXattrs': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_xattr_flag', 'False')),
        'bandwidthLimit': int(os.environ.get('rsyncConfig_rsyncOptions_bandwidth_limit_kbps', 0)),
        'includePattern': os.environ.get('rsyncConfig_rsyncOptions_include_pattern', ''),
        'excludePattern': os.environ.get('rsyncConfig_rsyncOptions_exclude_pattern', ''),
        'isParallel': str_to_bool(os.environ.get('rsyncConfig_rsyncOptions_parallel_flag', 'False')),
        'parallelThreads': int(os.environ.get('rsyncConfig_rsyncOptions_parallel_threads', 0)),
        'customArgs': os.environ.get('rsyncConfig_rsyncOptions_custom_args', ''),
        'logFilePath': os.environ.get('rsyncConfig_rsyncOptions_log_file_path', ''),
    }


def main():
    try:
        dbg("=== rsync task start ===")
        notifier.notify("STATUS=Starting task…")
        notifier.notify("READY=1")
        notifier.notify("STATUS=Running task…")
        print("Starting rsync script...")
        options = parse_arguments()
        dbg(f"direction={options['direction']} host={options['targetHost']} src={options['localPath']} dest={options['targetPath']}")
        options['localPath'] = normalize_local_source_path(options.get('localPath', ''))
        if not options.get('targetHost'):
            options['targetPath'] = normalize_dest_path_for_file_copy(options.get('targetPath', ''))
            
        execute_rsync(options)
        notifier.notify("STATUS=Finishing up…")
        dbg("=== rsync task completed ===")

        # Persist last-run timestamp for UI display across disable/enable cycles
        try:
            import time as _time
            _task_name = os.environ.get("taskName", "").strip()
            if _task_name:
                _lr = f"/etc/systemd/system/houston_scheduler_RsyncTask_{_task_name}.lastrun"
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
        notifier.notify(f"STATUS=Rsync task failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
