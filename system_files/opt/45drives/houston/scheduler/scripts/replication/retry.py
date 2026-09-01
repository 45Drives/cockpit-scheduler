"""Retry policy for the ZFS replication task.

Thin binding over the shared ``task_retry`` module: it pins the unit-name
fallback and routes diagnostics into the replication debug log.
"""

import task_retry
from task_retry import DEFAULT_MAX_ATTEMPTS, NO_RETRY_EXIT_CODE

from .logging_utils import dbg

# The workflow already uses exit code 2 for user-actionable configuration errors.
PERMANENT_FAILURE_EXIT_CODE = 2
UNIT_NAME_PREFIX = "houston_scheduler_ZfsReplicationTask_"


def _unit_name():
    return task_retry.unit_name(UNIT_NAME_PREFIX)


def max_attempts():
    return task_retry.max_attempts()


def current_attempt():
    return task_retry.current_attempt(unit=_unit_name(), log=dbg)


def failure_exit_code(permanent=False):
    return task_retry.failure_exit_code(permanent=permanent, unit=_unit_name(), log=dbg)


def resolve_exit_code(code):
    return task_retry.resolve_exit_code(
        code,
        permanent_exit_codes=(PERMANENT_FAILURE_EXIT_CODE,),
        unit=_unit_name(),
        log=dbg,
    )
