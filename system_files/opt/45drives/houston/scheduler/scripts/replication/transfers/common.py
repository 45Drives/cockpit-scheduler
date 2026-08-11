"""Shared names used by transfer pipeline implementations."""

import shlex

from ..constants import (
    DIRECT_PIPE_ENABLED,
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
    _effective_mbuffer_block,
    estimate_send_size,
    stream_with_progress_stall,
)
from ..ssh import estimate_send_size_remote, remote_has_command, ssh_base_args, ssh_popen_args, ssh_run_args
from .netcat import _build_nc_connect_cmd, _wait_for_port_remote, build_nc_listen_cmd


def mbuffer_shell_stage(buf_size, buf_unit):
    """Render a shell-safe mbuffer stage for remote pipeline command strings."""
    return "mbuffer -s {block} -m {size}".format(
        block=shlex.quote(str(_effective_mbuffer_block())),
        size=shlex.quote(f"{buf_size}{buf_unit}"),
    )


def resolve_mbuffer_callback_target(callback_host, callback_port):
    """Return remote-shell callback host expression plus user-facing display text."""
    host = str(callback_host or "").strip()
    port = str(callback_port)
    if host:
        return shlex.quote(host), host, f"{host}:{port}"
    return "${SSH_CLIENT%% *}", "<ssh-client-source-ip>", "${SSH_CLIENT%% *}:" + port


def resolve_mbuffer_callback_target_for_remote(remote_user, remote_host, remote_port, callback_host, callback_port):
    """Resolve callback target, preferring an explicit host and otherwise probing SSH_CLIENT.

    Returns (callback_expr, callback_display, callback_cli).
    """
    callback_expr, callback_display, callback_cli = resolve_mbuffer_callback_target(callback_host, callback_port)

    if str(callback_host or "").strip():
        return callback_expr, callback_display, callback_cli

    try:
        proc = ssh_run_args(
            remote_user,
            remote_host,
            remote_port,
            ["/bin/sh", "-lc", "printf '%s' \"${SSH_CLIENT%% *}\""],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        resolved = (proc.stdout or "").strip()
        if proc.returncode == 0 and resolved:
            return shlex.quote(resolved), resolved, f"{resolved}:{callback_port}"
    except Exception:
        pass

    return callback_expr, callback_display, callback_cli


def preflight_remote_callback_connectivity(remote_user, remote_host, remote_port, callback_host_expr, callback_host_display, callback_port, timeout=4):
    """Check whether the remote side can reach the callback host/port.

    Returns a tuple: (ok, detail, checked). When checked is False the check was skipped.
    """
    script = (
        "HOST={host}; PORT={port}; "
        "if command -v nc >/dev/null 2>&1; then "
        "nc -z -v -w {timeout} \"$HOST\" \"$PORT\" 2>&1; "
        "exit $?; "
        "fi; "
        "echo 'callback preflight skipped: nc not installed'; "
        "exit 127"
    ).format(
        host=callback_host_expr,
        port=shlex.quote(str(callback_port)),
        timeout=max(1, int(timeout)),
    )

    proc = ssh_run_args(
        remote_user,
        remote_host,
        remote_port,
        ["/bin/sh", "-lc", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=max(10, int(timeout) + 6),
    )

    output = "\n".join(part for part in ((proc.stdout or "").strip(), (proc.stderr or "").strip()) if part).strip()
    output_lc = output.lower()

    if proc.returncode == 127:
        return True, "callback preflight skipped: nc not installed on source host", False

    if proc.returncode == 0:
        return True, "", True

    if "refused" in output_lc:
        # Connection refused still proves route/address reachability.
        dbg("callback preflight: route reachable but listener not accepting yet (connection refused)")
        return True, "", True

    detail = output if output else "connectivity check failed without diagnostic output"
    return False, detail, True

__all__ = [
    "DIRECT_PIPE_ENABLED",
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
    "resolve_mbuffer_callback_target",
    "resolve_mbuffer_callback_target_for_remote",
    "preflight_remote_callback_connectivity",
    "_build_nc_connect_cmd",
    "_wait_for_port_remote",
    "build_nc_listen_cmd",
]
