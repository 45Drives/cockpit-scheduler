"""Push and local ZFS transfer pipelines."""

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


def _start_push_snapshot_replay_monitor(send_name, recv_name, recv_host, recv_ssh_port, recv_host_user, poll_interval=30.0):
    src_fs = _dataset_of_snapshot(send_name)
    if not src_fs:
        return None, None, None

    total_src = _count_local_snapshots(src_fs)
    if recv_host:
        baseline_dst = _count_remote_snapshots(recv_name, recv_host_user, recv_host, recv_ssh_port)
    else:
        baseline_dst = _count_local_snapshots(recv_name)

    total_replay = max(0, total_src - baseline_dst)
    if total_replay <= 0:
        return None, None, None

    state = {"note": "; snapshots replayed 0/{0}".format(total_replay)}
    stop_event = threading.Event()

    def _monitor():
        while not stop_event.is_set():
            try:
                if recv_host:
                    current_dst = _count_remote_snapshots(recv_name, recv_host_user, recv_host, recv_ssh_port)
                else:
                    current_dst = _count_local_snapshots(recv_name)
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

def send_snapshot_push(
    sendName,
    recvName,
    sendName2="",
    compressed=False,
    raw=False,
    recvHost="",
    recvSshPort="22",
    recvHostUser="",
    mBufferSize="1",
    mBufferUnit="G",
    forceOverwrite=False,
    transferMethod="",
    recursive=False,
    recvDataPort=None,
    include_intermediates=None,
):
    notifier.notify("STATUS=Preparing ZFS send/recv pipeline…")

    send_cmd = build_zfs_send_args(
        sendName,
        sendName2,
        recursive=recursive,
        compressed=compressed,
        raw=raw,
        include_intermediates=include_intermediates,
    )

    if sendName2:
        print(f"sending incrementally from {sendName2} -> {sendName} to {recvName}")
    else:
        print(f"sending {sendName} to {recvName}")

    # Print the full CLI-reproducible command for troubleshooting
    send_str = " ".join(shlex.quote(str(a)) for a in send_cmd)
    if transferMethod == "local" or not recvHost:
        recv_flags = "zfs recv -s" + (" -F" if forceOverwrite else "") + f" {recvName}"
        print(f"CLI command: {send_str} | {recv_flags}")
    elif transferMethod == "netcat":
        recv_flags = "zfs recv -s" + (" -F" if forceOverwrite else "") + f" {recvName}"
        print(f"CLI command (sender): {send_str} | nc -l <port>")
        print(f"CLI command (receiver): nc <host> <port> | {recv_flags}")
    else:
        recv_flags = "zfs recv -s" + (" -F" if forceOverwrite else "") + f" {recvName}"
        ssh_target = f"{recvHostUser}@{recvHost}" if recvHostUser else recvHost
        ssh_port_flag = f" -p {recvSshPort}" if str(recvSshPort) != "22" else ""
        print(f"CLI command: {send_str} | ssh{ssh_port_flag} {ssh_target} {recv_flags}")
    dbg(f"send_cmd: {send_str}")

    total_bytes = estimate_send_size(send_cmd)
    if total_bytes is None:
        print("Note: Could not estimate send size; progress will be indeterminate.")

    process_send = subprocess.Popen(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    send_capture = StreamCapture(process_send.stderr)
    dbg(f"PIPE send pid={process_send.pid} cmd={_fmt_cmd(send_cmd)}")
    
    if transferMethod == "local" or not recvHost:
        recv_cmd = ["zfs", "recv", "-s"]
        if forceOverwrite:
            recv_cmd.append("-F")
        recv_cmd.append(recvName)

        process_recv = subprocess.Popen(
            recv_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        recv_capture = StreamCapture(process_recv.stderr)

        if process_send.stdout is None or process_recv.stdin is None:
            raise RuntimeError("Failed to initialize send/recv pipes.")

        replay_note_getter = None
        replay_stop_event = None
        replay_thread = None
        if recursive and not sendName2:
            replay_note_getter, replay_stop_event, replay_thread = _start_push_snapshot_replay_monitor(
                sendName,
                recvName,
                "",
                recvSshPort,
                recvHostUser,
            )

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_send.stdout, process_recv.stdin, total_bytes,
                label="Transferring", stall_timeout=TRANSFER_STALL_TIMEOUT,
                progress_note_getter=replay_note_getter,
            )
        except StallTimeout as e:
            _kill_procs(process_send, process_recv)
            notifier.notify(f"STATUS=Transfer stalled: {e}")
            print(f"ERROR: {e}")
            sys.exit(1)
        finally:
            if replay_stop_event:
                replay_stop_event.set()
            if replay_thread:
                replay_thread.join(timeout=1)
        try:
            _close_pipe(process_recv.stdin)
            process_recv.stdin = None
        except Exception:
            pass

        if pipe_broken:
            try:
                process_recv.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process_recv.terminate()
            recv_stderr = recv_capture.text()
            process_send.terminate()
            notifier.notify("STATUS=Transfer failed — downstream pipe broken.")
            if recv_stderr:
                safe_print(f"ERROR: local recv error: {recv_stderr.strip()}")
            else:
                safe_print("ERROR: Transfer pipe broken. Downstream process (recv) likely died.")
            sys.exit(1)

        notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
        _wait_with_finalize_heartbeat(process_send, "local zfs send", PIPELINE_FINALIZE_TIMEOUT)

        try:
            _recv_stdout_unused, _recv_stderr_unused = _communicate_with_finalize_heartbeat(
                process_recv,
                "local zfs recv",
                PIPELINE_FINALIZE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            process_recv.kill()
            notifier.notify("STATUS=Finalization timed out — recv process killed.")
            print(f"ERROR: zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed.")
            sys.exit(1)
        send_stderr = send_capture.text()
        recv_stderr = recv_capture.text()

        if process_send.returncode != 0:
            notifier.notify("STATUS=Local send failed.")
            if send_stderr:
                print(f"send error: {send_stderr}")
            sys.exit(1)

        if process_recv.returncode != 0:
            notifier.notify("STATUS=Local receive failed.")
            print(f"recv error: {recv_stderr}")
            sys.exit(1)

        notifier.notify("STATUS=Local receive completed.")
        return

    if transferMethod == "ssh":
        notifier.notify(f"STATUS=Sending snapshot {sendName} to {recvHostUser}@{recvHost}:{recvName} via ssh…")

        replay_note_getter = None
        replay_stop_event = None
        replay_thread = None
        if recursive and not sendName2:
            replay_note_getter, replay_stop_event, replay_thread = _start_push_snapshot_replay_monitor(
                sendName,
                recvName,
                recvHost,
                recvSshPort,
                recvHostUser,
            )

        # --- Direct-pipe path: zfs send -> pv -> mbuffer -> ssh zfs recv ---
        if DIRECT_PIPE_ENABLED and _has_pv():
            dbg("push SSH: using direct-pipe transfer (pv)")

            # Build the remote recv command via SSH
            flags = ["zfs", "recv", "-s"]
            if forceOverwrite:
                flags.append("-F")
            flags.append(recvName)

            # We need mbuffer stdout -> ssh recv.  Build that chain first,
            # then wire process_send -> pv -> mbuffer.
            m_buff_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)

            # For push, the recv side is remote. We build the full pipeline
            # and let _direct_pipe_transfer handle send -> pv -> mbuffer,
            # but we need to pipe mbuffer -> ssh_recv separately.
            # Use a custom approach: pipe process_send through pv+mbuffer,
            # then ssh recv reads from mbuffer stdout.

            pv_cmd = ["pv", "-f", "-b", "-r", "-t"]
            if total_bytes:
                pv_cmd.extend(["-s", str(total_bytes)])

            process_pv = subprocess.Popen(
                pv_cmd,
                stdin=process_send.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _close_pipe(process_send.stdout)

            process_m_buff = subprocess.Popen(
                m_buff_cmd,
                stdin=process_pv.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            mbuf_capture = StreamCapture(process_m_buff.stderr)
            _close_pipe(process_pv.stdout)

            process_remote_recv = ssh_popen_args(
                recvHostUser, recvHost, recvSshPort, flags,
                stdin=process_m_buff.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
            )
            _close_pipe(process_m_buff.stdout)

            dbg(f"direct_pipe push: pv pid={process_pv.pid} mbuffer pid={process_m_buff.pid} recv pid={process_remote_recv.pid}")

            # Shared mutable timestamp for stall detection
            last_activity = [time.time()]

            # Monitor pv in a thread (with stall tracking)
            pv_thread = threading.Thread(
                target=_pv_monitor_thread,
                args=(process_pv.stderr, total_bytes, "Transferring", notifier, last_activity),
                daemon=True,
            )
            pv_thread.start()

            notifier.notify("STATUS=Transferring… pipeline running (direct pipe)")

            # Wait for pipeline with stall detection watchdog
            stall_timeout = TRANSFER_STALL_TIMEOUT
            stall_enabled = bool(stall_timeout and stall_timeout > 0)
            poll_interval = min(30.0, stall_timeout) if stall_enabled else None

            try:
                while True:
                    try:
                        stdout, stderr = process_remote_recv.communicate(timeout=poll_interval)
                        break
                    except subprocess.TimeoutExpired:
                        if not stall_enabled:
                            continue
                        idle = time.time() - last_activity[0]
                        if idle >= stall_timeout:
                            dbg(f"direct_pipe push: STALL detected — no pv activity for {int(idle)}s, killing pipeline")
                            notifier.notify(f"STATUS=Transfer stalled — no data flow for {int(idle)}s, aborting.")
                            for p in [process_pv, process_m_buff, process_remote_recv, process_send]:
                                try:
                                    p.kill()
                                except Exception:
                                    pass
                            print(f"ERROR: Pipeline stalled: no data transferred for {int(idle)}s "
                                  f"(stall timeout: {stall_timeout}s). Check destination pool health.")
                            sys.exit(1)
                        else:
                            dbg(f"direct_pipe push: watchdog check — last activity {int(idle)}s ago (timeout {stall_timeout}s)")
                            continue
                stdout = stdout.decode(errors="replace") if stdout else ""
                stderr = stderr.decode(errors="replace") if stderr else ""

                notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
                _wait_with_finalize_heartbeat(process_m_buff, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)
                _wait_with_finalize_heartbeat(process_pv, "pv monitor", PIPELINE_FINALIZE_TIMEOUT)
                _wait_with_finalize_heartbeat(process_send, "zfs send", PIPELINE_FINALIZE_TIMEOUT)
            finally:
                if replay_stop_event:
                    replay_stop_event.set()
                if replay_thread:
                    replay_thread.join(timeout=1)

            send_stderr = ""
            if process_send.stderr:
                try:
                    send_stderr = process_send.stderr.read().decode(errors="replace")
                except Exception:
                    pass

            if process_send.returncode != 0:
                notifier.notify("STATUS=Remote send failed.")
                if send_stderr:
                    print(f"[Sender Side] zfs send error: {send_stderr}")
                sys.exit(1)

            if process_remote_recv.returncode != 0:
                notifier.notify("STATUS=Remote receive failed.")
                print(f"ERROR: remote recv error: {stderr}")
                sys.exit(1)

            mbuf_err = mbuf_capture.text()
            if process_m_buff.returncode != 0:
                notifier.notify("STATUS=Remote receive failed.")
                if mbuf_err:
                    print(f"[Sender Side] mbuffer error: {mbuf_err}")
                sys.exit(1)

            notifier.notify("STATUS=Remote receive completed (direct pipe).")
            if stdout:
                print(stdout)
            return

        # --- Standard path: Python copy loop ---
        # The copy loop sits downstream of mbuffer so measured bytes are the ones
        # actually handed to ssh, not the ones absorbed by mbuffer's RAM buffer.
        m_buff_cmd = _build_mbuffer_cmd(mBufferSize, mBufferUnit)
        process_m_buff = subprocess.Popen(
            m_buff_cmd,
            stdin=process_send.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mbuf_capture = StreamCapture(process_m_buff.stderr)
        # Close parent's copy so EOF propagates from send to mbuffer
        _close_pipe(process_send.stdout)

        flags = ["zfs", "recv", "-s"]
        if forceOverwrite:
            flags.append("-F")
        flags.append(recvName)

        process_remote_recv = ssh_popen_args(
            recvHostUser,
            recvHost,
            recvSshPort,
            flags,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
        )
        dbg(f"PIPE mbuffer pid={process_m_buff.pid} cmd={_fmt_cmd(m_buff_cmd)}")
        dbg(f"PIPE remote_recv pid={process_remote_recv.pid} recv={recvHostUser}@{recvHost}:{recvName} port={recvSshPort}")

        if process_m_buff.stdout is None or process_remote_recv.stdin is None:
            raise RuntimeError("Failed to initialize mbuffer/recv pipes.")

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_m_buff.stdout, process_remote_recv.stdin, total_bytes,
                label="Transferring", stall_timeout=TRANSFER_STALL_TIMEOUT,
                progress_note_getter=replay_note_getter,
            )
        except StallTimeout as e:
            _kill_procs(process_send, process_m_buff, process_remote_recv)
            notifier.notify(f"STATUS=Transfer stalled: {e}")
            print(f"ERROR: {e}")
            sys.exit(1)
        finally:
            if replay_stop_event:
                replay_stop_event.set()
            if replay_thread:
                replay_thread.join(timeout=1)
        try:
            _close_pipe(process_remote_recv.stdin)
            # Detach so communicate() below does not flush a closed pipe
            process_remote_recv.stdin = None
        except Exception:
            pass

        if pipe_broken:
            try:
                process_remote_recv.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process_remote_recv.terminate()
            recv_stderr = ""
            try:
                recv_stderr = process_remote_recv.stderr.read().decode(errors="replace") if process_remote_recv.stderr else ""
            except Exception:
                pass
            process_send.terminate()
            process_m_buff.terminate()
            notifier.notify("STATUS=Transfer failed — downstream pipe broken.")
            if recv_stderr:
                safe_print(f"ERROR: remote recv error: {recv_stderr.strip()}")
            else:
                safe_print("ERROR: Transfer pipe broken. Downstream process (recv) likely died.")
            sys.exit(1)

        notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        _wait_with_finalize_heartbeat(process_send, "zfs send", PIPELINE_FINALIZE_TIMEOUT)
        _wait_with_finalize_heartbeat(process_m_buff, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)

        try:
            stdout, stderr = _communicate_with_finalize_heartbeat(
                process_remote_recv,
                "remote zfs recv",
                PIPELINE_FINALIZE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            process_remote_recv.kill()
            notifier.notify("STATUS=Finalization timed out — remote recv process killed.")
            print(f"ERROR: Remote zfs recv did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed.")
            sys.exit(1)
        stdout = stdout.decode(errors="replace") if stdout else ""
        stderr = stderr.decode(errors="replace") if stderr else ""

        mbuf_err = mbuf_capture.text()

        if process_send.returncode != 0:
            notifier.notify("STATUS=Remote send failed.")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            sys.exit(1)

        if process_m_buff.returncode != 0:
            notifier.notify("STATUS=Remote receive failed.")
            if mbuf_err:
                print(f"[Sender Side] mbuffer error: {mbuf_err}")
            sys.exit(1)

        if process_remote_recv.returncode != 0:
            notifier.notify("STATUS=Remote receive failed.")
            print(f"ERROR: remote recv error: {stderr}")
            sys.exit(1)

        notifier.notify("STATUS=Remote receive completed.")
        if stdout:
            print(stdout)
        return

    if transferMethod == "netcat":
        data_port = str(recvDataPort or recvSshPort or "31337")
        ssh_port = str(recvSshPort or "22")

        notifier.notify(f"STATUS=Sending snapshot {sendName} via netcat to {recvHostUser}@{recvHost}:{recvName}…")

        replay_note_getter = None
        replay_stop_event = None
        replay_thread = None
        if recursive and not sendName2:
            replay_note_getter, replay_stop_event, replay_thread = _start_push_snapshot_replay_monitor(
                sendName,
                recvName,
                recvHost,
                recvSshPort,
                recvHostUser,
            )

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
        nc_cmd = _build_nc_connect_cmd(recvHost, data_port, recv_only=False)

        # Copy loop sits downstream of mbuffer so progress tracks bytes actually
        # pushed into netcat rather than bytes absorbed by mbuffer's RAM buffer.
        process_mbuffer = subprocess.Popen(
            mbuffer_cmd,
            stdin=process_send.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mbuf_capture = StreamCapture(process_mbuffer.stderr)
        # Close parent's copy so EOF propagates from send to mbuffer
        _close_pipe(process_send.stdout)
        process_nc = subprocess.Popen(
            nc_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if process_mbuffer.stdout is None or process_nc.stdin is None:
            raise RuntimeError("Failed to initialize mbuffer/netcat pipes.")

        try:
            _, pipe_broken = stream_with_progress_stall(
                process_mbuffer.stdout, process_nc.stdin, total_bytes,
                label="Transferring", stall_timeout=TRANSFER_STALL_TIMEOUT,
                progress_note_getter=replay_note_getter,
            )
        except StallTimeout as e:
            _kill_procs(process_send, process_mbuffer, process_nc, ssh_process_listener)
            notifier.notify(f"STATUS=Transfer stalled: {e}")
            print(f"ERROR: {e}")
            sys.exit(1)
        finally:
            if replay_stop_event:
                replay_stop_event.set()
            if replay_thread:
                replay_thread.join(timeout=1)
        try:
            _close_pipe(process_nc.stdin)
            # Detach so communicate() below does not flush a closed pipe
            process_nc.stdin = None
        except Exception:
            pass

        if pipe_broken:
            # In netcat push, recv runs on remote via SSH — try to get its stderr
            try:
                ssh_process_listener.wait(timeout=3)
            except subprocess.TimeoutExpired:
                ssh_process_listener.terminate()
            recv_stderr = ""
            try:
                recv_stderr = ssh_process_listener.stderr.read().decode(errors="replace") if ssh_process_listener.stderr else ""
            except Exception:
                pass
            process_send.terminate()
            process_mbuffer.terminate()
            process_nc.terminate()
            notifier.notify("STATUS=Transfer failed — downstream pipe broken.")
            if recv_stderr:
                safe_print(f"ERROR: remote recv error: {recv_stderr.strip()}")
            else:
                safe_print("ERROR: Transfer pipe broken. Downstream process (recv) likely died.")
            sys.exit(1)

        notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
        send_stderr = process_send.stderr.read().decode(errors="replace") if process_send.stderr else ""
        _wait_with_finalize_heartbeat(process_send, "zfs send", PIPELINE_FINALIZE_TIMEOUT)
        _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)

        try:
            _, nc_stderr = _communicate_with_finalize_heartbeat(
                process_nc,
                "netcat sender",
                PIPELINE_FINALIZE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            process_nc.kill()
            ssh_process_listener.terminate()
            notifier.notify("STATUS=Finalization timed out — netcat process killed.")
            print(f"ERROR: Netcat did not finish within {PIPELINE_FINALIZE_TIMEOUT}s after all data was sent. Process killed.")
            sys.exit(1)

        mbuf_stderr = mbuf_capture.text()

        if process_send.returncode != 0:
            notifier.notify("STATUS=Netcat send failed.")
            if send_stderr:
                print(f"[Sender Side] zfs send error: {send_stderr}")
            ssh_process_listener.terminate()
            sys.exit(1)

        if process_mbuffer.returncode != 0:
            notifier.notify("STATUS=Netcat send failed.")
            if mbuf_stderr:
                print(f"[Sender Side] mbuffer error: {mbuf_stderr}")
            ssh_process_listener.terminate()
            sys.exit(1)

        if process_nc.returncode != 0:
            notifier.notify("STATUS=Netcat send failed.")
            print(f"[Sender Side] nc error: {nc_stderr.decode(errors='replace')}")
            ssh_process_listener.terminate()
            sys.exit(1)

        ssh_stdout, ssh_stderr = ssh_process_listener.communicate(timeout=300)
        if ssh_process_listener.returncode != 0:
            notifier.notify("STATUS=Remote receive via netcat failed.")
            print(f"[Receiver Side] Error during receive: {ssh_stderr.strip()}")
            sys.exit(1)

        notifier.notify("STATUS=Netcat send/receive completed.")

        snapshot_process = ssh_run_args(
            recvHostUser,
            recvHost,
            ssh_port,
            ["zfs", "list", recvName],
            capture_output=True,
            check=False,
            text=True,
        )
        if snapshot_process.returncode != 0:
            err = (snapshot_process.stderr or snapshot_process.stdout or "").strip()
            print(f"[Receiver Side] Error checking dataset: {err}")
            sys.exit(1)

        return

    print("ERROR: Invalid transferMethod specified. Must be 'local', 'ssh', or 'netcat'.")
    sys.exit(1)
