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
        ssh_cmd.append(user + '@' + host)
        ssh_cmd.extend(['zpool', 'list', '-H', '-o', 'name'])
        
        # Using check_output for compatibility with earlier Python versions
        result = subprocess.check_output(ssh_cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        pools = result.strip().split('\n')
        return {"success": True, "data": pools, "error": None}
    except subprocess.CalledProcessError as e:
        print(f"Error {e}")
        return {"success": False, "data": [], "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description='Get pools from Local or Remote system')
    parser.add_argument('-H', '--host', type=str, help='hostname of remote system')
    parser.add_argument('-p', '--port', type=str, default='22', help='port to connect via ssh (22 by default)')
    parser.add_argument('-u', '--user', type=str, default='root', help='user of remote system (root by default)')

    args = parser.parse_args()
    
    if args.host:
        result = get_remote_zfs_pools(args.host, args.port, args.user)
    else:
        result = get_local_zfs_pools()
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
