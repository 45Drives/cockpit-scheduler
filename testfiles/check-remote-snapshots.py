import subprocess
import argparse

def check_if_recv_dataset_has_snapshots(recvName, recvHost, recvPort, recvHostUser):
    # Construct the SSH command
    if recvPort == '22':
        ssh_cmd = ['ssh', f'{recvHostUser}@{recvHost}', f'zfs list -H -o name -t snapshot {recvName}']
    else:
        ssh_cmd = ['ssh', '-p', f'{recvPort}', f'{recvHostUser}@{recvHost}', f'zfs list -H -o name -t snapshot {recvName}']

    # Run the SSH command
    process_check_snapshots = subprocess.Popen(
        ssh_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # Ensures text mode for stdout and stderr
    )

    # Wait for the command to complete and capture the output
    stdout, stderr = process_check_snapshots.communicate()

    # Log stdout and stderr for debugging
    print("stdout:", stdout)
    print("stderr:", stderr)

    # Check the return code
    if process_check_snapshots.returncode != 0:
        # raise Exception(f"Error:{stderr}")
        return False
    else:
        # Check if the output contains snapshots
        return bool(stdout.strip())

def main() :
    parser = argparse.ArgumentParser(description='Check ZFS Datasets/Snapshots')
    parser.add_argument('recvName', type=str, help='receiving dataset name')
    parser.add_argument('recvHost', type=str, help='receiving dataset host')
    parser.add_argument('recvPort', type=str, default='22', help='receiving dataset port')
    parser.add_argument('recvHostUser', type=str, help='receiving dataset host user')

    args = parser.parse_args()

    recvName = args.recvName
    recvHost = args.recvHost
    recvPort = args.recvPort
    recvHostUser = args.recvHostUser

    if recvPort == '22':
        print(f"ssh {recvHostUser}@{recvHost} 'zfs list -H -o name -t snapshot {recvName}'")
    else:
        print(f"ssh -p {recvPort} {recvHostUser}@{recvHost} 'zfs list -H -o name -t snapshot {recvName}'")

    exists = check_if_recv_dataset_has_snapshots(recvName, recvHost, recvPort, recvHostUser)

    print(str(exists))

if __name__ == '__main__':
    main()