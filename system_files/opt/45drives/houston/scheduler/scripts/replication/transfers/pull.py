"""Pull ZFS transfer pipelines."""

import shlex
import subprocess
import sys
import threading
import time

from .common import *


def _dataset_of_snapshot(snapshot_name):
    return (snapshot_name or "").split("@", 1)[0]


def _count_local_snapshots(filesystem):
    try:
        p = subprocess.run(
            ["zfs", "list", "-H", "-t", "snapshot", "-o", "name", "-r", filesystem],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            timeout=30,
        )
        if p.returncode != 0:
            return 0
        out = (p.stdout or "").strip()
        if not out:
            return 0
        return len(out.splitlines())
    except Exception:
        return 0


def _count_remote_snapshots(filesystem, remote_user, remote_host, remote_port):
    try:
        p = ssh_run_args(
            remote_user,
            remote_host,
            remote_port,
            ["zfs", "list", "-H", "-t", "snapshot", "-o", "name", "-r", filesystem],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        if p.returncode != 0:
            return 0
        out = (p.stdout or "").strip()
        if not out:
            return 0
        return len(out.splitlines())
    except Exception:
        return 0


def _start_pull_snapshot_replay_monitor(remote_snap_name, local_recv_fs, remote_user, remote_host, remote_ssh_port, poll_interval=30.0):
    src_fs = _dataset_of_snapshot(remote_snap_name)
    if not src_fs:
        return None, None, None

    total_src = _count_remote_snapshots(src_fs, remote_user, remote_host, remote_ssh_port)
    baseline_dst = _count_local_snapshots(local_recv_fs)
    total_replay = max(0, total_src - baseline_dst)
    if total_replay <= 0:
        return None, None, None

    state = {"note": "; snapshots replayed 0/{0}".format(total_replay)}
    stop_event = threading.Event()

    def _monitor():
        while not stop_event.is_set():
            try:
                current_dst = _count_local_snapshots(local_recv_fs)
                applied = max(0, current_dst - baseline_dst)
                if applied > total_replay:
                    applied = total_replay
                state["note"] = "; snapshots replayed {0}/{1}".format(applied, total_replay)
            except Exception:
                pass
            stop_event.wait(poll_interval)

    thread = threading.Thread(target=_monitor, daemon=True)
    thread.start()
    return (lambda: state["note"]), stop_event, thread


def _start_remote_send_over_ssh(
    remote_user,
    remote_host,
    remote_ssh_port,
    remote_send_args,
    remote_mbuffer_enabled,
    m_buffer_size,
    m_buffer_unit,
):
    if not remote_mbuffer_enabled:
        return ssh_popen_args(
            remote_user,
            remote_host,
            remote_ssh_port,
            remote_send_args,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
        )

    remote_send_str = " ".join(shlex.quote(str(a)) for a in remote_send_args)
    remote_cmd = f"{remote_send_str} | {mbuffer_shell_stage(m_buffer_size, m_buffer_unit)}"
    ssh_cmd = ssh_base_args(remote_user, remote_host, remote_ssh_port)
    ssh_cmd.append(remote_cmd)
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
    mbufferCallbackHost="",
):
    notifier.notify("STATUS=Preparing ZFS pull pipeline…")

    if not remoteHost:
        raise RuntimeError("Pull replication requires a remote host.")

    if transferMethod not in ("ssh", "netcat", "mbuffer"):
        notifier.notify("STATUS=Invalid transfer method for pull replication.")
        print(f"ERROR: Invalid transferMethod '{transferMethod}'. Pull replication supports 'ssh', 'netcat', or 'mbuffer'.")
        sys.exit(1)

    remote_mbuffer_enabled = False
    if transferMethod in ("ssh", "netcat"):
        remote_mbuffer_enabled = remote_has_command(remoteUser, remoteHost, remoteSshPort, "mbuffer")
        if remote_mbuffer_enabled:
            msg = f"Remote mbuffer detected on {remoteHost}; enabling two-ended buffering."
            notifier.notify(f"STATUS={msg}")
            print(msg)
        else:
            msg = f"Remote mbuffer not found on {remoteHost}; using local-only buffering."
            notifier.notify(f"STATUS={msg}")
            print(msg)

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

    replay_note_getter = None
    replay_stop_event = None
    replay_thread = None
    if recursive and not remoteBaseSnapName:
        replay_note_getter, replay_stop_event, replay_thread = _start_pull_snapshot_replay_monitor(
            remoteSnapName,
            localRecvFs,
            remoteUser,
            remoteHost,
            remoteSshPort,
        )

    if remoteBaseSnapName:
        print(f"pulling incrementally from {remoteBaseSnapName} -> {remoteSnapName} into {localRecvFs}")
    else:
        print(f"pulling {remoteSnapName} into {localRecvFs}")

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

    # Print the full CLI-reproducible command for troubleshooting
    send_str = " ".join(shlex.quote(str(a)) for a in remote_send_args)
    recv_flags = "zfs recv -s" + (" -F" if forceOverwrite else "") + f" {localRecvFs}"
    ssh_port_flag = f" -p {remoteSshPort}" if str(remoteSshPort) != "22" else ""
    if transferMethod == "netcat":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        local_recv_stage = f"nc {remoteHost} {data_port} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {recv_flags}"
        if remote_mbuffer_enabled:
            print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | nc -l {data_port}'")
        else:
            print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str} | nc -l {data_port}'")
        print(f"CLI command (dest, local receiver):   {local_recv_stage}")
    elif transferMethod == "mbuffer":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        print(f"CLI command (source): ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -O {mbuffer_callback_cli}'")
        print(f"CLI command (dest, local receiver):   {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -I {data_port} | {recv_flags}")
    else:
        if remote_mbuffer_enabled:
            print(f"CLI command: ssh{ssh_port_flag} {remoteUser}@{remoteHost} '{send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)}' | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {recv_flags}")
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
        if remote_mbuffer_enabled:
            remote_cmd = f"{remote_send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} | {nc_listen}"
        else:
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
                "are disabled for this netcat transfer."
            )

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
        # pv is the only activity source for this pipeline; without it every poll looks idle.
        stall_enabled = bool(process_pv and stall_timeout and stall_timeout > 0)
        poll_interval = min(30.0, stall_timeout) if stall_enabled else 60.0

        while True:
            try:
                recv_stdout, recv_stderr = safe_communicate(process_local_recv, timeout=poll_interval)
                break
            except subprocess.TimeoutExpired:
                if not stall_enabled:
                    notifier.notify("STATUS=Receiving data via netcat… still running (no pv, progress unavailable).")
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

        notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
        try:
            _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)
            if process_pv:
                _wait_with_finalize_heartbeat(process_pv, "pv monitor", PIPELINE_FINALIZE_TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_procs(process_mbuffer, process_pv, process_nc, ssh_process_sender)
            notifier.notify("STATUS=Finalization timed out — buffer stage killed.")
            print(f"ERROR: mbuffer/pv did not drain within {PIPELINE_FINALIZE_TIMEOUT}s after the receive completed. Processes killed.")
            sys.exit(1)
        try:
            _, nc_stderr = _communicate_with_finalize_heartbeat(
                process_nc,
                "netcat receiver",
                PIPELINE_FINALIZE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            process_nc.kill()
            ssh_process_sender.terminate()
            notifier.notify("STATUS=Finalization timed out — netcat receiver process killed.")
            print(f"ERROR: netcat receiver did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was received. Process killed.")
            sys.exit(1)

        try:
            ssh_stdout, ssh_stderr = _communicate_with_finalize_heartbeat(
                ssh_process_sender,
                "remote netcat sender",
                300,
            )
        except subprocess.TimeoutExpired:
            ssh_process_sender.kill()
            notifier.notify("STATUS=Finalization timed out — remote sender process killed.")
            print("ERROR: Remote sender did not finish during netcat pull finalization. Process killed.")
            sys.exit(1)

        if isinstance(nc_stderr, bytes):
            nc_stderr = nc_stderr.decode(errors="replace")
        if isinstance(ssh_stdout, bytes):
            ssh_stdout = ssh_stdout.decode(errors="replace")
        if isinstance(ssh_stderr, bytes):
            ssh_stderr = ssh_stderr.decode(errors="replace")

        mbuf_err = mbuf_capture.text()

        if ssh_process_sender.returncode != 0:
            notifier.notify("STATUS=Remote send via netcat failed.")
            print(f"[Remote Side] Error during send: {ssh_stderr.strip()}")
            sys.exit(1)

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat pull failed.")
            print(f"[Receiver Side] nc error: {nc_stderr}")
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
        if replay_stop_event:
            replay_stop_event.set()
        if replay_thread:
            replay_thread.join(timeout=1)
        return

    if transferMethod == "mbuffer":
        data_port = str(recvDataPort or remoteSshPort or "31337")
        ssh_port = str(remoteSshPort or "22")
        callback_expr = mbuffer_callback_expr
        callback_display = mbuffer_callback_display

        notifier.notify(f"STATUS=Pulling snapshot {remoteSnapName} via mbuffer from {remoteUser}@{remoteHost} into {localRecvFs}…")

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
            print(f"ERROR: Data-plane blocked for mbuffer pull. Source {remoteHost} cannot reach callback host {callback_display}:{data_port}.")
            if preflight_detail:
                print(f"Preflight detail: {preflight_detail}")
            print("Hint: Open firewall/route for callback host:port or set an explicit mBuffer callback host.")
            sys.exit(1)
        if preflight_checked and preflight_detail:
            notifier.notify(f"STATUS=Callback preflight note: {preflight_detail}")
            print(f"Preflight note: {preflight_detail}")
        if not preflight_checked:
            notifier.notify(f"STATUS=Callback preflight skipped ({preflight_detail}).")
            print(f"Warning: {preflight_detail}")

        # Local listener: mbuffer -I <port> | zfs recv
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

        process_local_recv = subprocess.Popen(
            recv_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        notifier.notify(f"STATUS=Listener ready on local port {data_port}; waiting for remote mbuffer callback from {remoteHost} to {callback_display}:{data_port}…")

        # Remote sender connects back to the callback host.
        remote_send_str = " ".join(shlex.quote(str(a)) for a in remote_send_args)
        remote_cmd = f"{remote_send_str} | {mbuffer_shell_stage(mBufferSize, mBufferUnit)} -O {callback_expr}:{shlex.quote(data_port)}"
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
            raise RuntimeError("Failed to initialize mbuffer pull pipes.")

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_mbuffer.stdout,
                process_local_recv.stdin,
                total_bytes,
                label="Transferring",
                stall_timeout=TRANSFER_STALL_TIMEOUT,
                progress_note_getter=replay_note_getter,
            )
        except StallTimeout as e:
            _kill_procs(process_mbuffer, process_local_recv, ssh_process_sender)
            notifier.notify(f"STATUS=Transfer stalled: {e}")
            print(f"ERROR: {e}")
            sys.exit(1)
        finally:
            if replay_stop_event:
                replay_stop_event.set()
            if replay_thread:
                replay_thread.join(timeout=1)

        try:
            _close_pipe(process_local_recv.stdin)
            process_local_recv.stdin = None
        except Exception:
            pass

        if pipe_broken:
            _kill_procs(process_mbuffer, process_local_recv, ssh_process_sender)
            notifier.notify("STATUS=Transfer failed — downstream pipe broken.")
            safe_print("ERROR: Transfer pipe broken. Downstream process (recv) likely died.")
            sys.exit(1)

        notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
        _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer listener", PIPELINE_FINALIZE_TIMEOUT)

        try:
            recv_stdout, recv_stderr = _communicate_with_finalize_heartbeat(
                process_local_recv,
                "local zfs recv",
                PIPELINE_FINALIZE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            process_local_recv.kill()
            ssh_process_sender.kill()
            notifier.notify("STATUS=Finalization timed out — local recv process killed.")
            print(f"ERROR: Local zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was received. Process killed.")
            sys.exit(1)

        try:
            ssh_stdout, ssh_stderr = _communicate_with_finalize_heartbeat(
                ssh_process_sender,
                "remote mbuffer sender",
                300,
            )
        except subprocess.TimeoutExpired:
            ssh_process_sender.kill()
            notifier.notify("STATUS=Finalization timed out — remote sender process killed.")
            print("ERROR: Remote sender did not finish during mbuffer pull finalization. Process killed.")
            sys.exit(1)

        recv_stdout = recv_stdout.decode(errors="replace") if isinstance(recv_stdout, bytes) else (recv_stdout or "")
        recv_stderr = recv_stderr.decode(errors="replace") if isinstance(recv_stderr, bytes) else (recv_stderr or "")
        ssh_stdout = ssh_stdout.decode(errors="replace") if isinstance(ssh_stdout, bytes) else (ssh_stdout or "")
        ssh_stderr = ssh_stderr.decode(errors="replace") if isinstance(ssh_stderr, bytes) else (ssh_stderr or "")

        mbuf_err = mbuf_capture.text()

        if ssh_process_sender.returncode != 0:
            notifier.notify("STATUS=Remote send via mbuffer failed.")
            print(f"[Remote Side] Error during send: {ssh_stderr.strip()}")
            sys.exit(1)

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=mBuffer pull failed.")
            if mbuf_err:
                print(f"[Receiver Side] mbuffer error: {mbuf_err}")
            sys.exit(1)

        if process_local_recv.returncode != 0:
            notifier.notify("STATUS=Local receive (pull via mbuffer) failed.")
            print(f"ERROR: local recv error: {recv_stderr}")
            sys.exit(1)

        notifier.notify("STATUS=mBuffer pull receive completed.")
        if recv_stdout:
            print(recv_stdout)
        if ssh_stdout:
            print(ssh_stdout)
        return

    # SSH transfer (default)
    process_remote_send = _start_remote_send_over_ssh(
        remoteUser,
        remoteHost,
        remoteSshPort,
        remote_send_args,
        remote_mbuffer_enabled,
        mBufferSize,
        mBufferUnit,
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
        if replay_stop_event:
            replay_stop_event.set()
        if replay_thread:
            replay_thread.join(timeout=1)
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
            progress_note_getter=replay_note_getter,
        )
    except StallTimeout as e:
        _kill_procs(process_remote_send, process_m_buff, process_local_recv)
        notifier.notify(f"STATUS=Transfer stalled: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        if replay_stop_event:
            replay_stop_event.set()
        if replay_thread:
            replay_thread.join(timeout=1)
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
        remote_out, remote_err = _communicate_with_finalize_heartbeat(
            process_remote_send,
            "remote zfs send",
            PIPELINE_FINALIZE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        process_remote_send.kill()
        process_m_buff.kill()
        process_local_recv.kill()
        notifier.notify("STATUS=Finalization timed out — remote send process killed.")
        print(f"ERROR: Remote zfs send did not finish within {PIPELINE_FINALIZE_TIMEOUT}s. Process killed.")
        sys.exit(1)
    remote_err = remote_err.decode(errors="replace") if remote_err else ""
    _wait_with_finalize_heartbeat(process_m_buff, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)

    try:
        stdout, stderr = _communicate_with_finalize_heartbeat(
            process_local_recv,
            "local zfs recv",
            PIPELINE_FINALIZE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        process_local_recv.kill()
        notifier.notify("STATUS=Finalization timed out — local recv process killed.")
        print(f"ERROR: Local zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed.")
        sys.exit(1)
    stdout = stdout.decode(errors="replace") if stdout else ""
    stderr = stderr.decode(errors="replace") if stderr else ""

    if replay_stop_event:
        replay_stop_event.set()
    if replay_thread:
        replay_thread.join(timeout=1)

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
    if replay_stop_event:
        replay_stop_event.set()
    if replay_thread:
        replay_thread.join(timeout=1)
    return
