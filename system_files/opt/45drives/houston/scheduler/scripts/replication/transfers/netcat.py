"""Netcat variant detection and connection helpers."""

import re
import shlex
import subprocess
import time

from ..logging_utils import dbg, safe_print
from ..ssh import ssh_base_args

# `which` is absent on minimal installs; `command -v` is a POSIX shell builtin.
_NC_PROBE_CMD = 'p=$(command -v nc 2>/dev/null) && readlink -f "$p"; nc -h 2>&1; true'


def _classify_nc(probe_output):
    """Return (flavour, sender_eof_args) from the binary path and `nc -h` output."""
    text = probe_output or ""
    lowered = text.lower()
    if "ncat" in lowered or "nmap" in lowered:
        return "ncat", ["--send-only"]
    if "openbsd" in lowered:
        flavour = "openbsd"
    elif "[v1.10" in lowered or "traditional" in lowered:
        flavour = "traditional"
    else:
        flavour = "unknown"
    # Without one of these, a sending nc keeps the socket open after its input ends.
    if re.search(r"^\s*-N\b", text, re.MULTILINE):
        return flavour, ["-N"]
    if re.search(r"^\s*-q\b", text, re.MULTILINE):
        return flavour, ["-q", "0"]
    return flavour, []


def _detect_nc(remote_user=None, remote_host=None, remote_port="22"):
    """Detect the local or remote netcat variant and its close-on-EOF sender flags."""
    try:
        if remote_user and remote_host:
            cmd = ssh_base_args(remote_user, remote_host, remote_port)
            cmd.append(_NC_PROBE_CMD)
        else:
            cmd = ["sh", "-c", _NC_PROBE_CMD]
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=10,
        )
        flavour, eof_args = _classify_nc((p.stdout or "") + "\n" + (p.stderr or ""))
    except Exception:
        flavour, eof_args = "unknown", []

    where = f"remote {remote_host}" if remote_host else "local"
    dbg(f"nc flavour on {where}: {flavour}; sender EOF args: {eof_args or 'none'}")
    if not eof_args:
        safe_print(
            f"WARNING: netcat on {where} ({flavour}) has no close-on-EOF option; "
            "a sending transfer may not finish when its data ends."
        )
    return flavour, eof_args


def build_nc_listen_cmd(port: str, remote_user=None, remote_host=None, remote_port="22", bind_address=None, send_only=False):
    """
    Build a portable `nc -l …` command string for the listener side.
    If bind_address is provided, binds the listener to that IP only.
    If send_only is True (pull: zfs send | nc -l), the listener closes the
    connection at end of input. Otherwise ncat uses --recv-only (push).

    IMPORTANT: Never combine -p with -l. Port is always passed as a positional
    argument, which works on all netcat variants.
    """
    flavour, eof_args = _detect_nc(remote_user, remote_host, remote_port)
    if send_only:
        flags = eof_args
    else:
        flags = ["--recv-only"] if flavour == "ncat" else []
    parts = ["nc", "-l", *flags]
    if bind_address:
        parts += ["-s", shlex.quote(bind_address)]
    parts.append(shlex.quote(port))
    return " ".join(parts)


def _build_nc_connect_cmd(host: str, port: str, recv_only=True):
    """Build a local nc connect command.
    recv_only=True for pull (client receives), False for push (client sends and
    must close the connection at end of input)."""
    flavour, eof_args = _detect_nc()
    if recv_only:
        flags = ["--recv-only"] if flavour == "ncat" else []
    else:
        flags = eof_args
    return ["nc", *flags, host, port]


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
