import subprocess
import argparse
import sys

def execute_rsync(localPath, direction, targetPath, targetHost="", targetPort=22, targetUser='root', isArchive=False, isRecursive=False, isCompressed=False, isDelete=False, isQuiet=False, preserveTimes=False, preserveHardLinks=False, preservePerms=False, preserveXattrs=False, bandwidthLimit=0, includePattern='', excludePattern='', customArgs='', isParallel=False, parallelThreads=0):
    try:
    
        command = ['rsync']
        command.append('-h')
        
        # Rsync options
        if isArchive:
            command.append('-a')
        if isRecursive:
            command.append('-r')
        if isCompressed:
            command.append('-z')
        if isDelete:
            command.append('--delete')
        if isQuiet:
            command.append('-q')
        if preserveTimes:
            command.append('-t')
        if preserveHardLinks:
            command.append('-H')
        if preservePerms:
            command.append('-p')
        if preserveXattrs:
            command.append('-X')
        if bandwidthLimit > 0:
            command.append(f'--bwlimit={bandwidthLimit}')
        if includePattern:
            command.append(f'--include={includePattern}')
        if excludePattern:
            command.append(f'--exclude={excludePattern}')
        if customArgs:
            command.extend(customArgs.split())
            
        # Rsync direction
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
        
        if isParallel and not targetHost:
            print(f'Transferring using {parallelThreads} parallel threads ({direction}) from {src} to {dest}')
            parallel_command = f'ls -1 {src} | xargs -I {{}} -P {parallelThreads} -n 1 {" ".join(command)} {{}} {dest}'
            subprocess.run(parallel_command, shell=True)
        else:
            print(f'Rsync transferring ({direction}) from {src} to {dest}')
            command.extend([src, dest])
            subprocess.run(command)
            
            
    except Exception as e:
        print(f"send error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Rsync Script')
    parser.add_argument('--source', type=str, help='source/local directory')
    parser.add_argument('--direction', type=str, help='direction of transfer (push/pull)')
    parser.add_argument('--host', type=str, nargs='?', default='', help='hostname or ip of ssh connection')
    parser.add_argument('--port', type=str, default='22', help='port to connect via ssh (22)')
    parser.add_argument('--user', type=str, nargs='?', default='root', help='user of ssh connection (root)')
    parser.add_argument('--target', type=str, help='target/remote directory')
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
    parser.add_argument('--include', type=str, nargs='?',default='', help='include pattern')
    parser.add_argument('--exclude', type=str, nargs='?',default='', help='exclude pattern')
    parser.add_argument('--customArgs', type=str, nargs='?', default='', help='additional custom arguments')
    parser.add_argument('--parallel', action='store_true', help='parallel transfer')
    parser.add_argument('--threads', type=int, nargs='?', default=0, help='number of parallel threads')

    args = parser.parse_args()
    
    localPath = args.source
    direction = args.direction
    targetHost = args.host
    targetPort = args.port
    targetUser = args.user
    targetPath = args.target
    isArchive = args.archive
    isRecursive = args.recursive
    isCompressed = args.compressed
    isDelete = args.delete
    isQuiet = args.quiet
    preserveTimes = args.times
    preserveHardLinks = args.hardLinks
    preservePerms = args.permissions
    preserveXattrs = args.xattr
    bandwidthLimit = args.bandwidth
    includePattern = args.include
    excludePattern = args.exclude
    customArgs = args.customArgs
    isParallel = args.parallel
    parallelThreads = args.threads
    
    execute_rsync(localPath, direction, targetPath, targetHost, targetPort, targetUser, isArchive, isRecursive, isCompressed, isDelete, isQuiet, preserveTimes, preserveHardLinks, preservePerms, preserveXattrs, bandwidthLimit, includePattern, excludePattern, customArgs, isParallel, parallelThreads)
    
    
if __name__ == '__main__':
    main()