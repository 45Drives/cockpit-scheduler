"""Netcat variant detection and connection helpers."""

import shlex
import subprocess
import time

from ..logging_utils import dbg
from ..ssh import ssh_base_args

def _detect_nc_flavour(remote_user=None, remote_host=None, remote_port="22"):
    """
    Detect which netcat variant is installed (locally or on a remote host).
    Returns "ncat" for nmap-ncat (Rocky/RHEL), "openbsd" for netcat-openbsd
    (Ubuntu/Debian), or "unknown".

    Detection strategy:
      1. `readlink -f $(which nc)` — binary path is the most reliable indicator
      2. `nc -h` output — look for self-identification strings
    """
    try:
        # Primary: resolve the actual binary path via readlink
        readlink_cmd = "readlink -f $(which nc) 2>/dev/null || true"
        if remote_user and remote_host:
            ssh_cmd = ssh_base_args(remote_user, remote_host, remote_port)
            ssh_cmd.append(readlink_cmd)
            p = subprocess.run(
                ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=10,
            )
        else:
            p = subprocess.run(
                ["sh", "-c", readlink_cmd], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, universal_newlines=True, timeout=10,
            )
        bin_path = (p.stdout or "").strip().lower()
        if "ncat" in bin_path:
            return "ncat"
        if "openbsd" in bin_path:
            return "openbsd"

        # Fallback: parse nc -h output for self-identification
        if remote_user and remote_host:
            ssh_cmd = ssh_base_args(remote_user, remote_host, remote_port)
            ssh_cmd.append("nc -h")
            p = subprocess.run(
                ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=10,
            )
        else:
            p = subprocess.run(
                ["nc", "-h"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=10,
            )
        out = ((p.stdout or "") + " " + (p.stderr or "")).lower()
        if "ncat" in out or "nmap" in out:
            return "ncat"
        if "openbsd" in out:
            return "openbsd"
    except Exception:
        pass

    return "unknown"


def build_nc_listen_cmd(port: str, remote_user=None, remote_host=None, remote_port="22", bind_address=None, send_only=False):
    """
    Build a portable `nc -l …` command string for the listener side.
    Handles ncat (Rocky/RHEL) vs netcat-openbsd (Ubuntu/Debian).
    If bind_address is provided, binds the listener to that IP only.
    If send_only is True, ncat uses --send-only (for pull: zfs send | nc -l).
    If send_only is False, ncat uses --recv-only (for push: nc -l | zfs recv).

    IMPORTANT: Never combine -p with -l. Port is always passed as a positional
    argument, which works on all netcat variants.
    """
    flavour = _detect_nc_flavour(remote_user, remote_host, remote_port)
    dbg(f"nc flavour on {'remote' if remote_host else 'local'}: {flavour}")
    port_q = shlex.quote(port)
    bind_q = shlex.quote(bind_address) if bind_address else None
    if flavour == "ncat":
        # ncat: nc -l [--send-only|--recv-only] [-s bind] <port>
        direction_flag = "--send-only" if send_only else "--recv-only"
        if bind_q:
            return f"nc -l {direction_flag} -s {bind_q} {port_q}"
        return f"nc -l {direction_flag} {port_q}"
    # openbsd / unknown: nc -l [-s bind] <port>  (positional port, no -p)
    if bind_q:
        return f"nc -l -s {bind_q} {port_q}"
    return f"nc -l {port_q}"


def _build_nc_connect_cmd(host: str, port: str, recv_only=True):
    """Build a local nc connect command with --recv-only or --send-only for ncat.
    recv_only=True for pull (client receives), False for push (client sends)."""
    flavour = _detect_nc_flavour()
    if flavour == "ncat":
        flag = "--recv-only" if recv_only else "--send-only"
        return ["nc", flag, host, port]
    # openbsd and unknown: no direction flags available
    return ["nc", host, port]


def _wait_for_port_remote(user, host, port, ssh_port="22", timeout=30, interval=0.5):
    """Check from the REMOTE side whether a port is listening, via SSH + ss.
    This avoids consuming a single-accept netcat listener with a local TCP probe."""
    deadline = time.time() + timeout
    port_str = str(port)
    check_cmd = f"ss -tln 'sport = :{port_str}' | grep -q ':{port_str}'"
    while time.time() < deadline:
        try:
            ssh_cmd = ssh_base_args(user, host, ssh_port)
            ssh_cmd.append(check_cmd)
            rc = subprocess.run(
                ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=min(5, deadline - time.time()),
            ).returncode
            if rc == 0:
                dbg(f"_wait_for_port_remote: {host}:{port} ready (via ss)")
                return True
        except (subprocess.TimeoutExpired, OSError):
            pass
        time.sleep(interval)
    dbg(f"_wait_for_port_remote: {host}:{port} timeout after {timeout}s")
    return False
