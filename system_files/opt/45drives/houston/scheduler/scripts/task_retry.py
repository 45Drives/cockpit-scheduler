"""Bounded retry accounting shared by every scheduler task type.

systemd's StartLimitBurst/StartLimitIntervalSec pair cannot bound retries for a
unit whose runtime is unbounded: the rate limiter only counts starts, so once a
run takes longer than the window the limiter never trips and ``Restart=on-failure``
loops forever. Attempts are counted from the unit's own NRestarts instead, and the
final attempt exits with NO_RETRY_EXIT_CODE, which the unit lists in
RestartPreventExitStatus so systemd stops and lets the timer schedule the next run.
"""

import configparser
import os
import subprocess
import sys

NO_RETRY_EXIT_CODE = 90
DEFAULT_MAX_ATTEMPTS = 3
SCHEDULER_CONF_PATH = "/opt/45drives/houston/scheduler/scheduler.conf"


def _default_log(msg):
    try:
        sys.stderr.write(f"{msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def unit_name(fallback_prefix=""):
    unit = (os.environ.get("HOUSTON_SCHEDULER_UNIT") or "").strip()
    if unit:
        return unit
    task_name = (os.environ.get("taskName") or "").strip()
    if fallback_prefix and task_name:
        return f"{fallback_prefix}{task_name}.service"
    return ""


def max_attempts():
    """Total permitted attempts per scheduled run, including the first one."""
    raw = os.environ.get("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "")
    try:
        value = int(str(raw).strip())
        return value if value >= 1 else DEFAULT_MAX_ATTEMPTS
    except (TypeError, ValueError):
        pass
    # Units created before HOUSTON_SCHEDULER_MAX_ATTEMPTS existed.
    try:
        config = configparser.ConfigParser()
        config.read(SCHEDULER_CONF_PATH)
        value = config.getint("retry", "start_limit_burst", fallback=DEFAULT_MAX_ATTEMPTS)
        return value if value >= 1 else DEFAULT_MAX_ATTEMPTS
    except (configparser.Error, OSError, ValueError):
        return DEFAULT_MAX_ATTEMPTS


def current_attempt(unit=None, log=None):
    """1-based attempt number within this start cycle.

    systemd clears NRestarts on every explicit start (timer or manual) and keeps
    it across automatic restarts, so it is exactly the counter we need.
    """
    log = log or _default_log
    unit = unit if unit is not None else unit_name()
    if not unit:
        return 1
    try:
        proc = subprocess.run(
            ["systemctl", "show", unit, "--property=NRestarts", "--value"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as e:
        log(f"retry: could not read NRestarts for {unit}: {e}")
        return 1
    if proc.returncode != 0:
        log(f"retry: systemctl show NRestarts failed for {unit}: {(proc.stderr or '').strip()}")
        return 1
    try:
        return int((proc.stdout or "").strip()) + 1
    except ValueError:
        return 1


def failure_exit_code(permanent=False, unit=None, log=None):
    """Exit code for a failed run.

    NO_RETRY_EXIT_CODE stops systemd from restarting so the unit settles into
    ``failed`` and the timer can trigger the next scheduled run; 1 lets systemd
    retry.
    """
    log = log or _default_log
    if permanent:
        return NO_RETRY_EXIT_CODE
    attempt = current_attempt(unit=unit, log=log)
    limit = max_attempts()
    if attempt >= limit:
        log(f"retry: attempt {attempt} of {limit} failed; suppressing further systemd restarts")
        return NO_RETRY_EXIT_CODE
    log(f"retry: attempt {attempt} of {limit} failed; systemd will retry")
    return 1


def resolve_exit_code(code, permanent_exit_codes=(), unit=None, log=None):
    """Map a raw SystemExit code onto the retry policy."""
    # sys.exit("message") prints the string and exits 1; leave it untouched.
    if not isinstance(code, int) or isinstance(code, bool):
        return code
    if code == 0 or code == NO_RETRY_EXIT_CODE:
        return code
    return failure_exit_code(permanent=code in permanent_exit_codes, unit=unit, log=log)


def run_with_retry_policy(main_func, permanent_exit_codes=(), unit=None, log=None):
    """Run a task entry point and translate its exit code into the retry policy."""
    try:
        main_func()
    except SystemExit as exit_request:
        raise SystemExit(
            resolve_exit_code(exit_request.code, permanent_exit_codes, unit=unit, log=log)
        )
