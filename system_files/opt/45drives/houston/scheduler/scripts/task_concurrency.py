"""Per-destination-host concurrency limiting, shared by any task type that
opens SSH connections to a remote host (ZFS replication, rsync).

Tasks that all fire at the same scheduled time and target the same remote
host can overwhelm that host's ability to accept new SSH connections
(sshd's own connection throttling, plus CPU/network contention from
transfers already under way), which surfaces as "failed to establish SSH
connection" errors that cascade through the rest of the burst. This module
gates how many task runs may be actively connected to/transferring with a
given remote host at once, across all task types; runs beyond the limit
wait for a slot instead of racing each other, with no need to know in
advance how long any run will take.
"""

import configparser
import contextlib
import fcntl
import os
import re
import time

from transfer_summary import format_duration

SCHEDULER_CONF_PATH = "/opt/45drives/houston/scheduler/scheduler.conf"
DEFAULT_MAX_CONCURRENT_PER_HOST = 3
SLOT_DIR_ROOT = "/run/houston-scheduler/task-slots"
POLL_INTERVAL_SEC = 2.0
NOTIFY_REPEAT_SEC = 30.0


def max_concurrent_per_host():
    """Resolve the per-host concurrency limit.

    A value of 0 (or negative) disables gating entirely. Checked first via
    HOUSTON_MAX_CONCURRENT_PER_HOST, then scheduler.conf's
    [concurrency] max_per_host, falling back to the default.
    """
    raw = os.environ.get("HOUSTON_MAX_CONCURRENT_PER_HOST", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    try:
        config = configparser.ConfigParser()
        config.read(SCHEDULER_CONF_PATH)
        return config.getint(
            "concurrency", "max_per_host",
            fallback=DEFAULT_MAX_CONCURRENT_PER_HOST,
        )
    except (configparser.Error, OSError, ValueError):
        return DEFAULT_MAX_CONCURRENT_PER_HOST


def _slot_dir(host):
    safe_host = re.sub(r"[^A-Za-z0-9_.-]", "_", host.strip()) or "unknown"
    return os.path.join(SLOT_DIR_ROOT, safe_host)


@contextlib.contextmanager
def acquire_host_slot(host, notify=None, poll_interval=POLL_INTERVAL_SEC):
    """Block until a concurrency slot for *host* is free, then hold it.

    Slots are OS-level advisory locks (flock) on small files under /run, one
    per allowed concurrent run. Whichever process holds the lock on a slot
    file owns that slot until it exits or the context manager releases it;
    the kernel drops the lock automatically if the process dies, so a
    crashed run can never leak a permanently-held slot. The slot pool is
    keyed only by host, so replication and rsync tasks aimed at the same
    host correctly share the same limit instead of each getting their own.

    Gating is skipped entirely when *host* is empty (nothing to serialize
    against, e.g. local-only tasks) or the configured limit is <= 0.

    *notify* (if given) receives "STATUS=..." live-status updates; separately,
    plain lines are always printed to stdout so a wait shows up in the task's
    journal-backed log, not just the transient systemd status text. Yields a
    dict with ``waited_seconds`` so the caller can surface it in its own
    end-of-run summary.
    """
    host = (host or "").strip()
    limit = max_concurrent_per_host()
    if not host or limit <= 0:
        yield {"waited_seconds": 0.0}
        return

    slot_dir = _slot_dir(host)
    os.makedirs(slot_dir, exist_ok=True)

    fd = None
    waited = False
    wait_start = None
    last_notify = 0.0
    try:
        while fd is None:
            for i in range(limit):
                slot_path = os.path.join(slot_dir, f"slot-{i}.lock")
                candidate = os.open(slot_path, os.O_CREAT | os.O_RDWR, 0o644)
                try:
                    fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fd = candidate
                    break
                except OSError:
                    os.close(candidate)
            if fd is None:
                now = time.time()
                if wait_start is None:
                    wait_start = now
                if not waited or now - last_notify >= NOTIFY_REPEAT_SEC:
                    message = f"Waiting for a free task slot to {host} (0/{limit} available, {limit} in use)…"
                    print(message)
                    if notify:
                        notify(f"STATUS={message}")
                    last_notify = now
                waited = True
                time.sleep(poll_interval)
        waited_seconds = (time.time() - wait_start) if wait_start is not None else 0.0
        if waited:
            message = f"Slot to {host} acquired after waiting {format_duration(waited_seconds)}; starting now."
            print(message)
            if notify:
                notify(f"STATUS={message}")
        yield {"waited_seconds": waited_seconds}
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
