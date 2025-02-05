import subprocess
import json
import argparse

def get_local_zfs_pools():
    try:
        result = subprocess.run(['zpool', 'list', '-H', '-o', 'name'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
        pools = result.stdout.strip().split('\n')
        return {"success": True, "data": pools, "error": None}
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return {"success": False, "data": [], "error": str(e)}

def get_remote_zfs_pools(host, port=22, user='root'):
    try:
        ssh_cmd = ['ssh']
        if port != '22':
            ssh_cmd.extend(['-p', port])
        ssh_cmd.append(f"{user}@{host}")
        ssh_cmd.extend(['zpool', 'list', '-H', '-o', 'name'])
        
        result = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        pools = result.strip().split('\n')
        return {"success": True, "data": pools, "error": None}
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return {"success": False, "data": [], "error": str(e)}

def get_remote_zfs_pools_netcat(host, port=22):
    try:
        command = "zpool list -H -o name\n"  # Note: The newline character ensures the command is sent properly

        # Netcat command
        nc_cmd = ['nc', host, str(port)]
        
        process = subprocess.Popen(nc_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        stdout, stderr = process.communicate(command)

        # Check for errors
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, ' '.join(nc_cmd), output=stdout, stderr=stderr)

        # Process the result
        pools = stdout.strip().split('\n')
        return {"success": True, "data": pools, "error": None}
        
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return {"success": False, "data": [], "error": str(e)}

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
        
        result = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        datasets = result.strip().split('\n')
        return {"success": True, "data": datasets, "error": None}
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return {"success": False, "data": [], "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description='Get Pools or Datasets from Local or Remote system')
    parser.add_argument('-t', '--type', type=str, choices=['pools', 'datasets'], required=True, help='Specify whether to get pools or datasets')
    parser.add_argument('-H', '--host', type=str, help='hostname of remote system')
    parser.add_argument('-p', '--port', type=str, default='22', help='port to connect via ssh (22 by default)')
    parser.add_argument('-u', '--user', type=str, default='root', help='user of remote system (root by default)')
    parser.add_argument('-P', '--pool', type=str, help='zfs pool to get datasets from (required if type is datasets)')

    args = parser.parse_args()
    
    if args.type == 'pools':
        if args.host:
            result = get_remote_zfs_pools(args.host, args.port, args.user)
        else:
            result = get_local_zfs_pools()
    elif args.type == 'datasets':
        if not args.pool:
            parser.error("the following arguments are required: -P/--pool")
        if args.host:
            result = get_remote_zfs_datasets(args.pool, args.host, args.port, args.user)
        else:
            result = get_local_zfs_datasets(args.pool)
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
