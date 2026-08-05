"""Shared names used by transfer pipeline implementations."""

import shlex

from ..constants import (
    DIRECT_PIPE_ENABLED,
    MBUFFER_BLOCK_SIZE,
    NC_BIND_ADDRESS,
    PIPELINE_FINALIZE_TIMEOUT,
    TRANSFER_STALL_TIMEOUT,
)
from ..context import notifier
from ..logging_utils import _fmt_cmd, dbg, safe_print
from ..planner import build_zfs_send_args
from ..process import (
    StallTimeout,
    StreamCapture,
    _build_mbuffer_cmd,
    _close_pipe,
    _communicate_with_finalize_heartbeat,
    _direct_pipe_transfer,
    _has_pv,
    _kill_procs,
    _pv_monitor_thread,
    _wait_with_finalize_heartbeat,
    estimate_send_size,
    stream_with_progress_stall,
)
from ..ssh import estimate_send_size_remote, remote_has_command, ssh_base_args, ssh_popen_args, ssh_run_args
from .netcat import _build_nc_connect_cmd, _wait_for_port_remote, build_nc_listen_cmd


def mbuffer_shell_stage(buf_size, buf_unit):
    """Render a shell-safe mbuffer stage for remote pipeline command strings."""
    return "mbuffer -s {block} -m {size}".format(
        block=shlex.quote(str(MBUFFER_BLOCK_SIZE)),
        size=shlex.quote(f"{buf_size}{buf_unit}"),
    )

__all__ = [
    "DIRECT_PIPE_ENABLED",
    "MBUFFER_BLOCK_SIZE",
    "NC_BIND_ADDRESS",
    "PIPELINE_FINALIZE_TIMEOUT",
    "TRANSFER_STALL_TIMEOUT",
    "notifier",
    "_fmt_cmd",
    "dbg",
    "safe_print",
    "build_zfs_send_args",
    "StallTimeout",
    "StreamCapture",
    "_build_mbuffer_cmd",
    "_close_pipe",
    "_communicate_with_finalize_heartbeat",
    "_direct_pipe_transfer",
    "_has_pv",
    "_kill_procs",
    "_pv_monitor_thread",
    "_wait_with_finalize_heartbeat",
    "estimate_send_size",
    "stream_with_progress_stall",
    "estimate_send_size_remote",
    "remote_has_command",
    "ssh_base_args",
    "ssh_popen_args",
    "ssh_run_args",
    "mbuffer_shell_stage",
    "_build_nc_connect_cmd",
    "_wait_for_port_remote",
    "build_nc_listen_cmd",
]
