import subprocess
import json
import argparse

def get_local_zfs_datasets(pool):
    try:
        result = subprocess.run(['zfs', 'list', '-H', '-o', 'name', '-r', pool], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
        datasets = result.stdout.strip().split('\n')
        return {"success": True, "data": datasets, "error": None}
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return {"success": False, "data": [], "error": str(e)}

def get_remote_zfs_datasets(pool, host, port=22, user='root'):
    try:
        ssh_cmd = ['ssh']
        
        if port != '22':
            ssh_cmd.extend(['-p', port])
        ssh_cmd.append(f"{user}@{host}")
        ssh_cmd.extend(['zfs', 'list', '-H', '-o', 'name', '-r', pool])
        
        # Using check_output with stderr=subprocess.STDOUT to capture all output
        result = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        datasets = result.strip().split('\n')
        return {"success": True, "data": datasets, "error": None}
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return {"success": False, "data": [], "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description='Get Datasets from Local or Remote system')
    parser.add_argument('-P', '--pool', type=str, required=True, help='zfs pool to get datasets from')
    parser.add_argument('-H', '--host', type=str, help='hostname of remote system')
    parser.add_argument('-p', '--port', type=str, default='22', help='port to connect via ssh (22 by default)')
    parser.add_argument('-u', '--user', type=str, default='root', help='user of remote system (root by default)')

    args = parser.parse_args()
    
    if args.host:
        result = get_remote_zfs_datasets(args.pool, args.host, args.port, args.user)
    else:
        result = get_local_zfs_datasets(args.pool)
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
