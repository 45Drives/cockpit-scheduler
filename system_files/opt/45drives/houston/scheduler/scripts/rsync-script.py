import subprocess
import argparse
import sys

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
    
    if options['bandwidthLimit'] > 0:
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
        if options['targetPort'] and options['targetPort'] != 22:
            ssh_command = f"ssh -p {options['targetPort']}"
            command.append(f"-e '{ssh_command}'")
        else:
            command.append("-e 'ssh'")
    
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

# def execute_command(command, src, dest, isParallel=False, parallelThreads=0):
#     if isParallel and parallelThreads > 0:
#         print(f'Transferring using {parallelThreads} parallel threads from {src} to {dest}')
#         rsync_command = " ".join(command)
#         parallel_command = f'ls -1 {src} | xargs -I {{}} -P {parallelThreads} -n 1 {rsync_command} {{}} {dest}'
        
#         print(f'Executing command: {parallel_command}')
        
#         process = subprocess.Popen(
#             parallel_command, 
#             shell=True, 
#             universal_newlines=True
#         )
#     else:
#         command.extend([src, dest])
        
#         print(f'Executing command: {" ".join(command)}')
        
#         process = subprocess.Popen(
#             command, 
#             universal_newlines=True
#         )
    
#     stdout, stderr = process.communicate()
#     if process.returncode != 0:
#         print(f"Error: {stderr}")
#         sys.exit(1)
#     else:
#         print(stdout)

def execute_command(command, src, dest, isParallel=False, parallelThreads=0):
    if isParallel and parallelThreads > 0:
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

def parse_arguments():
    parser = argparse.ArgumentParser(description='Rsync Script')
    parser.add_argument('--source', type=str, required=True, help='source/local directory')
    parser.add_argument('--direction', type=str, required=True, choices=['push', 'pull'], help='direction of transfer (push/pull)')
    parser.add_argument('--host', type=str, nargs='?', default='', help='hostname or ip of ssh connection')
    parser.add_argument('--port', type=int, default=22, help='port to connect via ssh (22)')
    parser.add_argument('--user', type=str, nargs='?', default='root', help='user of ssh connection (root)')
    parser.add_argument('--target', type=str, required=True, help='target/remote directory')
    parser.add_argument('--archive', action='store_true', help='archive mode')
    parser.add_argument('--recursive', action='store_true', help='recurse into directories')
    parser.add_argument('--compressed', action='store_true', help='compress file data during transfer')
    parser.add_argument('--delete', action='store_true', help='delete extraneous files from destination dirs')
    parser.add_argument('--quiet', action='store_true', help='suppress non-error message')
    parser.add_argument('--times', action='store_true', help='preserve modification times')
    parser.add_argument('--hardLinks', action='store_true', help='preserve hard links')
    parser.add_argument('--permissions', action='store_true', help='preserve permissions')
    parser.add_argument('--xattr', action='store_true', help='preserve extended attributes')
    parser.add_argument('--bandwidth', type=int, nargs='?', default=0, help='limit I/O bandwidth; KBytes per second')
    parser.add_argument('--include', type=str, nargs='?', default='', help='include pattern')
    parser.add_argument('--exclude', type=str, nargs='?', default='', help='exclude pattern')
    parser.add_argument('--parallel', action='store_true', help='parallel transfer')
    parser.add_argument('--threads', type=int, nargs='?', default=0, help='number of parallel threads')
    parser.add_argument('--customArgs', type=str, nargs=argparse.REMAINDER, help='additional custom arguments')

    args = parser.parse_args()
    
    return {
        'localPath': args.source,
        'direction': args.direction,
        'targetHost': args.host,
        'targetPort': args.port,
        'targetUser': args.user,
        'targetPath': args.target,
        'isArchive': args.archive,
        'isRecursive': args.recursive,
        'isCompressed': args.compressed,
        'isDelete': args.delete,
        'isQuiet': args.quiet,
        'preserveTimes': args.times,
        'preserveHardLinks': args.hardLinks,
        'preservePerms': args.permissions,
        'preserveXattrs': args.xattr,
        'bandwidthLimit': args.bandwidth,
        'includePattern': args.include,
        'excludePattern': args.exclude,
        'isParallel': args.parallel,
        'parallelThreads': args.threads,
        'customArgs': args.customArgs,
    }

def main():
    options = parse_arguments()
    execute_rsync(options)

if __name__ == '__main__':
    main()
