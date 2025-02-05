import subprocess
import argparse
import time


def test_netcat(user,target, port):
    try:
        listen_cmd = f"nc -l {port}"
        ssh_cmd_listener = ['ssh', f'{user}@{target}', listen_cmd]

        # Start the listener process
        print(f"Starting SSH listener command: {' '.join(ssh_cmd_listener)}")
        ssh_process_listener = subprocess.Popen(
        ssh_cmd_listener,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        )
        # Wait a moment to ensure the listener is running
        time.sleep(5)

        # Test if the port is open by attempting a connection
        test_cmd = ['nc', '-zv', target, port]
        process_test = subprocess.Popen(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process_test.communicate()

        if process_test.returncode != 0:
            print(stderr)
            ssh_process_listener.terminate()  # Terminate the listener
            ssh_process_listener.wait()  # Wait for the process to exit
            return False
        else:
            print(stdout)
            ssh_process_listener.terminate()  # Gracefully terminate
            ssh_process_listener.wait()  # Wait for the process to exit
            return True

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False
def main():
    parser = argparse.ArgumentParser(description='Test netcat connectivity')
    parser.add_argument('user', type=str, help='Target hostname or IP address')
    parser.add_argument('ncTarget', type=str, help='Target hostname or IP address')
    parser.add_argument('port', type=str, help='Port to connect to')

    args = parser.parse_args()

    result = test_netcat(args.user,args.ncTarget, args.port)
    print(f"Netcat test result: {result}")

if __name__ == "__main__":
    main()
