import subprocess
import argparse
import time

# Matches the replication task: it cannot answer a password prompt either.
SSH_OPTS = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=accept-new']

def test_netcat(user, target, port):
    try:
        # Start Netcat listener remotely
        listen_cmd = f'bash -c "nohup nc -lk {port} >/dev/null 2>&1 & disown"'
        ssh_cmd_listener = ['ssh', *SSH_OPTS, f'{user}@{target}', listen_cmd]

        print(f"Starting SSH listener command: {' '.join(ssh_cmd_listener)}")
        listener = subprocess.run(
            ssh_cmd_listener, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=20,
        )
        if listener.returncode != 0:
            print(f"SSH_FAILED: {listener.stderr.strip()}")
            return False

        # Allow listener to start
        time.sleep(3)

        # Test port connection
        test_cmd = ['nc', '-zv', target, str(port)]
        process_test = subprocess.run(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        # Kill the listener remotely after test
        kill_cmd = ['ssh', *SSH_OPTS, f'{user}@{target}', f'fuser -k {port}/tcp']
        subprocess.run(kill_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

        if process_test.returncode != 0:
            print(process_test.stderr.strip())
            return False
        else:
            print(process_test.stderr.strip())
            return True

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test netcat connectivity')
    parser.add_argument('user', type=str, help='SSH user')
    parser.add_argument('ncTarget', type=str, help='Target hostname or IP address')
    parser.add_argument('port', type=int, help='Port to connect to')

    args = parser.parse_args()

    result = test_netcat(args.user, args.ncTarget, args.port)
    print(f"Netcat test result: {result}")

if __name__ == "__main__":
    main()
