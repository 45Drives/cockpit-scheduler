import subprocess
import sys
import os

def build_rclone_command(options):
    print("Building rclone command with options:", options)
    
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
        'metadata_flag': '--metadata'
    }
    
    for key, flag in option_flags.items():
        if options.get(key):
            command.append(flag)
            
    if options['custom_args']:
        cleaned_custom_args = [arg.strip().replace(',', '') for arg in options['custom_args']]
        for arg in cleaned_custom_args:
            command.append(arg)
            
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
        
    print("Constructed rclone command:", " ".join(command))
    return command
    
def construct_paths(localPath, direction, targetPath):
    print(f"Constructing paths with localPath='{localPath}', direction='{direction}', targetPath='{targetPath}'")
    if direction == 'push':
        src = localPath
        dest = targetPath
    elif direction == 'pull':
        src = targetPath
        dest = localPath
        
    print(f"Constructed source path: {src}")
    print(f"Constructed destination path: {dest}")
    return src, dest


def execute_command(command, src, dest):
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
    try:
        print("Starting rclone execution with options:", options)
        command = build_rclone_command(options)
        src, dest = construct_paths(options['local_path'], options['direction'], options['target_path'])
        execute_command(command, src, dest)
    except Exception as e:
        print(f"Execution error: {e}")
        sys.exit(1)


def str_to_bool(value):
    return str(value).lower() in ('true', '1', 't', 'yes', 'y')

def parse_arguments():
    options = {
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
        'metadata_flag': str_to_bool(os.environ.get('cloudSyncConfig_rcloneOptions_metadata_flag', 'False')),
    }
    print("Parsed arguments:", options)
    return options


def main():
    print("Starting rclone script...")
    options = parse_arguments()
    execute_rclone(options)
    print("Rclone task execution completed.")
    
if __name__ == '__main__':
    main()