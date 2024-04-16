import subprocess
import json
import argparse

def get_local_zfs_datasets(pool):
    try:
        result = subprocess.run(['zfs', 'list', '-H', '-o', 'name', '-r', pool], capture_output=True, text=True, check=True)
        datasets = result.stdout.strip().split('\n')
        return json.dumps(datasets)
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return json.dumps([])

def get_remote_zfs_datasets(user, host, port, pool):
    try:
        ssh_cmd = ['ssh']
        
        if port != '22':
            ssh_cmd.extend(['-p', port])
        ssh_cmd.append(f"{user}@{host}")
        ssh_cmd.extend(['zfs', 'list', '-H', '-o', 'name', '-r', pool])
        result = subprocess.check_output(ssh_cmd)
        datasets = result.decode('utf-8').strip().split('\n')
        return json.dumps(datasets)
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return json.dumps([])

def main():
    parser = argparse.ArgumentParser(description='Get Datasets from Local or Remote system')
    parser.add_argument('-r', '--remote', action='store_true', help='get datasets from a remote system with ssh')
    parser.add_argument('-H', '--host', type=str, help='hostname of remote system')
    parser.add_argument('-p', '--port', type=str, default='22', help='port to connect via ssh (22 by default)')
    parser.add_argument('-u', '--user', type=str, default='root', help='user of remote system (root by default)')
    parser.add_argument('-P', '--pool', type=str, required=True, help='zfs pool to get datasets from')

    args = parser.parse_args()
    
    if args.remote:
        if args.host:
            json_datasets = get_remote_zfs_datasets(args.user, args.host, args.port, args.pool)
        else:
            print("Remote mode requires a host parameter.")
            return
    else:
        json_datasets = get_local_zfs_datasets(args.pool)
    
    print(json_datasets)

if __name__ == "__main__":
    main()
