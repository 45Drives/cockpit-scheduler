"""Shared helper for printing a compact, parseable transfer summary to stdout/journal.

Used by rsync-script.py, cloudsync-script.py and the ZFS replication task so every
transfer-style task ends its journal output with the same easy-to-read block. The
frontend (scheduler/src/composables/taskTransferSummary.ts) looks for the delimiter
lines below and parses the "Key: value" pairs in between, so keep the format stable.
"""
import datetime

SUMMARY_START = "===TASK_SUMMARY_START==="
SUMMARY_END = "===TASK_SUMMARY_END==="

_UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]

_UNIT_MULTIPLIERS = {
    "b": 1,
    "kb": 1000, "kib": 1024,
    "mb": 1000 ** 2, "mib": 1024 ** 2,
    "gb": 1000 ** 3, "gib": 1024 ** 3,
    "tb": 1000 ** 4, "tib": 1024 ** 4,
    "pb": 1000 ** 5, "pib": 1024 ** 5,
}


def format_bytes(n):
    """Human-readable byte count, e.g. '12.3 GiB'."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "0 B"
    if n < 0:
        n = 0
    for unit in _UNITS:
        if n < 1024.0 or unit == _UNITS[-1]:
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PiB"


def parse_size_to_bytes(value, unit):
    """Convert a numeric string + unit (e.g. '1.23', 'GiB') into raw bytes, or None."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    multiplier = _UNIT_MULTIPLIERS.get(str(unit).strip().lower())
    if multiplier is None:
        return None
    return int(num * multiplier)


def format_duration(seconds):
    """Human-readable duration, e.g. '1h 5m 32s'."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "unknown"
    if seconds < 0:
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if hours or minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def print_transfer_summary(status, started_at, finished_at=None, bytes_transferred=None, extra_lines=None):
    """Print a delimited, easy-to-read summary block to stdout (captured by the journal).

    status: e.g. 'SUCCESS', 'FAILED', 'STALLED'
    started_at / finished_at: datetime.datetime instances (finished_at defaults to now)
    bytes_transferred: total bytes moved this run, or None if unknown
    extra_lines: optional list of extra "Label: value" strings
    """
    finished_at = finished_at or datetime.datetime.now()
    duration_seconds = None
    if started_at:
        duration_seconds = max(0.0, (finished_at - started_at).total_seconds())

    lines = [SUMMARY_START, f"Status: {status}"]
    if started_at:
        lines.append(f"Started: {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Finished: {finished_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if duration_seconds is not None:
        lines.append(f"Duration: {format_duration(duration_seconds)}")
    if bytes_transferred is not None:
        lines.append(f"Data Transferred: {format_bytes(bytes_transferred)}")
    for extra in (extra_lines or []):
        lines.append(extra)
    lines.append(SUMMARY_END)

    print("\n".join(lines))
