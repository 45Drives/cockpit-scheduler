
# import subprocess
# import argparse
# import time


# def test_netcat(user, target, port):
#     try:
#         # Start the Netcat listener remotely using SSH with nohup
#         listen_cmd = f'bash -c "nohup nc -l -p {port} >/dev/null 2>&1 & </dev/null disown"'
#         ssh_cmd_listener = ['ssh', f'{user}@{target}', listen_cmd]

#         # Start the listener process
#         print(f"Starting SSH listener command: {' '.join(ssh_cmd_listener)}")
#         ssh_process_listener = subprocess.Popen(
#             ssh_cmd_listener,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             universal_newlines=True,
#         )
#         # Wait a moment to ensure the listener is running
#         time.sleep(5)

#         # Test if the port is open by attempting a connection
#         test_cmd = ['nc', '-zv', target, str(port)]
#         process_test = subprocess.Popen(
#             test_cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             universal_newlines=True,
#         )
#         stdout, stderr = process_test.communicate()
        
        

#         # Stop the SSH process
#         ssh_process_listener.terminate()
#         ssh_process_listener.wait()

#         if process_test.returncode != 0:
#             print(stderr)
#             return False
#         else:
#             print(stdout)
#             return True

#     except Exception as e:
#         print(f"Unexpected error: {str(e)}")
#         return False


# def main():
#     parser = argparse.ArgumentParser(description='Test netcat connectivity')
#     parser.add_argument('user', type=str, help='SSH user')
#     parser.add_argument('ncTarget', type=str, help='Target hostname or IP address')
#     parser.add_argument('port', type=int, help='Port to connect to')

#     args = parser.parse_args()

#     result = test_netcat(args.user, args.ncTarget, args.port)
#     print(f"Netcat test result: {result}")

# if __name__ == "__main__":
#     main()

import subprocess
import argparse
import time

def test_netcat(user, target, port):
    try:
        # Start Netcat listener remotely
        listen_cmd = f'bash -c "nohup nc -lk {port} >/dev/null 2>&1 & disown"'
        ssh_cmd_listener = ['ssh', f'{user}@{target}', listen_cmd]

        print(f"Starting SSH listener command: {' '.join(ssh_cmd_listener)}")
        subprocess.run(ssh_cmd_listener, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
        kill_cmd = ['ssh', f'{user}@{target}', f'fuser -k {port}/tcp']
        subprocess.run(kill_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
