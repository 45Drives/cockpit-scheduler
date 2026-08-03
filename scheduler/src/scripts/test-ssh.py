import subprocess
import argparse

def test_passwordless_ssh(target):
    try:
        # Attempt to run a command on the remote host without providing a password
        # Add connection timeout and strict host key checking options
        test_cmd = [
            'ssh',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'BatchMode=yes',
            target,
            'echo Success'
        ]

        process_test = subprocess.Popen(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  
        )

        # Add a timeout to communicate() call (overall command timeout)
        try:
            stdout, stderr = process_test.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process_test.kill()
            print("SSH connection timed out")
            return False

        if process_test.returncode != 0:
            # raise Exception(f"Error: {stderr.decode('utf-8')}")
            return False
        else:
            print(stdout)
            return True

    
    except subprocess.CalledProcessError as e:
        # If there is an error, notify the user and return False
        print(f"Error: {e.stderr}")
        print("Passwordless SSH connection failed.")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test passwordless SSH connection')
  
    parser.add_argument('sshTarget', type=str, help='ssh target')
    
    args = parser.parse_args()

    ssh_target = args.sshTarget
    
    result = test_passwordless_ssh(ssh_target)
    print(result)

if __name__ == "__main__":
    main()