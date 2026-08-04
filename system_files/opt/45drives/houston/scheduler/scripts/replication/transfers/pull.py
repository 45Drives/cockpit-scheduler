"""Pull ZFS transfer pipelines."""

import shlex
import subprocess
import sys
import threading
import time

from .common import *

def send_snapshot_pull(
    remoteSnapName,
    localRecvFs,
    remoteBaseSnapName="",
    compressed=False,
    raw=False,
    remoteHost="",
    remoteSshPort="22",
    remoteUser="root",
    mBufferSize="1",
    mBufferUnit="G",
    forceOverwrite=False,
    recursive=False,
    transferMethod="ssh",
    recvDataPort=None,
    include_intermediates=None,
):
    notifier.notify("STATUS=Preparing ZFS pull pipeline…")

    if not remoteHost:
        raise RuntimeError("Pull replication requires a remote host.")

    remote_send_args = build_zfs_send_args(
        remoteSnapName,
        remoteBaseSnapName,
        recursive=recursive,
        compressed=compressed,
        raw=raw,
        include_intermediates=include_intermediates,
    )

    total_bytes = estimate_send_size_remote(remoteUser, remoteHost, remoteSshPort, remote_send_args)
    if total_bytes is None:
        print("Note: Could not estimate send size; progress will be indeterminate.")

    if remoteBaseSnapName:
        print(f"pulling incrementally from {remoteBaseSnapName} -> {remoteSnapName} into {localRecvFs}")
    else:
        print(f"pulling {remoteSnapName} into {localRecvFs}")

    # Print the full CLI-reproducible command for troubleshooting
    send_str = " ".join(shlex.quote(str(a)) for a in remote_send_args)
    recv_flags = "zfs recv -s" + (" -F" if forceOverwrite else "") + f" {localRecvFs}"
    ssh_port_flag = f" -p {remoteSshPort}" if str(remoteSshPort) != "22" else ""
    if transferMethod == "netcat":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str} | nc -l {data_port}'")
        print(f"CLI command (dest):   nc {remoteHost} {data_port} | {recv_flags}")
    else:
        print(f"CLI command: ssh{ssh_port_flag} {remoteUser}@{remoteHost} {send_str} | {recv_flags}")
    dbg(f"send_cmd: {send_str}")

    if transferMethod == "netcat":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        ssh_port = str(remoteSshPort or "22")

        notifier.notify(f"STATUS=Pulling snapshot {remoteSnapName} via netcat from {remoteUser}@{remoteHost} into {localRecvFs}…")

        # Build the remote command: zfs send | nc -l <port>
        remote_send_str = " ".join(shlex.quote(str(a)) for a in remote_send_args)
        nc_listen = build_nc_listen_cmd(data_port, remoteUser, remoteHost, ssh_port, bind_address=NC_BIND_ADDRESS, send_only=True)
        remote_cmd = f"{remote_send_str} | {nc_listen}"
        ssh_cmd_sender = ssh_base_args(remoteUser, remoteHost, ssh_port)
        ssh_cmd_sender.append(remote_cmd)

        # Start remote zfs send | nc -l via SSH
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

        # Insert pv for progress monitoring on pull
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
        # Close parent's copy so SIGPIPE propagates
        if process_pv:
            _close_pipe(process_pv.stdout)
        else:
            _close_pipe(process_nc.stdout)

        # Start pv progress monitor thread (with stall tracking)
        last_activity = [time.time()]
        if process_pv:
            pv_thread = threading.Thread(
                target=_pv_monitor_thread,
                args=(process_pv.stderr, total_bytes, "Transferring", notifier, last_activity),
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
        # Close parent's copy so SIGPIPE propagates
        _close_pipe(process_mbuffer.stdout)

        # Wait for the pipeline with stall detection
        notifier.notify("STATUS=Receiving data via netcat… waiting for pipeline to complete.")
        stall_timeout = TRANSFER_STALL_TIMEOUT
        stall_enabled = bool(stall_timeout and stall_timeout > 0)
        poll_interval = min(30.0, stall_timeout) if stall_enabled else None

        while True:
            try:
                recv_stdout, recv_stderr = process_local_recv.communicate(timeout=poll_interval)
                break
            except subprocess.TimeoutExpired:
                if not stall_enabled:
                    continue
                idle = time.time() - last_activity[0]
                if idle >= stall_timeout:
                    dbg(f"netcat pull: STALL detected — no pv activity for {int(idle)}s, killing pipeline")
                    notifier.notify(f"STATUS=Transfer stalled — no data flow for {int(idle)}s, aborting.")
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
                    print(f"ERROR: Pipeline stalled: no data transferred for {int(idle)}s "
                          f"(stall timeout: {stall_timeout}s).")
                    sys.exit(1)
                else:
                    dbg(f"netcat pull: watchdog check — last activity {int(idle)}s ago (timeout {stall_timeout}s)")
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
            notifier.notify("STATUS=Remote send via netcat failed.")
            print(f"[Remote Side] Error during send: {ssh_stderr.strip()}")
            sys.exit(1)

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat pull failed.")
            print(f"[Receiver Side] nc error: {nc_stderr.decode(errors='replace') if isinstance(nc_stderr, bytes) else nc_stderr}")
            sys.exit(1)

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=Netcat pull failed.")
            if mbuf_err:
                print(f"[Receiver Side] mbuffer error: {mbuf_err}")
            sys.exit(1)

        if process_local_recv.returncode != 0:
            notifier.notify("STATUS=Local receive (pull via netcat) failed.")
            print(f"ERROR: local recv error: {recv_stderr}")
            sys.exit(1)

        notifier.notify("STATUS=Netcat pull receive completed.")
        if recv_stdout:
            print(recv_stdout)
        return

    # SSH transfer (default)
    process_remote_send = ssh_popen_args(
        remoteUser,
        remoteHost,
        remoteSshPort,
        remote_send_args,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    )

    # --- Direct-pipe path: SSH stdout -> pv -> mbuffer -> zfs recv (no Python copy) ---
    if DIRECT_PIPE_ENABLED and _has_pv():
        dbg("pull SSH: using direct-pipe transfer (pv)")
        m_buff_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
        recv_cmd = ["zfs", "recv", "-s"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(localRecvFs)

        ok, err_msg = _direct_pipe_transfer(
            process_remote_send, m_buff_cmd, recv_cmd, total_bytes,
            label="Transferring",
        )
        if not ok:
            notifier.notify("STATUS=Local receive (pull) failed.")
            print(f"ERROR: {err_msg}")
            sys.exit(1)
        return

    # --- Standard path: Python copy loop SSH -> mbuffer -> recv ---
    m_buff_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
    process_m_buff = subprocess.Popen(
        m_buff_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    mbuf_capture = StreamCapture(process_m_buff.stderr)

    recv_cmd = ["zfs", "recv", "-s"]
    if forceOverwrite:
        recv_cmd.append("-F")
    recv_cmd.append(localRecvFs)

    process_local_recv = subprocess.Popen(
        recv_cmd,
        stdin=process_m_buff.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Close parent's copy so SIGPIPE propagates if recv dies
    _close_pipe(process_m_buff.stdout)

    if process_remote_send.stdout is None or process_m_buff.stdin is None:
        raise RuntimeError("Failed to initialize send/mbuffer pipes.")

    try:
        _, pipe_broken = stream_with_progress_stall(
            process_remote_send.stdout, process_m_buff.stdin, total_bytes,
            label="Transferring", stall_timeout=TRANSFER_STALL_TIMEOUT,
        )
    except StallTimeout as e:
        _kill_procs(process_remote_send, process_m_buff, process_local_recv)
        notifier.notify(f"STATUS=Transfer stalled: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)
    try:
        _close_pipe(process_m_buff.stdin)
    except Exception:
        pass

    if pipe_broken:
        # Give recv a moment to flush its stderr before we kill it
        try:
            process_local_recv.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process_local_recv.terminate()
        recv_stderr = ""
        try:
            recv_stderr = process_local_recv.stderr.read().decode(errors="replace") if process_local_recv.stderr else ""
        except Exception:
            pass
        process_remote_send.terminate()
        process_m_buff.terminate()
        notifier.notify("STATUS=Transfer failed — downstream pipe broken.")
        if recv_stderr:
            safe_print(f"ERROR: local recv error: {recv_stderr.strip()}")
        else:
            safe_print("ERROR: Transfer pipe broken. Downstream process (recv) likely died.")
        sys.exit(1)

    # Wait for send -> mbuffer -> recv chain to settle
    notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
    try:
        remote_out, remote_err = process_remote_send.communicate(timeout=PIPELINE_FINALIZE_TIMEOUT)
    except subprocess.TimeoutExpired:
        process_remote_send.kill()
        process_m_buff.kill()
        process_local_recv.kill()
        notifier.notify("STATUS=Finalization timed out — remote send process killed.")
        print(f"ERROR: Remote zfs send did not finish within {PIPELINE_FINALIZE_TIMEOUT}s. Process killed.")
        sys.exit(1)
    remote_err = remote_err.decode(errors="replace") if remote_err else ""
    process_m_buff.wait()

    try:
        stdout, stderr = process_local_recv.communicate(timeout=PIPELINE_FINALIZE_TIMEOUT)
    except subprocess.TimeoutExpired:
        process_local_recv.kill()
        notifier.notify("STATUS=Finalization timed out — local recv process killed.")
        print(f"ERROR: Local zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed.")
        sys.exit(1)
    stdout = stdout.decode(errors="replace") if stdout else ""
    stderr = stderr.decode(errors="replace") if stderr else ""

    if process_remote_send.returncode != 0:
        notifier.notify("STATUS=Local receive (pull) failed.")
        if remote_err:
            print(f"[Remote zfs send stderr]\n{remote_err}")
        sys.exit(1)

    mbuf_err = mbuf_capture.text()
    if process_m_buff.returncode != 0:
        notifier.notify("STATUS=Local receive (pull) failed.")
        if mbuf_err:
            print(f"[mbuffer stderr]\n{mbuf_err}")
        sys.exit(1)

    if process_local_recv.returncode != 0:
        notifier.notify("STATUS=Local receive (pull) failed.")
        if remote_err:
            print(f"[Remote zfs send stderr]\n{remote_err}")
        print(f"ERROR: local recv error: {stderr}")
        sys.exit(1)

    notifier.notify("STATUS=Pull receive completed.")
    if stdout:
        print(stdout)
    return

    print("ERROR: Invalid transferMethod specified. Must be 'ssh' or 'netcat'.")
    sys.exit(1)
