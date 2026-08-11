"""Local process execution and stream-copy helpers."""

import errno
import os
import re
import socket
import subprocess
import threading
import time
from collections import deque

from .config import as_bool
from .constants import MBUFFER_BLOCK_SIZE, PIPELINE_FINALIZE_TIMEOUT
from .context import notifier
from .logging_utils import _fmt_cmd, _truncate, dbg, safe_print


def _close_pipe(pipe):
    """Close an optional subprocess pipe when it was configured."""
    if pipe is not None:
        pipe.close()


class StreamCapture:
    def __init__(self, stream, max_lines=200):
        self._lines = deque(maxlen=max_lines)
        self._stream = stream
        self._thread = None
        if stream is not None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self):
        try:
            for line in iter(self._stream.readline, b""):
                self._lines.append(line)
        except Exception:
            pass

    def text(self) -> str:
        if not self._lines:
            return ""
        return b"".join(self._lines).decode(errors="replace")


class StallTimeout(Exception):
    """Raised when no data flows for longer than the stall timeout."""
    pass


def _parse_send_size_output(raw: bytes):
    """Parse zfs send -nP output and return total estimated bytes.

    For non-recursive sends, looks for a 'size' summary line.
    For recursive (-R) sends, sums the last numeric field of each
    'full' or 'incremental' line.
    """
    total = 0
    found_size_line = False
    for raw_line in raw.split(b"\n"):
        line = raw_line.decode(errors="replace").strip()
        if not line:
            continue
        # Prefer explicit "size" summary line (non-recursive sends)
        if "size" in line.lower():
            m = re.search(r"\bsize\b\s*=?\s*(\d+)", line, re.IGNORECASE)
            if m:
                return int(m.group(1))
        # Sum per-stream sizes for recursive sends
        if line.startswith("full") or line.startswith("incremental"):
            parts = line.split("\t")
            if parts:
                try:
                    total += int(parts[-1])
                    found_size_line = True
                except (ValueError, IndexError):
                    pass
    return total if found_size_line and total > 0 else None


def run_logged(cmd, *, check=False, text=True, timeout=None, env=None):
    """
    Local subprocess.run with debug logging.
    """
    dbg(f"RUN local: {_fmt_cmd(cmd)}")
    start = time.time()
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=text,
        check=False,
        timeout=timeout,
        env=env,
    )
    dur = time.time() - start
    out = p.stdout if p.stdout is not None else ""
    err = p.stderr if p.stderr is not None else ""
    dbg(f"RC local={p.returncode} dur={dur:.2f}s stdout:\n{_truncate(out)}")
    dbg(f"RC local={p.returncode} dur={dur:.2f}s stderr:\n{_truncate(err)}")
    if check and p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, cmd, output=p.stdout, stderr=p.stderr)
    return p


def _effective_mbuffer_block():
    """Resolve mbuffer block size for this run.

    Block-size overrides are only applied when transfer method is standalone
    mbuffer. SSH/netcat methods keep the repository default block size unless
    overridden globally via ZFS_REP_MBUFFER_BLOCK.
    """
    transfer_method = (os.environ.get("zfsRepConfig_sendOptions_transferMethod", "") or "").strip().lower()
    if transfer_method != "mbuffer":
        return MBUFFER_BLOCK_SIZE

    size_raw = (os.environ.get("zfsRepConfig_sendOptions_mbufferBlockSize", "") or "").strip()
    unit_raw = (os.environ.get("zfsRepConfig_sendOptions_mbufferBlockUnit", "") or "").strip()

    try:
        size = int(size_raw or "0")
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return MBUFFER_BLOCK_SIZE

    unit_map = {
        "b": "b",
        "B": "b",
        "k": "k",
        "K": "k",
        "m": "M",
        "M": "M",
        "g": "G",
        "G": "G",
    }
    unit = unit_map.get(unit_raw)
    if not unit:
        return MBUFFER_BLOCK_SIZE

    return f"{size}{unit}"


def _build_mbuffer_cmd(buf_size, buf_unit):
    """Build the mbuffer command list with configurable block size."""
    return ["mbuffer", "-s", _effective_mbuffer_block(), "-m", f"{buf_size}{buf_unit}"]


def _wait_for_port(host, port, timeout=30, interval=0.5):
    """Poll a TCP port until it accepts connections or timeout expires.
    Returns True if connected, False on timeout.
    Used to replace sleep(2) for netcat listener readiness.
    
    IMPORTANT: For remote netcat listeners, use _wait_for_port_remote() instead.
    A local TCP connect probe will CONSUME a single-accept nc -l listener."""
    deadline = time.time() + timeout
    port_int = int(port)
    while time.time() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(min(interval, deadline - time.time()))
            s.connect((host, port_int))
            s.close()
            dbg(f"_wait_for_port: {host}:{port} ready")
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(interval)
        finally:
            try:
                s.close()
            except Exception:
                pass
    dbg(f"_wait_for_port: {host}:{port} timeout after {timeout}s")
    return False


def _apply_tcp_tuning():
    """Apply TCP tuning sysctl values if ZFS_REP_TCP_TUNING=1.
    Only takes effect as root. Logs but does not fail if sysctls cannot be set.
    These are non-destructive runtime changes that revert on reboot."""
    if not as_bool(os.environ.get("ZFS_REP_TCP_TUNING")):
        return

    tunings = {
        "net.core.rmem_max": "67108864",
        "net.core.wmem_max": "67108864",
        "net.ipv4.tcp_rmem": "4096 87380 33554432",
        "net.ipv4.tcp_wmem": "4096 87380 33554432",
    }
    # Optional: set congestion control if specified
    cc = os.environ.get("ZFS_REP_TCP_CC", "").strip()
    if cc:
        tunings["net.ipv4.tcp_congestion_control"] = cc

    for key, val in tunings.items():
        try:
            subprocess.run(
                ["sysctl", "-w", f"{key}={val}"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5,
            )
            dbg(f"tcp_tuning: {key}={val}")
        except Exception as e:
            dbg(f"tcp_tuning: failed to set {key}: {e}")


def _has_pv():
    """Check if pv (pipe viewer) is installed."""
    try:
        p = subprocess.run(["which", "pv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return p.returncode == 0
    except Exception:
        return False


def _pv_monitor_thread(pv_stderr, total_bytes, label, notifier_ref, last_activity=None):
    """Read pv stderr output and emit progress notifications.

    pv redraws a single status line terminated by carriage returns rather than
    newlines, so readline() would block until the process exits. Read bytes and
    split on both \\r and \\n instead.
    If last_activity is provided (a single-element list), update it with time.time()
    on each output line so the caller can detect stalls."""
    last_pct = -1.0
    last_emit = 0.0
    last_dbg = 0.0
    buf = bytearray()
    try:
        while True:
            ch = pv_stderr.read(1)
            if not ch:
                break
            if ch not in (b"\r", b"\n"):
                buf.extend(ch)
                continue

            line = buf.decode(errors="replace").strip()
            buf.clear()
            if not line:
                continue
            now = time.time()
            if last_activity is not None:
                last_activity[0] = now
            # pv outputs percentage in the form " 12%" or "100%"
            m = re.search(r'(\d+)%', line)
            if m:
                pct = float(m.group(1))
                if pct > last_pct and (now - last_emit) >= 1.0:
                    notifier_ref.notify(f"STATUS={label}… {pct:.0f}% complete")
                    last_pct = pct
                    last_emit = now
            # Also log rate info from pv
            if (now - last_dbg) >= 10.0:
                dbg(f"pv {label}: {line}")
                last_dbg = now
    except Exception:
        pass


def _direct_pipe_transfer(src_process, mbuffer_cmd, recv_cmd, total_bytes, label,
                          stderr_captures=None, stall_timeout=3600):
    """Wire src_process.stdout -> pv -> mbuffer -> recv using OS pipes (no Python copy).

    Returns (success: bool, error_msg: str).
    stderr_captures is an optional dict to store StreamCapture objects for the caller.
    stall_timeout: seconds with no pv progress before killing the pipeline (0 to disable).
    """
    if stderr_captures is None:
        stderr_captures = {}

    procs = []
    try:
        # -f is required: pv prints nothing when stderr is not a terminal.
        pv_cmd = ["pv", "-f", "-i", "1", "-b", "-r", "-t"]
        if total_bytes:
            pv_cmd.extend(["-s", str(total_bytes)])

        # Shared mutable timestamp for stall detection (single-element list for thread safety)
        last_activity = [time.time()]

        # Pipeline: src_stdout -> pv -> mbuffer -> recv
        # bufsize=0 disables buffering on stderr so progress lines appear immediately
        process_pv = subprocess.Popen(
            pv_cmd,
            stdin=src_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        procs.append(("pv", process_pv))
        # Close parent's copy so EOF propagates
        _close_pipe(src_process.stdout)

        process_mbuffer = subprocess.Popen(
            mbuffer_cmd,
            stdin=process_pv.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        procs.append(("mbuffer", process_mbuffer))
        stderr_captures["mbuffer"] = StreamCapture(process_mbuffer.stderr)
        _close_pipe(process_pv.stdout)

        process_recv = subprocess.Popen(
            recv_cmd,
            stdin=process_mbuffer.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        procs.append(("recv", process_recv))
        _close_pipe(process_mbuffer.stdout)

        # Monitor pv stderr in a thread for progress + stall tracking
        pv_thread = threading.Thread(
            target=_pv_monitor_thread,
            args=(process_pv.stderr, total_bytes, label, notifier, last_activity),
            daemon=True,
        )
        pv_thread.start()

        notifier.notify(f"STATUS={label}… pipeline running (direct pipe)")
        dbg(f"direct_pipe {label}: pv pid={process_pv.pid} mbuffer pid={process_mbuffer.pid} recv pid={process_recv.pid}")

        # Wait for recv to finish, with stall detection watchdog
        stall_enabled = bool(stall_timeout and stall_timeout > 0)
        poll_interval = min(30.0, stall_timeout) if stall_enabled else None

        while True:
            try:
                recv_stdout, recv_stderr = process_recv.communicate(
                    timeout=poll_interval
                )
                break  # recv finished
            except subprocess.TimeoutExpired:
                if not stall_enabled:
                    continue
                idle = time.time() - last_activity[0]
                if idle >= stall_timeout:
                    dbg(f"direct_pipe {label}: STALL detected — no pv activity for {int(idle)}s, killing pipeline")
                    notifier.notify(f"STATUS={label} stalled — no data flow for {int(idle)}s, aborting.")
                    for name, p in procs:
                        try:
                            p.kill()
                        except Exception:
                            pass
                    try:
                        src_process.kill()
                    except Exception:
                        pass
                    return False, (
                        f"Pipeline stalled: no data transferred for {int(idle)}s "
                        f"(stall timeout: {stall_timeout}s). The transfer may be resumable — "
                        f"check for a resume token with the Resume Transfer button."
                    )
                else:
                    dbg(f"direct_pipe {label}: watchdog check — last activity {int(idle)}s ago (timeout {stall_timeout}s)")
                    continue
        recv_stderr = recv_stderr.decode(errors="replace") if isinstance(recv_stderr, bytes) else (recv_stderr or "")
        recv_stdout = recv_stdout.decode(errors="replace") if isinstance(recv_stdout, bytes) else (recv_stdout or "")

        notifier.notify("STATUS=Finalizing receive… waiting for pipeline to complete.")
        _wait_with_finalize_heartbeat(process_mbuffer, "mbuffer flush", PIPELINE_FINALIZE_TIMEOUT)
        _wait_with_finalize_heartbeat(process_pv, "pv monitor", PIPELINE_FINALIZE_TIMEOUT)
        _wait_with_finalize_heartbeat(src_process, "zfs send", PIPELINE_FINALIZE_TIMEOUT)

        # Check return codes in pipeline order
        src_rc = src_process.returncode
        pv_rc = process_pv.returncode
        mbuf_rc = process_mbuffer.returncode
        recv_rc = process_recv.returncode

        dbg(f"direct_pipe {label}: src_rc={src_rc} pv_rc={pv_rc} mbuf_rc={mbuf_rc} recv_rc={recv_rc}")

        src_stderr = ""
        if src_process.stderr:
            try:
                src_stderr = src_process.stderr.read().decode(errors="replace")
            except Exception:
                pass

        if src_rc != 0:
            return False, f"Source process failed (rc={src_rc}): {src_stderr}"
        if recv_rc != 0:
            return False, f"Receive failed (rc={recv_rc}): {recv_stderr}"
        if mbuf_rc != 0:
            mbuf_err = stderr_captures.get("mbuffer")
            return False, f"mBuffer failed (rc={mbuf_rc}): {mbuf_err.text() if mbuf_err else ''}"
        # pv non-zero is not critical (e.g. SIGPIPE after recv closes)

        notifier.notify(f"STATUS={label} completed (direct pipe).")
        if recv_stdout:
            print(recv_stdout)
        return True, ""

    except Exception as e:
        # Kill everything on unexpected error
        for name, p in procs:
            try:
                p.kill()
            except Exception:
                pass
        try:
            src_process.kill()
        except Exception:
            pass
        return False, f"Direct pipe error: {e}"


def estimate_send_size(send_cmd):
    try:
        cmd = list(send_cmd)
        if len(cmd) < 2 or cmd[0] != "zfs" or cmd[1] != "send":
            return None
        cmd.insert(2, "-nP")
        p = run_logged(cmd, text=False)

        if p.returncode != 0:
            return None
        raw = (p.stdout or b"") + (p.stderr or b"")
        return _parse_send_size_output(raw)
    except Exception:
        return None


def _write_all_stalled(fd, data, stall_timeout, bytes_sent):
    """Write all of data to fd, raising StallTimeout if the pipe stays unwritable.

    The watchdog has to cover the write side too: when the copy loop sits downstream
    of mbuffer, a stalled network blocks in write(), not read().
    """
    import select as _select

    view = memoryview(data)
    sent = 0
    while sent < len(view):
        if stall_timeout:
            waited = 0.0
            poll_interval = min(30.0, stall_timeout)
            while True:
                _, writable, _ = _select.select([], [fd], [], poll_interval)
                if writable:
                    break
                waited += poll_interval
                if waited >= stall_timeout:
                    raise StallTimeout(
                        "Downstream pipe not writable for {0}s (stall timeout: {1}s). "
                        "Transferred {2:.1f} MiB before stall.".format(
                            int(waited), stall_timeout, bytes_sent / (1024 * 1024)
                        )
                    )
        sent += os.write(fd, view[sent:])
    return sent


def stream_with_progress_stall(src, dst, total_bytes, label="Resuming", min_interval=1.0, stall_timeout=3600, progress_note_getter=None):
    """Copy src to dst with progress, raising StallTimeout if no data moves for stall_timeout seconds.
    If stall_timeout is 0 or None, stall detection is disabled.
    Returns (bytes_sent, pipe_broken) tuple."""
    import select as _select

    bytes_sent = 0
    pipe_broken = False
    last_pct = -1.0
    last_emit = 0.0
    last_dbg = 0.0
    last_pct_change = 0.0
    last_liveness_notice = 0.0
    liveness_notice_interval = 45.0
    last_data_time = time.time()
    start_time = last_data_time
    window_bytes = 0
    window_start = start_time
    stall_enabled = bool(stall_timeout and stall_timeout > 0)

    read_size = int(os.environ.get("ZFS_REP_CHUNK_SIZE", str(1024 * 1024)))

    if total_bytes:
        notifier.notify(f"STATUS={label}… 0.0% complete")
        dbg(f"{label} start: estimated_total={total_bytes} ({format_bytes(total_bytes)}) chunk_size={read_size}")
        last_pct_change = start_time
    else:
        notifier.notify(f"STATUS={label}…")
        dbg(f"{label} start: estimated_total=unknown chunk_size={read_size}")

    fd = src.fileno()
    dst_fd = dst.fileno()
    # read1 returns whatever is buffered instead of blocking for a full chunk,
    # which keeps the stall watchdog and the progress bar responsive.
    _read = getattr(src, "read1", None) or src.read

    while True:
        if stall_enabled:
            # Wait for data with a timeout chunk (check every 30s)
            poll_interval = min(30.0, stall_timeout)
            ready, _, _ = _select.select([fd], [], [], poll_interval)
            if not ready:
                elapsed = time.time() - last_data_time
                if elapsed >= stall_timeout:
                    mib = bytes_sent / (1024 * 1024)
                    raise StallTimeout(
                        f"No data received for {int(elapsed)}s (stall timeout: {stall_timeout}s). "
                        f"Transferred {mib:.1f} MiB before stall."
                    )
                continue

        chunk = _read(read_size)
        if not chunk:
            break
        last_data_time = time.time()
        try:
            _write_all_stalled(dst_fd, chunk, stall_timeout if stall_enabled else None, bytes_sent)
        except (BrokenPipeError, ValueError, OSError) as e:
            if isinstance(e, OSError) and not isinstance(e, BrokenPipeError) and e.errno not in (errno.EPIPE, errno.ECONNRESET):
                raise
            safe_print(f"WARNING: {label} pipe broken after {bytes_sent/(1024*1024):.1f} MiB — downstream process likely exited.")
            dbg(f"{label} BrokenPipeError after bytes_sent={bytes_sent}")
            pipe_broken = True
            break
        bytes_sent += len(chunk)
        window_bytes += len(chunk)
        now = time.time()

        if total_bytes:
            # Hold at 99.9% if we overrun the estimate; only EOF means 100%.
            pct = min(round(bytes_sent * 100.0 / total_bytes, 1), 99.9)
            if pct > last_pct and (now - last_emit) >= min_interval:
                notifier.notify(f"STATUS={label}… {pct:.1f}% complete")
                last_pct = pct
                last_emit = now
                last_pct_change = now
            elif pct <= last_pct and (now - last_pct_change) >= liveness_notice_interval and (now - last_liveness_notice) >= liveness_notice_interval:
                # Reassure users during long recursive replay phases where bytes move but rounded % appears unchanged.
                mib = bytes_sent / (1024 * 1024)
                progress_note = ""
                if progress_note_getter:
                    try:
                        progress_note = progress_note_getter() or ""
                    except Exception:
                        progress_note = ""
                if last_pct >= 99.9:
                    notifier.notify(
                        f"STATUS={label}… {last_pct:.1f}% complete (still active; near stream completion, waiting for receive-side finalization, {mib:.1f} MiB sent{progress_note})"
                    )
                else:
                    notifier.notify(
                        f"STATUS={label}… {last_pct:.1f}% complete (still active; replaying many small snapshot deltas, {mib:.1f} MiB sent{progress_note})"
                    )
                last_liveness_notice = now
        else:
            if (now - last_emit) >= max(5.0, min_interval):
                mib = bytes_sent / (1024 * 1024)
                notifier.notify(f"STATUS={label}… {mib:.1f} MiB sent")
                safe_print(f"{label}… {mib:.1f} MiB sent")
                last_emit = now

        if (now - last_dbg) >= 10.0:
            elapsed = now - start_time
            avg_rate = bytes_sent / elapsed if elapsed > 0 else 0
            window_elapsed = now - window_start
            current_rate = window_bytes / window_elapsed if window_elapsed > 0 else 0
            eta_str = ""
            if total_bytes and avg_rate > 0:
                remaining = total_bytes - bytes_sent
                eta_secs = remaining / avg_rate
                eta_str = f" ETA={int(eta_secs)}s"
            dbg(
                f"heartbeat {label}: bytes_sent={bytes_sent} ({bytes_sent/(1024*1024):.1f} MiB) "
                f"current_rate={current_rate/(1024*1024):.1f} MiB/s "
                f"avg_rate={avg_rate/(1024*1024):.1f} MiB/s{eta_str}"
            )
            last_dbg = now
            window_bytes = 0
            window_start = now

    try:
        dst.flush()
    except Exception:
        pass

    elapsed = time.time() - start_time
    avg_rate = bytes_sent / elapsed if elapsed > 0 else 0
    if not pipe_broken:
        notifier.notify(f"STATUS={label}… 100.0% complete")
    est_note = ""
    if total_bytes:
        est_note = f" estimated_total={total_bytes} accuracy={bytes_sent * 100.0 / total_bytes:.1f}%"
    dbg(
        f"{label} finished: bytes_sent={bytes_sent} ({format_bytes(bytes_sent)}) "
        f"elapsed={elapsed:.1f}s avg_rate={avg_rate/(1024*1024):.1f} MiB/s pipe_broken={pipe_broken}{est_note}"
    )
    return bytes_sent, pipe_broken


def _wait_with_finalize_heartbeat(proc, wait_on, timeout, heartbeat_interval=15):
    """Wait for a process with periodic finalize heartbeat updates."""
    start = time.time()
    interval = max(1.0, float(heartbeat_interval or 15))
    while True:
        elapsed = time.time() - start
        remaining = timeout - elapsed
        if remaining <= 0:
            raise subprocess.TimeoutExpired(proc.args, timeout)
        try:
            return proc.wait(timeout=min(interval, remaining))
        except subprocess.TimeoutExpired:
            elapsed_i = int(time.time() - start)
            remaining_i = max(0, int(timeout - elapsed_i))
            dbg(f"finalize heartbeat: waiting_on={wait_on} pid={getattr(proc, 'pid', '?')} elapsed={elapsed_i}s remaining={remaining_i}s")
            notifier.notify(f"STATUS=Finalizing receive… waiting on {wait_on} ({elapsed_i}s elapsed)")


def _communicate_with_finalize_heartbeat(proc, wait_on, timeout, heartbeat_interval=15):
    """communicate() with periodic finalize heartbeat updates."""
    start = time.time()
    interval = max(1.0, float(heartbeat_interval or 15))
    while True:
        elapsed = time.time() - start
        remaining = timeout - elapsed
        if remaining <= 0:
            raise subprocess.TimeoutExpired(proc.args, timeout)
        try:
            return proc.communicate(timeout=min(interval, remaining))
        except subprocess.TimeoutExpired:
            elapsed_i = int(time.time() - start)
            remaining_i = max(0, int(timeout - elapsed_i))
            dbg(f"finalize heartbeat: waiting_on={wait_on} pid={getattr(proc, 'pid', '?')} elapsed={elapsed_i}s remaining={remaining_i}s")
            notifier.notify(f"STATUS=Finalizing receive… waiting on {wait_on} ({elapsed_i}s elapsed)")


def format_bytes(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KiB"
    if n < 1024**3:
        return f"{n / (1024**2):.1f} MiB"
    if n < 1024**4:
        return f"{n / (1024**3):.1f} GiB"
    return f"{n / (1024**4):.1f} TiB"


def _kill_procs(*procs):
    """Terminate and wait on a list of subprocesses (best effort)."""
    for p in procs:
        if p is None:
            continue
        try:
            p.kill()
        except Exception:
            pass
    for p in procs:
        if p is None:
            continue
        try:
            p.wait(timeout=10)
        except Exception:
            pass
