import subprocess
import json
import argparse

def get_local_zfs_pools():
    try:
        result = subprocess.run(['zpool', 'list', '-H', '-o', 'name'], capture_output=True, text=True, check=True)
        pools = result.stdout.strip().split('\n')
        return json.dumps(pools)
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return json.dumps([])

def get_remote_zfs_pools(user, host, port):
    try:
        ssh_cmd = ['ssh']
        
        if port != '22':
            ssh_cmd.extend(['-p', port])
        ssh_cmd.append(f"{user}@{host}")
        ssh_cmd.extend(['zpool', 'list', '-H', '-o', 'name'])
        
        # Using check_output, the output is directly returned as bytes
        result = subprocess.check_output(ssh_cmd)
        # Decode result from bytes to string and split by new lines to form the dataset list
        pools = result.decode('utf-8').strip().split('\n')
        return json.dumps(pools)
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return json.dumps([])

def main():
    parser = argparse.ArgumentParser(description='Get pools from Local or Remote system')
    parser.add_argument('-r', '--remote', action='store_true', help='get pools from a remote system with ssh')
    parser.add_argument('-H', '--host', type=str, help='hostname of remote system')
    parser.add_argument('-p', '--port', type=str, default='22', help='port to connect via ssh (22 by default)')
    parser.add_argument('-u', '--user', type=str, default='root', help='user of remote system (root by default)')

    args = parser.parse_args()
    
    if args.remote:
        if args.host:
            json_pools = get_remote_zfs_pools(args.user, args.host, args.port)
        else:
            print("Remote mode requires a host parameter.")
            return
    else:
        json_pools = get_local_zfs_pools()
    
    print(json_pools)

if __name__ == "__main__":
    main()
