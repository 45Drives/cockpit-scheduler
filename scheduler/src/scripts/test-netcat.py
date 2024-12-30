import subprocess
import argparse

def test_netcat(target, port):
    try:
        # Construct the command with target and port
        test_cmd = ['nc', '-zv', target, port]

        process_test = subprocess.Popen(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = process_test.communicate()

        if process_test.returncode != 0:
            print(stderr.decode('utf-8'))
            return False
        else:
            print(stdout.decode('utf-8'))
            return True

    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr.decode('utf-8')}")
        print("Netcat connection test failed.")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test netcat connectivity')
    parser.add_argument('ncTarget', type=str, help='Target hostname or IP address')
    parser.add_argument('port', type=str, help='Port to connect to')

    args = parser.parse_args()

    result = test_netcat(args.ncTarget, args.port)
    print(f"Netcat test result: {result}")

if __name__ == "__main__":
    main()
