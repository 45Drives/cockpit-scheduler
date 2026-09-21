"""Shared detection and wait handling for ZFS EBUSY ("dataset is busy") failures.

A dataset that is the target of an in-flight `zfs receive` is held by ZFS, so
`zfs snapshot`, `zfs receive` and `zfs destroy` against it all fail with
"dataset is busy". The condition clears on its own once the other operation
finishes, so a single command is given a short wait budget before it is allowed
to fail.

This wait is deliberately NOT a retry. It happens inside one task run, costs no
attempt from the task's configured retry policy, and the messages below avoid
"attempt N of M" wording so it cannot be mistaken for one.
"""

import re

BUSY_WAIT_BUDGET_SECONDS = 45
BUSY_STEP_SECONDS = 3

# Narrow on purpose: a generic "busy" match would swallow unrelated failures.
_BUSY_PATTERN = re.compile(
    r"dataset is busy|pool or dataset is busy|dataset busy",
    re.IGNORECASE,
)

BUSY_HINT = (
    "The dataset is in use by another ZFS operation, most often a send/receive "
    "running against the same dataset. Check for a concurrent replication into "
    "or out of it."
)


def is_dataset_busy(text):
    return bool(_BUSY_PATTERN.search(text or ""))


def busy_wait_schedule(budget=BUSY_WAIT_BUDGET_SECONDS, step=BUSY_STEP_SECONDS):
    """Backoff waits (3s, 6s, 9s, ...) truncated so their sum stays within `budget`."""
    delays = []
    total = 0
    nxt = step
    while total + nxt <= budget:
        delays.append(nxt)
        total += nxt
        nxt += step
    return delays


def busy_wait_notice(target, delay, waited, budget=BUSY_WAIT_BUDGET_SECONDS):
    return (
        f"{target} is busy (held by another ZFS operation). Waiting {delay}s; "
        f"{waited}s of the {budget}s wait budget used. This is not a task retry."
    )


def busy_wait_status(target, delay, waited, budget=BUSY_WAIT_BUDGET_SECONDS):
    return f"STATUS=Waiting {delay}s for busy dataset {target} ({waited}s/{budget}s)…"


def busy_giveup_notice(target, budget=BUSY_WAIT_BUDGET_SECONDS):
    return (
        f"{target} was still busy after waiting {budget}s, so this run is failing. "
        f"{BUSY_HINT} The task's own retry policy decides what happens next."
    )


def merge_streams(stdout, stderr):
    """stderr first: zfs writes the diagnostic there and stdout is usually empty."""
    parts = [part.strip() for part in ((stderr or ""), (stdout or "")) if (part or "").strip()]
    return "\n".join(parts)
