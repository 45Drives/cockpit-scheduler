"""Report the SSH ciphers this host's client supports and, optionally, the ciphers
a remote host offers.

The remote list is read out of the pre-authentication KEXINIT proposal that OpenSSH
prints under -vv, so it works even when key-based login is not configured yet.
"""

import argparse
import json
import re
import subprocess

PEER_PROPOSAL_MARKER = "peer server KEXINIT proposal"
CIPHERS_STOC_RE = re.compile(r"ciphers stoc:\s*(\S+)")


def local_ciphers():
    try:
        proc = subprocess.run(
            ["ssh", "-Q", "cipher"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def remote_ciphers(user, host, port):
    cmd = [
        "ssh",
        "-vv",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(port or 22),
        "{0}@{1}".format(user or "root", host),
        "exit",
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return [], "Timed out while contacting {0}.".format(host)
    except OSError as err:
        return [], str(err)

    seen_peer_proposal = False
    for line in proc.stderr.splitlines():
        if PEER_PROPOSAL_MARKER in line:
            seen_peer_proposal = True
            continue
        if not seen_peer_proposal:
            continue
        match = CIPHERS_STOC_RE.search(line)
        if match:
            return [c for c in match.group(1).split(",") if c], ""

    return [], "Could not read the cipher list offered by {0}.".format(host)


def main():
    parser = argparse.ArgumentParser(
        description="List SSH ciphers available locally and offered by a remote host"
    )
    parser.add_argument("--host", type=str, default="", help="remote host to probe")
    parser.add_argument("--user", type=str, default="root", help="remote user")
    parser.add_argument("--port", type=str, default="22", help="remote ssh port")
    args = parser.parse_args()

    result = {
        "success": True,
        "local": local_ciphers(),
        "remote": [],
        "remoteError": "",
    }

    if args.host:
        result["remote"], result["remoteError"] = remote_ciphers(
            args.user, args.host, args.port
        )

    print(json.dumps(result))


if __name__ == "__main__":
    main()
