"""Interrupted ZFS receive continuation pipelines."""

import shlex
import subprocess
import threading
import time

from .common import *


def _start_remote_recv_over_ssh(
    recv_host_user,
    recv_host,
    recv_ssh_port,
    recv_name,
    force_overwrite,
    remote_mbuffer_enabled,
    m_buffer_size,
    m_buffer_unit,
    *,
    stdin,
):
    if not remote_mbuffer_enabled:
        recv_args = ["zfs", "recv", "-s"]
        if force_overwrite:
            recv_args.append("-F")
        recv_args.append(recv_name)
        return ssh_popen_args(
            recv_host_user,
            recv_host,
            recv_ssh_port,
            recv_args,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
        )

    recv_q = shlex.quote(recv_name)
    remote_cmd = f"{mbuffer_shell_stage(m_buffer_size, m_buffer_unit)} | zfs recv -s {'-F ' if force_overwrite else ''}{recv_q}"
    ssh_cmd = ssh_base_args(recv_host_user, recv_host, recv_ssh_port)
    ssh_cmd.append(remote_cmd)
    dbg(f"POPEN ssh (remote mbuffer recv): {_fmt_cmd(ssh_cmd)}")
    p = subprocess.Popen(
        ssh_cmd,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    )
    dbg(f"POPEN ssh pid={p.pid}")
    return p


def _start_remote_send_over_ssh(
    remote_user,
    remote_host,
    remote_ssh_port,
    resume_token,
    remote_mbuffer_enabled,
    m_buffer_size,
    m_buffer_unit,
):
    if not remote_mbuffer_enabled:
        return ssh_popen_args(
            remote_user,
            remote_host,
            remote_ssh_port,
            ["zfs", "send", "-t", resume_token],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
        )

    send_cmd = f"zfs send -t {shlex.quote(resume_token)} | {mbuffer_shell_stage(m_buffer_size, m_buffer_unit)}"
    ssh_cmd = ssh_base_args(remote_user, remote_host, remote_ssh_port)
    ssh_cmd.append(send_cmd)
    dbg(f"POPEN ssh (remote mbuffer send): {_fmt_cmd(ssh_cmd)}")
    p = subprocess.Popen(
        ssh_cmd,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    )
    dbg(f"POPEN ssh pid={p.pid}")
    return p

def resume_receive_push(
    resume_token,
    recvName,
    recvHost="",
    recvSshPort="22",
    recvHostUser="",
    mBufferSize="1",
    mBufferUnit="G",
    transferMethod="ssh",
    recvDataPort=None,
    forceOverwrite=False,
    stall_timeout=3600,
):
    notifier.notify("STATUS=Resuming ZFS send/recv pipeline from resume token…")

    remote_mbuffer_enabled = False
    if recvHost and transferMethod in ("ssh", "netcat"):
        remote_mbuffer_enabled = remote_has_command(recvHostUser, recvHost, recvSshPort, "mbuffer")
        if remote_mbuffer_enabled:
            msg = f"Remote mbuffer detected on {recvHost}; enabling two-ended buffering for resume."
            notifier.notify(f"STATUS={msg}")
            print(msg)
        else:
            msg = f"Remote mbuffer not found on {recvHost}; using local-only buffering for resume."
            notifier.notify(f"STATUS={msg}")
            print(msg)

    send_cmd = ["zfs", "send", "-t", resume_token]

    # Estimate resume send size for progress reporting
    total_bytes = estimate_send_size(send_cmd)
    if total_bytes:
        size_mib = total_bytes / (1024 * 1024)
        dbg(f"Resume send estimated size: {total_bytes} bytes ({size_mib:.1f} MiB)")
        print(f"Resuming interrupted transfer to {recvName} (~{size_mib:.0f} MiB remaining). Progress in debug log.")
    else:
        dbg("Resume send size estimation unavailable; progress will be indeterminate.")
        print(f"Resuming interrupted transfer to {recvName} (size unknown). Progress in debug log.")

    # Print CLI-reproducible resume command
    send_str = f"zfs send -t {shlex.quote(resume_token)}"
    recv_flags = "zfs recv -s" + (" -F" if forceOverwrite else "") + f" {recvName}"
    if transferMethod == "local" or not recvHost:
        print(f"CLI command: {send_str} | {recv_flags}")
    elif transferMethod == "netcat":
        data_port_cli = str(recvDataPort or recvSshPort or "31337")
        if remote_mbuffer_enabled:
            print(f"CLI command (sender): {send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | nc {recvHost} {data_port_cli}")
            print(f"CLI command (receiver): nc -l {data_port_cli} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {recv_flags}")
        else:
            print(f"CLI command (sender): {send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | nc {recvHost} {data_port_cli}")
            print(f"CLI command (receiver): nc -l {data_port_cli} | {recv_flags}")
    elif transferMethod == "mbuffer":
        data_port_cli = str(recvDataPort or recvSshPort or "31337")
        print(f"CLI command (sender): {send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -O {recvHost}:{data_port_cli}")
        print(f"CLI command (receiver): {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -I {data_port_cli} | {recv_flags}")
    else:
        ssh_target = f"{recvHostUser}@{recvHost}" if recvHostUser else recvHost
        ssh_port_flag = f" -p {recvSshPort}" if str(recvSshPort) != "22" else ""
        if remote_mbuffer_enabled:
            print(f"CLI command: {send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | ssh{ssh_port_flag} {ssh_target} '{mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {recv_flags}'")
        else:
            print(f"CLI command: {send_str} | ssh{ssh_port_flag} {ssh_target} {recv_flags}")

    process_send = subprocess.Popen(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if transferMethod == "local" or not recvHost:
        recv_cmd = ["zfs", "recv", "-s"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(recvName)
        dbg(f"PIPE recv cmd={_fmt_cmd(recv_cmd)}")
        process_recv = subprocess.Popen(
            recv_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        dbg(f"PIPE recv pid={process_recv.pid}")

        if process_send.stdout is None or process_recv.stdin is None:
            raise RuntimeError("Failed to initialize resume send/recv pipes.")

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_send.stdout, process_recv.stdin, total_bytes,
                label="Resuming", stall_timeout=stall_timeout,
            )
        except StallTimeout as e:
            notifier.notify(f"STATUS=Resume stalled: {e}")
            print(f"ERROR: {e}")
            _kill_procs(process_send, process_recv)
            return False, str(e)

        if pipe_broken:
            _kill_procs(process_send, process_recv)
            notifier.notify("STATUS=Resume transfer failed — downstream pipe broken.")
            err_msg = "ERROR: Resume transfer pipe broken. Downstream process (recv) likely died."
            safe_print(err_msg)
            return False, err_msg

        try:
            _close_pipe(process_recv.stdin)
            # Detach so communicate() below does not flush a closed pipe
            process_recv.stdin = None
        except Exception:
            pass

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        try:
            _wait_with_finalize_heartbeat(process_send, "zfs send", PIPELINE_FINALIZE_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_procs(process_send, process_recv)
            notifier.notify("STATUS=Finalization timed out — send process killed.")
            return False, f"zfs send did not exit within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed."

        try:
            recv_stdout, recv_stderr = _communicate_with_finalize_heartbeat(
                process_recv, "local zfs recv", PIPELINE_FINALIZE_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            process_recv.kill()
            notifier.notify("STATUS=Finalization timed out — recv process killed.")
            return False, f"zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed."
        recv_stdout = recv_stdout.decode(errors="replace") if recv_stdout else ""
        recv_stderr = recv_stderr.decode(errors="replace") if recv_stderr else ""

        if process_send.returncode != 0:
            notifier.notify("STATUS=Local resume send failed.")
            err_msg = f"send error: {send_stderr}"
            print(err_msg)
            return False, err_msg
        if process_recv.returncode != 0:
            notifier.notify("STATUS=Local resume receive failed.")
            err_msg = f"recv error: {recv_stderr}"
            print(err_msg)
            return False, err_msg
        notifier.notify("STATUS=Local resume receive completed.")
        if recv_stdout:
            print(recv_stdout)
        return True, ""

    if transferMethod == "netcat":
        data_port = str(recvDataPort or recvSshPort or "31337")
        ssh_port = str(recvSshPort or "22")

        recv_q = shlex.quote(recvName)
        nc_listen = build_nc_listen_cmd(data_port, recvHostUser, recvHost, ssh_port, bind_address=NC_BIND_ADDRESS)
        if remote_mbuffer_enabled:
            listen_cmd = f"{nc_listen} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | zfs recv -s {'-F ' if forceOverwrite else ''}{recv_q}"
        else:
            listen_cmd = f"{nc_listen} | zfs recv -s {'-F ' if forceOverwrite else ''}{recv_q}"
        ssh_cmd_listener = ssh_base_args(recvHostUser, recvHost, ssh_port)
        ssh_cmd_listener.append(listen_cmd)

        ssh_process_listener = subprocess.Popen(
            ssh_cmd_listener,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        if not _wait_for_port_remote(recvHostUser, recvHost, data_port, ssh_port, timeout=30):
            safe_print(f"WARNING: netcat listener on {recvHost}:{data_port} not ready after 30s, proceeding anyway")

        mbuffer_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
        process_mbuffer = subprocess.Popen(
            mbuffer_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        nc_cmd = _build_nc_connect_cmd(recvHost, data_port, recv_only=False)
        process_nc = subprocess.Popen(
            nc_cmd,
            stdin=process_mbuffer.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Close parent's copy so SIGPIPE propagates if nc dies
        _close_pipe(process_mbuffer.stdout)

        if process_send.stdout is None or process_mbuffer.stdin is None:
            raise RuntimeError("Failed to initialize resume netcat pipes.")

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_send.stdout, process_mbuffer.stdin, total_bytes,
                label="Resuming (netcat)", stall_timeout=stall_timeout,
            )
        except StallTimeout as e:
            notifier.notify(f"STATUS=Resume stalled: {e}")
            print(f"ERROR: {e}")
            _kill_procs(process_send, process_mbuffer, process_nc, ssh_process_listener)
            return False, str(e)

        if pipe_broken:
            _kill_procs(process_send, process_mbuffer, process_nc, ssh_process_listener)
            notifier.notify("STATUS=Resume transfer failed — downstream pipe broken.")
            err_msg = "ERROR: Resume transfer pipe broken. Downstream process (recv) likely died."
            safe_print(err_msg)
            return False, err_msg

        try:
            _close_pipe(process_mbuffer.stdin)
        except Exception:
            pass

        try:
            _, nc_stderr = _communicate_with_finalize_heartbeat(
                process_nc, "netcat sender", PIPELINE_FINALIZE_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            _kill_procs(process_send, process_mbuffer, process_nc, ssh_process_listener)
            notifier.notify("STATUS=Finalization timed out — netcat process killed.")
            return False, f"Netcat did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed."

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        mbuf_stderr = process_mbuffer.stderr.read().decode(errors="replace") if process_mbuffer.stderr else ""
        nc_err = nc_stderr.decode(errors="replace") if isinstance(nc_stderr, bytes) else (nc_stderr or "")

        try:
            _wait_with_finalize_heartbeat(process_send, "zfs send", PIPELINE_FINALIZE_TIMEOUT)
            _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_procs(process_send, process_mbuffer, ssh_process_listener)
            notifier.notify("STATUS=Finalization timed out — resume send pipeline killed.")
            return False, f"zfs send/mbuffer did not exit within {PIPELINE_FINALIZE_TIMEOUT}s. Processes killed."

        if process_send.returncode != 0:
            notifier.notify("STATUS=Netcat resume send failed.")
            ssh_process_listener.terminate()
            err_msg = f"[Sender Side] zfs send error: {send_stderr.strip()}"
            print(err_msg)
            return False, err_msg

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=Netcat resume send failed.")
            ssh_process_listener.terminate()
            err_msg = f"[Sender Side] mbuffer error: {mbuf_stderr.strip()}"
            print(err_msg)
            return False, err_msg

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat resume send failed.")
            print(f"[Sender Side] nc error: {nc_err}")
            if mbuf_stderr:
                print(f"[Sender Side] mbuffer error: {mbuf_stderr}")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            ssh_process_listener.terminate()
            err_msg = "Netcat resume send failed."
            return False, err_msg

        try:
            ssh_stdout, ssh_stderr = _communicate_with_finalize_heartbeat(
                ssh_process_listener, "remote netcat receiver", 300
            )
        except subprocess.TimeoutExpired:
            ssh_process_listener.kill()
            notifier.notify("STATUS=Finalization timed out — remote receiver killed.")
            return False, "Remote netcat receiver did not finish within 300s after all data was sent. Process killed."
        if ssh_process_listener.returncode != 0:
            notifier.notify("STATUS=Remote resume receive via netcat failed.")
            err_msg = f"[Receiver Side] Error during receive: {(ssh_stderr or '').strip()}"
            print(err_msg)
            return False, err_msg

        notifier.notify("STATUS=Netcat resume send/receive completed.")
        if ssh_stdout:
            print(ssh_stdout)
        return True, ""

    if transferMethod == "mbuffer":
        data_port = str(recvDataPort or recvSshPort or "31337")
        ssh_port = str(recvSshPort or "22")

        recv_q = shlex.quote(recvName)
        listen_cmd = (
            f"{mbuffer_shell_stage(mBufferSize, mBufferUnit)} -I {shlex.quote(data_port)} "
            f"| zfs recv -s {'-F ' if forceOverwrite else ''}{recv_q}"
        )
        ssh_cmd_listener = ssh_base_args(recvHostUser, recvHost, ssh_port)
        ssh_cmd_listener.append(listen_cmd)

        ssh_process_listener = subprocess.Popen(
            ssh_cmd_listener,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        if not _wait_for_port_remote(recvHostUser, recvHost, data_port, ssh_port, timeout=30):
            safe_print(f"WARNING: mbuffer listener on {recvHost}:{data_port} not ready after 30s, proceeding anyway")

        sender_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit) + ["-O", f"{recvHost}:{data_port}"]
        process_mbuffer = subprocess.Popen(
            sender_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mbuf_capture = StreamCapture(process_mbuffer.stderr)

        if process_send.stdout is None or process_mbuffer.stdin is None:
            raise RuntimeError("Failed to initialize resume mbuffer pipes.")

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_send.stdout,
                process_mbuffer.stdin,
                total_bytes,
                label="Resuming (mbuffer)",
                stall_timeout=stall_timeout,
            )
        except StallTimeout as e:
            notifier.notify(f"STATUS=Resume stalled: {e}")
            print(f"ERROR: {e}")
            _kill_procs(process_send, process_mbuffer, ssh_process_listener)
            return False, str(e)

        if pipe_broken:
            _kill_procs(process_send, process_mbuffer, ssh_process_listener)
            notifier.notify("STATUS=Resume transfer failed — downstream pipe broken.")
            err_msg = "ERROR: Resume transfer pipe broken. Downstream process (recv) likely died."
            safe_print(err_msg)
            return False, err_msg

        try:
            _close_pipe(process_mbuffer.stdin)
            process_mbuffer.stdin = None
        except Exception:
            pass

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        try:
            _wait_with_finalize_heartbeat(process_send, "zfs send", PIPELINE_FINALIZE_TIMEOUT)
            _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer network sender", PIPELINE_FINALIZE_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_procs(process_send, process_mbuffer, ssh_process_listener)
            notifier.notify("STATUS=Finalization timed out — resume send pipeline killed.")
            return False, f"zfs send/mbuffer did not exit within {PIPELINE_FINALIZE_TIMEOUT}s. Processes killed."
        mbuf_stderr = mbuf_capture.text()

        if process_send.returncode != 0:
            notifier.notify("STATUS=mBuffer resume send failed.")
            err_msg = f"send error: {send_stderr}"
            print(err_msg)
            ssh_process_listener.terminate()
            return False, err_msg

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=mBuffer resume send failed.")
            err_msg = f"mbuffer error: {mbuf_stderr}"
            print(err_msg)
            ssh_process_listener.terminate()
            return False, err_msg

        try:
            ssh_stdout, ssh_stderr = _communicate_with_finalize_heartbeat(
                ssh_process_listener, "remote mbuffer receiver", 300
            )
        except subprocess.TimeoutExpired:
            ssh_process_listener.kill()
            notifier.notify("STATUS=Finalization timed out — remote receiver killed.")
            return False, "Remote mbuffer receiver did not finish within 300s after all data was sent. Process killed."
        if ssh_process_listener.returncode != 0:
            notifier.notify("STATUS=Remote resume receive via mBuffer failed.")
            err_msg = f"[Receiver Side] Error during receive: {(ssh_stderr or '').strip()}"
            print(err_msg)
            return False, err_msg

        notifier.notify("STATUS=mBuffer resume send/receive completed.")
        if ssh_stdout:
            print(ssh_stdout)
        return True, ""

    if transferMethod != "ssh":
        print("ERROR: Resume tokens are only supported for local, ssh, netcat, or mbuffer transfers in this script.")
        return False, "Resume tokens are only supported for local, ssh, netcat, or mbuffer transfers in this script."

    m_buff_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    process_remote_recv = _start_remote_recv_over_ssh(
        recvHostUser,
        recvHost,
        recvSshPort,
        recvName,
        forceOverwrite,
        remote_mbuffer_enabled,
        mBufferSize,
        mBufferUnit,
        stdin=process_m_buff.stdout,
    )
    # Close parent's copy so SIGPIPE propagates if recv dies
    _close_pipe(process_m_buff.stdout)

    if process_send.stdout is None or process_m_buff.stdin is None:
        raise RuntimeError("Failed to initialize resume SSH pipes.")

    try:
        _, pipe_broken = stream_with_progress_stall(
            process_send.stdout, process_m_buff.stdin, total_bytes,
            label="Resuming", stall_timeout=stall_timeout,
        )
    except StallTimeout as e:
        notifier.notify(f"STATUS=Resume stalled: {e}")
        print(f"ERROR: {e}")
        _kill_procs(process_send, process_m_buff, process_remote_recv)
        return False, str(e)

    if pipe_broken:
        _kill_procs(process_send, process_m_buff, process_remote_recv)
        notifier.notify("STATUS=Resume transfer failed — downstream pipe broken.")
        err_msg = "ERROR: Resume transfer pipe broken. Downstream process (recv) likely died."
        safe_print(err_msg)
        return False, err_msg

    try:
        _close_pipe(process_m_buff.stdin)
    except Exception:
        pass

    send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
    mbuf_stderr = ""
    if process_m_buff.stderr:
        try:
            mbuf_stderr = process_m_buff.stderr.read().decode(errors="replace")
        except (OSError, ValueError):
            pass
    try:
        _wait_with_finalize_heartbeat(process_send, "zfs send", PIPELINE_FINALIZE_TIMEOUT)
        _wait_with_finalize_heartbeat(process_m_buff, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)
    except subprocess.TimeoutExpired:
        _kill_procs(process_send, process_m_buff, process_remote_recv)
        notifier.notify("STATUS=Finalization timed out — resume send pipeline killed.")
        return False, f"zfs send/mbuffer did not exit within {PIPELINE_FINALIZE_TIMEOUT}s. Processes killed."

    try:
        stdout, stderr = _communicate_with_finalize_heartbeat(
            process_remote_recv, "remote zfs recv", PIPELINE_FINALIZE_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        process_remote_recv.kill()
        notifier.notify("STATUS=Finalization timed out — remote recv process killed.")
        return False, f"Remote zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed."
    stdout = stdout.decode(errors="replace") if stdout else ""
    stderr = stderr.decode(errors="replace") if stderr else ""

    if process_send.returncode != 0:
        notifier.notify("STATUS=Remote resume send failed.")
        err_msg = f"send error: {send_stderr}"
        print(err_msg)
        return False, err_msg
    if process_m_buff.returncode != 0:
        notifier.notify("STATUS=Remote resume send failed.")
        err_msg = f"mbuffer error: {mbuf_stderr}"
        print(err_msg)
        return False, err_msg
    if process_remote_recv.returncode != 0:
        notifier.notify("STATUS=Remote resume receive failed.")
        err_msg = f"ERROR: remote recv error: {stderr}"
        print(err_msg)
        return False, err_msg
    notifier.notify("STATUS=Remote resume receive completed.")
    if stdout:
        print(stdout)
    return True, ""


def resume_receive_pull(
    resume_token,
    localRecvFs,
    remoteHost="",
    remoteSshPort="22",
    remoteUser="root",
    mBufferSize="1",
    mBufferUnit="G",
    forceOverwrite=False,
    stall_timeout=3600,
    transferMethod="ssh",
    recvDataPort=None,
    mbufferCallbackHost="",
):
    notifier.notify("STATUS=Resuming ZFS pull pipeline from resume token…")

    if not remoteHost:
        raise RuntimeError("Pull replication requires a remote host.")

    if transferMethod not in ("ssh", "netcat", "mbuffer"):
        notifier.notify("STATUS=Invalid transfer method for pull resume.")
        err_msg = f"Invalid transferMethod '{transferMethod}'. Pull resume supports 'ssh', 'netcat', or 'mbuffer'."
        print(f"ERROR: {err_msg}")
        return False, err_msg

    remote_mbuffer_enabled = False
    if transferMethod in ("ssh", "netcat"):
        remote_mbuffer_enabled = remote_has_command(remoteUser, remoteHost, remoteSshPort, "mbuffer")
        if remote_mbuffer_enabled:
            msg = f"Remote mbuffer detected on {remoteHost}; enabling two-ended buffering for resume."
            notifier.notify(f"STATUS={msg}")
            print(msg)
        else:
            msg = f"Remote mbuffer not found on {remoteHost}; using local-only buffering for resume."
            notifier.notify(f"STATUS={msg}")
            print(msg)

    # Estimate resume send size for progress reporting
    send_cmd = ["zfs", "send", "-t", resume_token]
    total_bytes = estimate_send_size_remote(remoteUser, remoteHost, remoteSshPort, send_cmd)
    if total_bytes:
        size_mib = total_bytes / (1024 * 1024)
        dbg(f"Resume pull send estimated size: {total_bytes} bytes ({size_mib:.1f} MiB)")
        print(f"Resuming interrupted transfer to {localRecvFs} (~{size_mib:.0f} MiB remaining). Progress in debug log.")
    else:
        dbg("Resume pull send size estimation unavailable; progress will be indeterminate.")
        print(f"Resuming interrupted transfer to {localRecvFs} (size unknown). Progress in debug log.")

    # Print CLI-reproducible resume command
    send_str_cli = f"zfs send -t {shlex.quote(resume_token)}"
    recv_flags = "zfs recv -s" + (" -F" if forceOverwrite else "") + f" {localRecvFs}"
    ssh_port_flag = f" -p {remoteSshPort}" if str(remoteSshPort) != "22" else ""
    mbuffer_callback_expr = None
    mbuffer_callback_display = None
    mbuffer_callback_cli = None
    if transferMethod == "mbuffer":
        _callback_port = str(recvDataPort or remoteSshPort or "31337")
        mbuffer_callback_expr, mbuffer_callback_display, mbuffer_callback_cli = resolve_mbuffer_callback_target_for_remote(
            remoteUser,
            remoteHost,
            remoteSshPort,
            mbufferCallbackHost,
            _callback_port,
        )
    if transferMethod == "netcat":
        data_port_cli = str(recvDataPort or remoteSshPort or "31337")
        local_recv_stage = f"nc {remoteHost} {data_port_cli} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {recv_flags}"
        if remote_mbuffer_enabled:
            print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str_cli} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | nc -l {data_port_cli}'")
        else:
            print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str_cli} | nc -l {data_port_cli}'")
        print(f"CLI command (dest, local receiver):   {local_recv_stage}")
    elif transferMethod == "mbuffer":
        data_port_cli = str(recvDataPort or remoteSshPort or "31337")
        print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str_cli} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -O {mbuffer_callback_cli}'")
        print(f"CLI command (dest, local receiver):   {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -I {data_port_cli} | {recv_flags}")
    else:
        if remote_mbuffer_enabled:
            print(f"CLI command: ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str_cli} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)}' | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {recv_flags}")
        else:
            print(f"CLI command: ssh{ssh_port_flag} {remoteUser}@{remoteHost} {send_str_cli} | {recv_flags}")

    if transferMethod == "netcat":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        ssh_port = str(remoteSshPort or "22")

        notifier.notify(f"STATUS=Resuming pull via netcat from {remoteUser}@{remoteHost} into {localRecvFs}…")

        # Remote: zfs send -t <token> | nc -l <port>
        send_str = f"zfs send -t {shlex.quote(resume_token)}"
        nc_listen = build_nc_listen_cmd(data_port, remoteUser, remoteHost, ssh_port, bind_address=NC_BIND_ADDRESS, send_only=True)
        if remote_mbuffer_enabled:
            remote_cmd = f"{send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {nc_listen}"
        else:
            remote_cmd = f"{send_str} | {nc_listen}"
        ssh_cmd_sender = ssh_base_args(remoteUser, remoteHost, ssh_port)
        ssh_cmd_sender.append(remote_cmd)

        ssh_process_sender = subprocess.Popen(
            ssh_cmd_sender,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        if not _wait_for_port_remote(remoteUser, remoteHost, data_port, ssh_port, timeout=30):
            safe_print(f"WARNING: netcat listener on {remoteHost}:{data_port} not ready after 30s, proceeding anyway")

        # Local: nc <remote> <port> | pv | mbuffer | zfs recv
        nc_cmd = _build_nc_connect_cmd(remoteHost, data_port, recv_only=True)
        process_nc = subprocess.Popen(
            nc_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Insert pv for progress monitoring on pull resume
        process_pv = None
        pv_source = process_nc.stdout
        if _has_pv():
            process_pv = subprocess.Popen(
                _build_pv_cmd(total_bytes),
                stdin=process_nc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            _close_pipe(process_nc.stdout)
            pv_source = process_pv.stdout
        else:
            safe_print(
                "WARNING: pv is not installed; progress reporting and the stall watchdog "
                "are disabled for this netcat resume."
            )

        mbuffer_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
        process_mbuffer = subprocess.Popen(
            mbuffer_cmd,
            stdin=pv_source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mbuf_capture = StreamCapture(process_mbuffer.stderr)
        if process_pv:
            _close_pipe(process_pv.stdout)
        else:
            _close_pipe(process_nc.stdout)

        # Start pv progress monitor thread (with stall tracking)
        last_activity = [time.time()]
        if process_pv:
            pv_thread = threading.Thread(
                target=_pv_monitor_thread,
                args=(process_pv.stderr, total_bytes, "Resuming", notifier, last_activity),
                daemon=True,
            )
            pv_thread.start()

        recv_cmd = ["zfs", "recv", "-s"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(localRecvFs)
        dbg(f"PIPE recv cmd={_fmt_cmd(recv_cmd)}")

        process_local_recv = subprocess.Popen(
            recv_cmd,
            stdin=process_mbuffer.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        dbg(f"PIPE recv pid={process_local_recv.pid}")
        _close_pipe(process_mbuffer.stdout)

        # Wait for pipeline with stall detection
        _stall_timeout = stall_timeout or TRANSFER_STALL_TIMEOUT
        # pv is the only activity source for this pipeline; without it every poll looks idle.
        _stall_enabled = bool(process_pv and _stall_timeout and _stall_timeout > 0)
        _poll = min(30.0, _stall_timeout) if _stall_enabled else 60.0

        while True:
            try:
                recv_stdout, recv_stderr = safe_communicate(process_local_recv, timeout=_poll)
                break
            except subprocess.TimeoutExpired:
                if not _stall_enabled:
                    notifier.notify("STATUS=Resuming via netcat… still running (no pv, progress unavailable).")
                    continue
                idle = time.time() - last_activity[0]
                if idle >= _stall_timeout:
                    dbg(f"netcat pull resume: STALL detected — no pv activity for {int(idle)}s, killing pipeline")
                    notifier.notify(f"STATUS=Resume stalled — no data flow for {int(idle)}s, aborting.")
                    for p in [process_local_recv, process_mbuffer, process_nc, ssh_process_sender]:
                        try:
                            p.kill()
                        except Exception:
                            pass
                    if process_pv:
                        try:
                            process_pv.kill()
                        except Exception:
                            pass
                    return False, (f"Pipeline stalled: no data transferred for {int(idle)}s "
                                   f"(stall timeout: {_stall_timeout}s).")
                else:
                    dbg(f"netcat pull resume: watchdog check — last activity {int(idle)}s ago (timeout {_stall_timeout}s)")
                    continue
        recv_stdout = recv_stdout.decode(errors="replace") if isinstance(recv_stdout, bytes) else (recv_stdout or "")
        recv_stderr = recv_stderr.decode(errors="replace") if isinstance(recv_stderr, bytes) else (recv_stderr or "")

        notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
        try:
            _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)
            if process_pv:
                _wait_with_finalize_heartbeat(process_pv, "pv monitor", PIPELINE_FINALIZE_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_procs(process_mbuffer, process_pv, process_nc, ssh_process_sender)
            notifier.notify("STATUS=Finalization timed out — buffer stage killed.")
            return False, f"mbuffer/pv did not drain within {PIPELINE_FINALIZE_TIMEOUT}s after the receive completed. Processes killed."

        try:
            _, nc_stderr = _communicate_with_finalize_heartbeat(
                process_nc,
                "netcat receiver",
                PIPELINE_FINALIZE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            _kill_procs(process_nc, ssh_process_sender)
            notifier.notify("STATUS=Finalization timed out — netcat receiver killed.")
            return False, f"netcat receiver did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was received. Process killed."

        try:
            ssh_stdout, ssh_stderr = _communicate_with_finalize_heartbeat(
                ssh_process_sender,
                "remote netcat sender",
                300,
            )
        except subprocess.TimeoutExpired:
            ssh_process_sender.kill()
            notifier.notify("STATUS=Finalization timed out — remote sender killed.")
            return False, "Remote sender did not finish during netcat pull resume finalization. Process killed."

        mbuf_err = mbuf_capture.text()

        if ssh_process_sender.returncode != 0:
            notifier.notify("STATUS=Remote resume send via netcat failed.")
            err_msg = f"[Remote Side] Error during send: {(ssh_stderr or '').strip()}"
            print(err_msg)
            return False, err_msg
        if process_nc.returncode != 0:
            nc_err = nc_stderr.decode(errors="replace") if isinstance(nc_stderr, bytes) else (nc_stderr or "")
            notifier.notify("STATUS=Netcat resume pull failed.")
            err_msg = f"[Receiver Side] nc error: {nc_err}"
            print(err_msg)
            return False, err_msg

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=Netcat resume pull failed.")
            err_msg = f"[Receiver Side] mbuffer error: {mbuf_err}"
            print(err_msg)
            return False, err_msg

        if process_local_recv.returncode != 0:
            notifier.notify("STATUS=Local resume receive (pull via netcat) failed.")
            err_msg = f"ERROR: local recv error: {recv_stderr}"
            print(err_msg)
            return False, err_msg

        notifier.notify("STATUS=Netcat pull resume receive completed.")
        if recv_stdout:
            print(recv_stdout)
        return True, ""

    if transferMethod == "mbuffer":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        ssh_port = str(remoteSshPort or "22")
        callback_expr = mbuffer_callback_expr
        callback_display = mbuffer_callback_display

        notifier.notify(f"STATUS=Resuming pull via mbuffer from {remoteUser}@{remoteHost} into {localRecvFs}…")

        notifier.notify(f"STATUS=Running callback preflight from source to {callback_display}:{data_port}…")
        preflight_ok, preflight_detail, preflight_checked = preflight_remote_callback_connectivity(
            remoteUser,
            remoteHost,
            ssh_port,
            callback_expr,
            callback_display,
            data_port,
        )
        if preflight_checked and not preflight_ok:
            notifier.notify(f"STATUS=Data-plane blocked: source cannot reach callback host {callback_display}:{data_port}.")
            err_msg = (
                f"Data-plane blocked for mbuffer pull resume. Source {remoteHost} cannot reach "
                f"callback host {callback_display}:{data_port}."
            )
            print(f"ERROR: {err_msg}")
            if preflight_detail:
                print(f"Preflight detail: {preflight_detail}")
            print("Hint: Open firewall/route for callback host:port or set an explicit mBuffer callback host.")
            return False, err_msg
        if preflight_checked and preflight_detail:
            notifier.notify(f"STATUS=Callback preflight note: {preflight_detail}")
            print(f"Preflight note: {preflight_detail}")
        if not preflight_checked:
            notifier.notify(f"STATUS=Callback preflight skipped ({preflight_detail}).")
            print(f"Warning: {preflight_detail}")

        mbuffer_listen_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit) + ["-I", data_port]
        process_mbuffer = subprocess.Popen(
            mbuffer_listen_cmd,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mbuf_capture = StreamCapture(process_mbuffer.stderr)

        recv_cmd = ["zfs", "recv", "-s"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(localRecvFs)
        dbg(f"PIPE recv cmd={_fmt_cmd(recv_cmd)}")
        process_local_recv = subprocess.Popen(
            recv_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
        )
        dbg(f"PIPE recv pid={process_local_recv.pid}")

        notifier.notify(f"STATUS=Listener ready on local port {data_port}; waiting for remote mbuffer callback from {remoteHost} to {callback_display}:{data_port}…")

        send_str = f"zfs send -t {shlex.quote(resume_token)}"
        remote_cmd = f"{send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -O {callback_expr}:{shlex.quote(data_port)}"
        ssh_cmd_sender = ssh_base_args(remoteUser, remoteHost, ssh_port)
        ssh_cmd_sender.append(remote_cmd)
        ssh_process_sender = subprocess.Popen(
            ssh_cmd_sender,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        notifier.notify("STATUS=Remote sender started; waiting for first data bytes…")

        if process_mbuffer.stdout is None or process_local_recv.stdin is None:
            raise RuntimeError("Failed to initialize resume mbuffer pull pipes.")

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_mbuffer.stdout,
                process_local_recv.stdin,
                total_bytes,
                label="Resuming (mbuffer)",
                stall_timeout=stall_timeout,
            )
        except StallTimeout as e:
            notifier.notify(f"STATUS=Resume stalled: {e}")
            print(f"ERROR: {e}")
            _kill_procs(process_mbuffer, process_local_recv, ssh_process_sender)
            return False, str(e)

        if pipe_broken:
            _kill_procs(process_mbuffer, process_local_recv, ssh_process_sender)
            notifier.notify("STATUS=Resume transfer failed — downstream pipe broken.")
            err_msg = "ERROR: Resume transfer pipe broken. Downstream process (recv) likely died."
            safe_print(err_msg)
            return False, err_msg

        try:
            _close_pipe(process_local_recv.stdin)
            process_local_recv.stdin = None
        except Exception:
            pass

        try:
            _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer listener", PIPELINE_FINALIZE_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_procs(process_mbuffer, process_local_recv, ssh_process_sender)
            notifier.notify("STATUS=Finalization timed out — mbuffer listener killed.")
            return False, f"mbuffer listener did not drain within {PIPELINE_FINALIZE_TIMEOUT}s after all data was received. Processes killed."

        try:
            recv_stdout, recv_stderr = _communicate_with_finalize_heartbeat(
                process_local_recv, "local zfs recv", PIPELINE_FINALIZE_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            process_local_recv.kill()
            ssh_process_sender.kill()
            notifier.notify("STATUS=Finalization timed out — local recv process killed.")
            return False, f"Local zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was received. Process killed."

        try:
            ssh_stdout, ssh_stderr = _communicate_with_finalize_heartbeat(
                ssh_process_sender, "remote sender", 300
            )
        except subprocess.TimeoutExpired:
            ssh_process_sender.kill()
            notifier.notify("STATUS=Finalization timed out — remote sender process killed.")
            return False, "Remote sender did not finish during mbuffer pull resume finalization. Process killed."

        recv_stdout = recv_stdout.decode(errors="replace") if isinstance(recv_stdout, bytes) else (recv_stdout or "")
        recv_stderr = recv_stderr.decode(errors="replace") if isinstance(recv_stderr, bytes) else (recv_stderr or "")
        mbuf_err = mbuf_capture.text()

        if ssh_process_sender.returncode != 0:
            notifier.notify("STATUS=Remote resume send via mbuffer failed.")
            err_msg = f"[Remote Side] Error during send: {(ssh_stderr or '').strip()}"
            print(err_msg)
            return False, err_msg

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=mBuffer resume pull failed.")
            err_msg = f"[Receiver Side] mbuffer error: {mbuf_err}"
            print(err_msg)
            return False, err_msg

        if process_local_recv.returncode != 0:
            notifier.notify("STATUS=Local resume receive (pull via mbuffer) failed.")
            err_msg = f"ERROR: local recv error: {recv_stderr}"
            print(err_msg)
            return False, err_msg

        notifier.notify("STATUS=mBuffer pull resume receive completed.")
        if recv_stdout:
            print(recv_stdout)
        return True, ""

    # SSH transfer (default)
    process_remote_send = _start_remote_send_over_ssh(
        remoteUser,
        remoteHost,
        remoteSshPort,
        resume_token,
        remote_mbuffer_enabled,
        mBufferSize,
        mBufferUnit,
    )

    m_buff_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    recv_cmd = ["zfs", "recv", "-s"]
    if forceOverwrite:
        recv_cmd.append("-F")
    recv_cmd.append(localRecvFs)
    dbg(f"PIPE recv cmd={_fmt_cmd(recv_cmd)}")
    process_local_recv = subprocess.Popen(
        recv_cmd,
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    dbg(f"PIPE recv pid={process_local_recv.pid}")

    if process_remote_send.stdout is None or process_m_buff.stdin is None:
        raise RuntimeError("Failed to initialize resume pull pipes.")

    try:
        _, pipe_broken = stream_with_progress_stall(
            process_remote_send.stdout, process_m_buff.stdin, total_bytes,
            label="Resuming (pull)", stall_timeout=stall_timeout,
        )
    except StallTimeout as e:
        notifier.notify(f"STATUS=Resume stalled: {e}")
        print(f"ERROR: {e}")
        _kill_procs(process_remote_send, process_m_buff, process_local_recv)
        return False, str(e)

    if pipe_broken:
        _kill_procs(process_remote_send, process_m_buff, process_local_recv)
        notifier.notify("STATUS=Resume transfer failed — downstream pipe broken.")
        err_msg = "ERROR: Resume transfer pipe broken. Downstream process (recv) likely died."
        safe_print(err_msg)
        return False, err_msg

    try:
        _close_pipe(process_m_buff.stdin)
    except Exception:
        pass

    remote_err = process_remote_send.stderr.read().decode(errors="replace") if process_remote_send.stderr else ""
    mbuf_stderr = ""
    if process_m_buff.stderr:
        try:
            mbuf_stderr = process_m_buff.stderr.read().decode(errors="replace")
        except (OSError, ValueError):
            pass
    try:
        _wait_with_finalize_heartbeat(process_remote_send, "remote zfs send", PIPELINE_FINALIZE_TIMEOUT)
        _wait_with_finalize_heartbeat(process_m_buff, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)
    except subprocess.TimeoutExpired:
        _kill_procs(process_remote_send, process_m_buff, process_local_recv)
        notifier.notify("STATUS=Finalization timed out — resume pull pipeline killed.")
        return False, f"Remote zfs send/mbuffer did not exit within {PIPELINE_FINALIZE_TIMEOUT}s. Processes killed."

    try:
        stdout, stderr = _communicate_with_finalize_heartbeat(
            process_local_recv, "local zfs recv", PIPELINE_FINALIZE_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        process_local_recv.kill()
        notifier.notify("STATUS=Finalization timed out — local recv process killed.")
        return False, f"Local zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed."
    stderr = stderr if isinstance(stderr, str) else (stderr.decode(errors="replace") if stderr else "")

    if process_local_recv.returncode != 0:
        notifier.notify("STATUS=Local resume receive (pull) failed.")
        err_msg = f"ERROR: local recv error: {stderr}"
        print(err_msg)
        if remote_err:
            print(f"[Remote zfs send stderr]\n{remote_err}")
        return False, err_msg

    if process_remote_send.returncode != 0:
        notifier.notify("STATUS=Resume send failed.")
        err_msg = f"ERROR: remote send error: {remote_err}"
        print(err_msg)
        return False, err_msg

    if process_m_buff.returncode != 0:
        notifier.notify("STATUS=Resume receive failed.")
        err_msg = f"ERROR: mbuffer error: {mbuf_stderr}"
        print(err_msg)
        return False, err_msg

    notifier.notify("STATUS=Pull resume receive completed.")
    if stdout:
        print(stdout)
    return True, ""
