import subprocess
import json
import argparse

def get_snapshots_info(recvName, recvHost, recvPort, recvHostUser):
    if recvPort == '22':
        ssh_cmd = ['ssh', f'{recvHostUser}@{recvHost}', f'zfs list -H -o name,guid,creation -t snapshot {recvName}']
    else:
        ssh_cmd = ['ssh', '-p', f'{recvPort}', f'{recvHostUser}@{recvHost}', f'zfs list -H -o name,guid,creation -t snapshot {recvName}']

    process = subprocess.Popen(
        ssh_cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        universal_newlines=True, 
    )

    stdout, stderr = process.communicate()

    if process.returncode != 0:
        # raise Exception(f"Error:{stderr}")
        return []

    # Parse the output and structure the data
    snapshots_info = []
    for line in stdout.splitlines():
        name, guid, creation_str = line.split('\t')
        snapshot_data = {'name': name, 'guid': guid, 'creation': creation_str}
        snapshots_info.append(snapshot_data)

    # Sort the array by 'creation' timestamp in descending order
    snapshots_info.sort(key=lambda x: x['creation'], reverse=True)

    return snapshots_info

def main():
    parser = argparse.ArgumentParser(description='Send ZFS Dataset')
   
    parser.add_argument('recvName', type=str, help='receiving dataset name')
    parser.add_argument('recvHost', type=str, help='receiving dataset host')
    parser.add_argument('recvPort', type=str, default='22', help='receiving dataset port')
    parser.add_argument('recvHostUser', type=str, help='receiving dataset host user')

    args = parser.parse_args()

    recvName = args.recvName
    recvHost = args.recvHost
    recvPort = args.recvPort
    recvHostUser = args.recvHostUser

    snapshots_info = get_snapshots_info(recvName, recvHost, recvPort, recvHostUser)

    # Print the structured data
    print(json.dumps(snapshots_info, indent=2))

    return snapshots_info

if __name__ == '__main__':
    main()
