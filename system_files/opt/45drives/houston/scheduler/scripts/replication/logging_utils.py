"""Fault-tolerant console and debug logging helpers."""

import datetime
import os
import shlex
import sys

class SafeStream:
    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        try:
            return self._stream.write(data)
        except Exception:
            return 0

    def flush(self):
        try:
            return self._stream.flush()
        except Exception:
            return None

    def isatty(self):
        try:
            return self._stream.isatty()
        except Exception:
            return False

    def fileno(self):
        try:
            return self._stream.fileno()
        except Exception:
            return -1

    def __getattr__(self, name):
        return getattr(self._stream, name)


def configure_standard_streams():
    """Make service output resilient to stdout/stderr being closed."""
    if not isinstance(sys.stdout, SafeStream):
        sys.stdout = SafeStream(sys.stdout)
    if not isinstance(sys.stderr, SafeStream):
        sys.stderr = SafeStream(sys.stderr)

_DEBUG_TASK_NAME = os.environ.get("taskName", "").strip()
DEBUG_LOG = os.environ.get(
    "ZFS_REP_DEBUG_LOG",
    f"/tmp/zfs_rep_debug_{_DEBUG_TASK_NAME}.log" if _DEBUG_TASK_NAME else "/tmp/zfs_rep_debug.log",
)
DEBUG_ENABLED = os.environ.get("ZFS_REP_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")
DEBUG_MAX_TEXT = int(os.environ.get("ZFS_REP_DEBUG_MAX_TEXT", "4000"))

def safe_print(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            sys.stderr.write(str(msg) + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def _truncate(s: str, limit: int = DEBUG_MAX_TEXT) -> str:
    if s is None:
        return ""
    s = str(s)
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n...[truncated {len(s) - limit} chars]"


def dbg(msg: str):
    if not DEBUG_ENABLED:
        return
    try:
        line = f"{datetime.datetime.now().isoformat()} {msg}\n"
        with open(DEBUG_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass


def dbg_kv(title: str, kv: dict):
    if not DEBUG_ENABLED:
        return
    dbg(f"{title}: " + ", ".join(f"{k}={v}" for k, v in kv.items()))


def dbg_env():
    keys = [
        "taskName",
        "zfsRepConfig_direction",
        "zfsRepConfig_sendOptions_transferMethod",
        "zfsRepConfig_sendOptions_recursive_flag",
        "zfsRepConfig_sendOptions_compressed_flag",
        "zfsRepConfig_sendOptions_raw_flag",
        "zfsRepConfig_sendOptions_allowOverwrite",
        "zfsRepConfig_sendOptions_useExistingDest",
        "zfsRepConfig_sendOptions_includeIntermediateSnapshots",
        "zfsRepConfig_destDataset_user",
        "zfsRepConfig_destDataset_host",
        "zfsRepConfig_destDataset_port",
        "zfsRepConfig_destDataset_sshPort",
        "zfsRepConfig_sourceDataset_pool",
        "zfsRepConfig_sourceDataset_dataset",
        "zfsRepConfig_destDataset_pool",
        "zfsRepConfig_destDataset_dataset",
        "ZFS_REP_SSH_CIPHER",
        "ZFS_REP_CHUNK_SIZE",
        "ZFS_REP_MBUFFER_BLOCK",
        "ZFS_REP_DIRECT_PIPE",
        "ZFS_REP_TCP_TUNING",
        "ZFS_REP_TCP_CC",
        "ZFS_REP_NC_BIND_ADDRESS",
        "HOME",
        "PATH",
    ]
    snap = {}
    for k in keys:
        v = os.environ.get(k)
        if v is None:
            continue
        snap[k] = v
    dbg_kv("env", snap)


def _fmt_cmd(cmd):
    if isinstance(cmd, (list, tuple)):
        return " ".join(shlex.quote(str(c)) for c in cmd)
    return str(cmd)
