import subprocess
import argparse
import re
import json
import os
import datetime
     
def create_snapshot(snapshot, is_recursive):
    command = [ 'zfs', 'snapshot' ]
    if is_recursive:
         command.append('-r')

    command.append(snapshot)
    subprocess.run(command)

def destroy_snapshot(snapshot):
    command = [ 'zfs', 'destroy' ]

    command.append(snapshot)
    subprocess.run(command)

def send_snapshot(sendName, recvName, sendName2="", compressed=False, raw=False, recvHost="", recvPort=22, recvHostUser="", mBufferSize=1, mBufferUnit="G"):
    try:
        # Initial local send command
        send_cmd = ['zfs', 'send', '-v']

        if compressed:
            send_cmd.append('-Lce')

        if raw:
            send_cmd.append('-w')

        if sendName2 != "":
            send_cmd.extend(['-i', sendName2])

        send_cmd.append(sendName)

        print(f"SEND_CMD: {send_cmd}")

        process_send = subprocess.Popen(
            send_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        # If sending locally
        if recvHost == "":
            recv_cmd = ['zfs', 'recv', '-v']

            recv_cmd.append(recvName)

            print(f"RECV_CMD: {recv_cmd}")

            process_recv = subprocess.Popen(
                recv_cmd,
                stdin=process_send.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )     
           
            stdout, stderr = process_recv.communicate()

            if process_recv.returncode != 0:
                raise Exception(f"Error:{stderr}")
            else:
                print(stdout)

        # If sending remotely via SSH
        if recvHost != "":

            m_buff_cmd = ['mbuffer', '-s', '256k']
            m_buff_cmd.extend(['-m', mBufferSize + mBufferUnit])

            process_m_buff = subprocess.Popen(
                m_buff_cmd,
                stdin=process_send.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            ssh_cmd = ['ssh']

            if recvPort != '22':
                ssh_cmd.extend(['-p', recvPort])

            ssh_cmd.append(recvHostUser + '@' + recvHost)

            ssh_cmd.extend(['zfs', 'recv'])

            ssh_cmd.append('-v')

            ssh_cmd.append(recvName)

            print(f"SSH_CMD: {ssh_cmd}")

            process_ssh_recv = subprocess.Popen(
                ssh_cmd,
                stdin=process_m_buff.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            stdout, stderr = process_ssh_recv.communicate()

            if process_ssh_recv.returncode != 0:
                raise Exception(f"Error: {stderr}")
            else:
                print(stdout)
        

    except Exception as e:
        print(f"An error occurred: {e}")


def main():
	parser = argparse.ArgumentParser(description='Create Snapshot')
	parser.add_argument('filesystem', type=str, help='filesystem to snapshot')
	parser.add_argument('--r', action='store_true',help='snap all child datasets')
	parser.add_argument('--custom-name', type=str, nargs='?', default=None, help='custom name for snapshot')

    # python3 create-snapshot.py <filesystem> --r
	args = parser.parse_args()
    
	timestamp = datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')

	snapshot_string = (f'{args.filesystem}@{timestamp}')

	create_snapshot(snapshot_string, args.r)
    #  send_snapshot(sendName, recvName, sendName2="", compressed=False, raw=False, recvHost="", recvPort=22, recvHostUser="", mBufferSize=1, mBufferUnit="G"):

if __name__ == "__main__":
	main()