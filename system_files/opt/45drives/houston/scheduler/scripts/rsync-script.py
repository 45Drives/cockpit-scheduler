import subprocess
import sys
import os

def build_rsync_command(options):
    command = ['rsync', '-h', '-i', '-v', '--progress']
    
    option_flags = {
        'isArchive': '-a',
        'isRecursive': '-r',
        'isCompressed': '-z',
        'isDelete': '--delete',
        'isQuiet': '-q',
        'preserveTimes': '-t',
        'preserveHardLinks': '-H',
        'preservePerms': '-p',
        'preserveXattrs': '-X'
    }
    
    for key, flag in option_flags.items():
        if options.get(key):
            command.append(flag)
    
    if options['customArgs']:
        cleaned_custom_args = [arg.strip().replace(',', '') for arg in options['customArgs']]
        for arg in cleaned_custom_args:
            command.append(arg)
    
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
    # Check if transferMethod is specified
    if 'transferMethod' in options:
        if options['transferMethod'] == 'ssh':
            remote_command = "ssh"
            if 'targetPort' in options and int(options['targetPort']) != 22:
                remote_command += f" -p {options['targetPort']}"
            command.append(f"-e {remote_command}")
            print(f'Using SSH command: ', command)

        elif options['transferMethod'] == 'netcat' and 'targetHost' in options:
            remote_command = f"nc {options['targetHost']} {options['targetPort']}"
            command.append(f"-e '{remote_command}'")
            print(f'Using Netcat command: ', command)
        else:
            print("Error: targetHost must be provided for Netcat.")
    else:
        # If transferMethod is missing, proceed with default logic
        if options['targetHost'] and options['targetUser']:
            if 'targetPort' in options and int(options['targetPort']) != 22:
                remote_command = f"ssh -p {options['targetPort']}"
                command.append(f"-e {remote_command}")
            else:
                command.append("-e 'ssh'")
        elif options['targetHost']:
            remote_command = f"nc {options['targetHost']} {options['targetPort']}"
            command.append(f"-e '{remote_command}'")  # Use netcat for remote command
            print(f'Using Netcat command: ', command)
    
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

def execute_command(command, src, dest, isParallel=False, parallelThreads=0):
    if isParallel and int(parallelThreads) > 0:
        print(f'Transferring using {parallelThreads} parallel threads from {src} to {dest}')
        rsync_command = " ".join(command)
        parallel_command = f'ls -1 {src} | xargs -I {{}} -P {parallelThreads} -n 1 {rsync_command} {src} {dest}'

        print(f'Executing command: {parallel_command}')

        process = subprocess.Popen(
            parallel_command,
            shell=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
    else:
        command.extend([src, dest])

        print(f'Executing command: {" ".join(command)}')

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


def execute_rsync(options):
    try:
        command = build_rsync_command(options)
        src, dest = construct_paths(options['localPath'], options['direction'], options['targetPath'], options['targetHost'], options['targetUser'])
        if options['isParallel']:
            execute_command(command, src, dest, isParallel=True, parallelThreads=options['parallelThreads'])
        else:
            execute_command(command, src, dest)
    except Exception as e:
        print(f"send error: {e}")
        sys.exit(1)

def str_to_bool(value):
    return str(value).lower() in ('true', '1', 't', 'yes', 'y')

def parse_arguments():
    return {
        'localPath': os.environ.get('rsyncConfig_local_path', ''),
        'direction': os.environ.get('rsyncConfig_direction', 'push'),
        'transferMethod': os.environ.get('rsyncConfig_target_info_transferMethod', ''),
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
    }
    
def main():
    options = parse_arguments()
    execute_rsync(options)

if __name__ == '__main__':
    main()