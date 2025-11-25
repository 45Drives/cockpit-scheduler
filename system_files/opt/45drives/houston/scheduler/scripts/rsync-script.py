import subprocess
import sys
import os
import re
import shlex
from notify import get_notifier

notifier = get_notifier()
PROGRESS_RE = re.compile(r'(\d+)%')
SCHEDULER_KEY_PATH = "/etc/45drives/houston/scheduler/ssh/rsync_key"

def ensure_scheduler_key(path: str = SCHEDULER_KEY_PATH) -> str:
    """
    Ensure a dedicated SSH key exists for the scheduler.
    Returns the path (even if it already existed).
    Safe to call multiple times.
    """
    key_dir = os.path.dirname(path)
    if not key_dir:
        return path

    try:
        os.makedirs(key_dir, exist_ok=True)
        os.chmod(key_dir, 0o700)
    except Exception as e:
        print(f"WARNING: Failed to prepare scheduler SSH dir {key_dir}: {e}")

    if not os.path.exists(path):
        # Generate a passwordless key via ssh-keygen if available
        try:
            print(f"Creating scheduler SSH key at {path}...")
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", path, "-N", ""],
                check=True,
            )
        except FileNotFoundError:
            print("WARNING: ssh-keygen not found; cannot create scheduler SSH key automatically.")
        except subprocess.CalledProcessError as e:
            print(f"WARNING: ssh-keygen failed when creating scheduler key: {e}")
    else:
        # Ensure private key perms are sane
        try:
            os.chmod(path, 0o600)
        except Exception as e:
            print(f"WARNING: Failed to chmod scheduler key {path}: {e}")

    return path

def build_rsync_command(options):
    command = ['rsync', '-h', '-i', '-v', '--progress', '--info=progress2']

    option_flags = {
        'isArchive': '-a',
        'isRecursive': '-r',
        'isCompressed': '-z',
        'isDelete': '--delete',
        'isQuiet': '-q',
        'preserveTimes': '-t',
        'preserveHardLinks': '-H',
        'preservePerms': '-p',
        'preserveXattrs': '-X',
    }

    for key, flag in option_flags.items():
        if options.get(key):
            command.append(flag)

    # customArgs can be either a comma-separated string or a list
    custom = options.get('customArgs') or ''
    if isinstance(custom, str):
        if custom.strip():
            for chunk in custom.split(','):
                chunk = chunk.strip()
                if not chunk:
                    continue
                # allow quoting, multiple flags per chunk
                command.extend(shlex.split(chunk))
    elif isinstance(custom, (list, tuple)):
        for arg in custom:
            if arg:
                command.append(str(arg))

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

    # if options['targetHost']:
    #     if options['targetPort'] and int(options['targetPort']) != 22:
    #         remote_command = f"ssh -p {options['targetPort']}"
    #         command.append(f"-e {remote_command}")
    #     else:
    #         command.append("-e ssh")

    if options['targetHost']:
        ssh_parts = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
        ]
        
        identity = options.get('identityFile') or ''
        if identity:
            ssh_parts.extend(["-i", identity])
            
        if options['targetPort'] and int(options['targetPort']) != 22:
            ssh_parts.extend(["-p", str(options['targetPort'])])

        remote_command = " ".join(ssh_parts)
        command.extend(["-e", remote_command])
    
    # Auto-create remote path for push
    if options['targetHost'] and options['direction'] == 'push':
        remote_parent = os.path.dirname(options['targetPath'].rstrip('/'))
        rsync_path_cmd = f"mkdir -p '{remote_parent}' && rsync"
        command.append(f"--rsync-path={rsync_path_cmd}")

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

def check_selinux_rsync_exec_denial() -> bool:
    """
    Best-effort check: did SELinux recently deny rsync executing ssh?
    Returns True if we see an AVC matching rsync -> ssh_exec_t execute denial.
    """
    try:
        out = subprocess.check_output(["getenforce"], text=True).strip()
        if out not in ("Enforcing", "Permissive"):
            return False

        cmd = ["ausearch", "-m", "avc", "-c", "rsync", "-ts", "recent"]
        avc = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return "ssh_exec_t" in avc and "{ execute }" in avc
    except Exception:
        return False

def ensure_rsync_selinux_boolean():
    """
    Best-effort: enable rsync_client boolean on SELinux systems.
    - No-op on systems without SELinux or without setsebool.
    - Safe to call multiple times.
    """
    try:
        mode = subprocess.check_output(["getenforce"], text=True).strip()
    except FileNotFoundError:
        # SELinux tools not installed (e.g. many Debian/Ubuntu systems)
        return
    except Exception:
        # Any other error → don't break the task, just skip
        return

    if mode == "Disabled":
        return

    try:
        # -P makes it persistent; repeated calls are harmless
        subprocess.run(
            ["setsebool", "-P", "rsync_client", "1"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        # setsebool not available
        return
    
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
        print(f'Transferring using {parallelThreads} parallel threads from {src} to {dest}')
        rsync_command = " ".join(command)
        parallel_command = f'ls -1 {src} | xargs -I {{}} -P {parallelThreads} -n 1 {rsync_command} {src} {dest}'

        print("Executing parallel rsync shell command:")
        print(f"  {parallel_command!r}")

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
        print("  " + shlex.join(command))

        process = subprocess.Popen(
            command,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )

    last_percent = None
    output_lines: list[str] = []
    
    try:
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line)
            
            # tee to optional log file
            if log_fh:
                try:
                    log_fh.write(line)
                except Exception as e:
                    print(f"WARNING: Failed to write to log file {log_file_path}: {e}")
                    log_fh = None

            # keep logs in journal
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
            
    error_buffer = "".join(output_lines)

    if process.returncode != 0:
        if process.returncode == 14 and "Failed to exec ssh: Permission denied (13)" in error_buffer:
            if check_selinux_rsync_exec_denial():
                print(
                    "ERROR: rsync failed because SELinux is denying ssh execution "
                    "from the rsync_t domain.\n"
                    "You can usually fix this by enabling the rsync_client boolean:\n"
                    "  setsebool -P rsync_client 1\n"
                    "or by creating an SELinux module based on the audit logs.\n"
                )
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
    identity_env = os.environ.get('rsyncConfig_target_info_identity_file', '')
    # If env not set but default key exists, use it
    if not identity_env and os.path.exists(SCHEDULER_KEY_PATH):
        identity_env = SCHEDULER_KEY_PATH
        
    return {
        'localPath': os.environ.get('rsyncConfig_local_path', ''),
        'direction': os.environ.get('rsyncConfig_direction', 'push'),
        'targetHost': os.environ.get('rsyncConfig_target_info_host', ''),
        'targetPort': int(os.environ.get('rsyncConfig_target_info_port', 22)),
        'targetUser': os.environ.get('rsyncConfig_target_info_user', 'root'),
        'targetPath': os.environ.get('rsyncConfig_target_info_path', ''),
        'identityFile': identity_env,
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
    ensure_rsync_selinux_boolean()
    notifier.notify("STATUS=Starting task…")
    notifier.notify("READY=1")
    notifier.notify("STATUS=Running task…")
    print("Starting rsync script...")
    ensure_scheduler_key()
    options = parse_arguments()
    execute_rsync(options)
    notifier.notify("STATUS=Finishing up…")
    print("Rsync task execution completed.")


if __name__ == '__main__':
    main()
