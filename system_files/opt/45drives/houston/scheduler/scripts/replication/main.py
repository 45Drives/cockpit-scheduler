"""Stable entry point for the ZFS replication task."""

from .context import notifier
from .logging_utils import safe_print
from .models import ReplicationRun
from .retry import (
    NO_RETRY_EXIT_CODE,
    PERMANENT_FAILURE_EXIT_CODE,
    max_attempts,
    resolve_exit_code,
)
from .workflow import handle_failure, run_replication


def main():
    ctx = ReplicationRun()
    try:
        try:
            run_replication(ctx)
        except SystemExit:
            raise
        except Exception as error:
            handle_failure(ctx, error)
    except SystemExit as exit_request:
        raw_code = exit_request.code
        code = resolve_exit_code(raw_code)
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

