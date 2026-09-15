"""Durable last-run marker shared by every scheduler task type.

systemd keeps a unit's ExecMain/ActiveEnter timestamps in memory only, so a
reboot — or a reset-failed, or a Type=notify service exiting — leaves the unit
reporting Result=success with no timestamps at all, indistinguishable from a
unit that has never run. The UI cannot tell those apart, so it falls back to
this file. It is written once, when the run ends, and records both the end time
and the outcome so a failed run is not later rendered as a success.
"""

import os
import re
import time

SYSTEMD_DIR = "/etc/systemd/system"
SUCCESS = "success"
FAILED = "failed"

# The unit name lands in a filesystem path, so keep it to characters systemd
# itself allows in a unit name and nothing that could traverse out of the dir.
_SAFE_UNIT = re.compile(r"^[A-Za-z0-9_.@-]+$")


def marker_path(unit):
    """Absolute path of the marker for a unit, or '' if the name is unusable."""
    name = (unit or "").strip()
    if name.endswith(".service"):
        name = name[: -len(".service")]
    if not name or name.startswith(".") or ".." in name:
        return ""
    if not _SAFE_UNIT.match(name):
        return ""
    return os.path.join(SYSTEMD_DIR, name + ".lastrun")


def persist(unit, outcome=SUCCESS):
    """Stamp the marker with the run's end time and outcome.

    Never raises: a task must not fail because its bookkeeping file could not be
    written. Writes via a temp file so a concurrent read cannot see a half-line.
    """
    path = marker_path(unit)
    if not path:
        return
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w") as handle:
            handle.write(f"{int(time.time())} {outcome}\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
