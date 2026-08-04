"""Interrupted ZFS receive continuation pipelines."""

import shlex
import subprocess
import threading
import time

from .common import *

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
    else:
        ssh_target = f"{recvHostUser}@{recvHost}" if recvHostUser else recvHost
        ssh_port_flag = f" -p {recvSshPort}" if str(recvSshPort) != "22" else ""
        print(f"CLI command: {send_str} | ssh{ssh_port_flag} {ssh_target} {recv_flags}")

    process_send = subprocess.Popen(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if transferMethod == "local" or not recvHost:
        recv_cmd = ["zfs", "recv", "-s"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(recvName)
        process_recv = subprocess.Popen(
            recv_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

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
        process_send.wait()

        try:
            recv_stdout, recv_stderr = process_recv.communicate(timeout=PIPELINE_FINALIZE_TIMEOUT)
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
            _, nc_stderr = process_nc.communicate(timeout=PIPELINE_FINALIZE_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_procs(process_nc, ssh_process_listener)
            notifier.notify("STATUS=Finalization timed out — netcat process killed.")
            return False, f"Netcat did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed."

        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        mbuf_stderr = process_mbuffer.stderr.read().decode(errors="replace") if process_mbuffer.stderr else ""

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat resume send failed.")
            print(f"[Sender Side] nc error: {nc_stderr.decode(errors='replace')}")
            if mbuf_stderr:
                print(f"[Sender Side] mbuffer error: {mbuf_stderr}")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            ssh_process_listener.terminate()
            err_msg = "Netcat resume send failed."
            return False, err_msg

        ssh_stdout, ssh_stderr = ssh_process_listener.communicate(timeout=300)
        if ssh_process_listener.returncode != 0:
            notifier.notify("STATUS=Remote resume receive via netcat failed.")
            err_msg = f"[Receiver Side] Error during receive: {ssh_stderr.strip()}"
            print(err_msg)
            return False, err_msg

        notifier.notify("STATUS=Netcat resume send/receive completed.")
        if ssh_stdout:
            print(ssh_stdout)
        return True, ""

    if transferMethod != "ssh":
        print("ERROR: Resume tokens are only supported for local, ssh, or netcat transfers in this script.")
        return False, "Resume tokens are only supported for local, ssh, or netcat transfers in this script."

    m_buff_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    recv_args = ["zfs", "recv", "-s"]
    if forceOverwrite:
        recv_args.append("-F")
    recv_args.append(recvName)
    process_remote_recv = ssh_popen_args(
        recvHostUser,
        recvHost,
        recvSshPort,
        recv_args,
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
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
    process_send.wait()
    process_m_buff.wait()

    try:
        stdout, stderr = process_remote_recv.communicate(timeout=PIPELINE_FINALIZE_TIMEOUT)
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
):
    notifier.notify("STATUS=Resuming ZFS pull pipeline from resume token…")

    if not remoteHost:
        raise RuntimeError("Pull replication requires a remote host.")

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
    if transferMethod == "netcat":
        data_port_cli = str(recvDataPort or remoteSshPort or "31337")
        print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str_cli} | nc -l {data_port_cli}'")
        print(f"CLI command (dest):   nc {remoteHost} {data_port_cli} | {recv_flags}")
    else:
        print(f"CLI command: ssh{ssh_port_flag} {remoteUser}@{remoteHost} {send_str_cli} | {recv_flags}")

    if transferMethod == "netcat":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        ssh_port = str(remoteSshPort or "22")

        notifier.notify(f"STATUS=Resuming pull via netcat from {remoteUser}@{remoteHost} into {localRecvFs}…")

        # Remote: zfs send -t <token> | nc -l <port>
        send_str = f"zfs send -t {shlex.quote(resume_token)}"
        nc_listen = build_nc_listen_cmd(data_port, remoteUser, remoteHost, ssh_port, bind_address=NC_BIND_ADDRESS, send_only=True)
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
            pv_cmd = ["pv", "-f", "-b", "-r", "-t"]
            if total_bytes:
                pv_cmd.extend(["-s", str(total_bytes)])
            process_pv = subprocess.Popen(
                pv_cmd,
                stdin=process_nc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _close_pipe(process_nc.stdout)
            pv_source = process_pv.stdout

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

        process_local_recv = subprocess.Popen(
            recv_cmd,
            stdin=process_mbuffer.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _close_pipe(process_mbuffer.stdout)

        # Wait for pipeline with stall detection
        _stall_timeout = stall_timeout or TRANSFER_STALL_TIMEOUT
        _stall_enabled = bool(_stall_timeout and _stall_timeout > 0)
        _poll = min(30.0, _stall_timeout) if _stall_enabled else None

        while True:
            try:
                recv_stdout, recv_stderr = process_local_recv.communicate(timeout=_poll)
                break
            except subprocess.TimeoutExpired:
                if not _stall_enabled:
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

        process_mbuffer.wait()
        if process_pv:
            process_pv.wait()
        _, nc_stderr = process_nc.communicate(timeout=PIPELINE_FINALIZE_TIMEOUT)

        ssh_stdout, ssh_stderr = ssh_process_sender.communicate(timeout=300)

        mbuf_err = mbuf_capture.text()

        if ssh_process_sender.returncode != 0:
            notifier.notify("STATUS=Remote resume send via netcat failed.")
            err_msg = f"[Remote Side] Error during send: {ssh_stderr.strip()}"
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

    # SSH transfer (default)
    process_remote_send = ssh_popen_args(
        remoteUser,
        remoteHost,
        remoteSshPort,
        ["zfs", "send", "-t", resume_token],
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
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
    process_local_recv = subprocess.Popen(
        recv_cmd,
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

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
    process_remote_send.wait()
    process_m_buff.wait()

    try:
        stdout, stderr = process_local_recv.communicate(timeout=PIPELINE_FINALIZE_TIMEOUT)
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

    notifier.notify("STATUS=Pull resume receive completed.")
    if stdout:
        print(stdout)
    return True, ""

    return False, "Resume tokens are only supported for ssh or netcat transfers in this script."
