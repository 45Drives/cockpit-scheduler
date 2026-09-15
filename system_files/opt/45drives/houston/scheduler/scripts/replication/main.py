"""Stable entry point for the ZFS replication task."""

import task_lastrun

from .context import notifier
from .logging_utils import safe_print
from .models import ReplicationRun
from .retry import (
    NO_RETRY_EXIT_CODE,
    PERMANENT_FAILURE_EXIT_CODE,
    max_attempts,
    resolve_exit_code,
    unit_name,
)
from .workflow import handle_failure, run_replication


def main():
    ctx = ReplicationRun()
    # Assume failure: anything that escapes without setting this is not a success.
    outcome = task_lastrun.FAILED
    try:
        try:
            run_replication(ctx)
            outcome = task_lastrun.SUCCESS
        except SystemExit:
            raise
        except Exception as error:
            handle_failure(ctx, error)
    except SystemExit as exit_request:
        raw_code = exit_request.code
        code = resolve_exit_code(raw_code)
        outcome = task_lastrun.SUCCESS if code == 0 else task_lastrun.FAILED
        if code == NO_RETRY_EXIT_CODE:
            if raw_code == PERMANENT_FAILURE_EXIT_CODE:
                msg = (
                    'This failure needs a configuration or destination change, so it will not be '
                    'retried automatically. The task will run again at its next scheduled time.'
                )
            else:
                msg = (
                    f'Attempt limit reached ({max_attempts()} per scheduled run). Not retrying '
                    'automatically. The task will run again at its next scheduled time.'
                )
            notifier.notify(f'STATUS=ZFS replication task failed. {msg}')
            safe_print(msg)
        raise SystemExit(code)
    finally:
        task_lastrun.persist(unit_name(), outcome)

