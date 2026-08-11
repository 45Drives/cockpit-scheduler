"""Stable entry point for the ZFS replication task."""

from .models import ReplicationRun
from .workflow import handle_failure, run_replication


def main():
    ctx = ReplicationRun()
    try:
        run_replication(ctx)
    except Exception as error:
        handle_failure(ctx, error)

