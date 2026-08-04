"""Shared constants for ZFS replication."""

import os

TASK_PROP = "com.45drives_scheduler:task_name"
TIER_PROP = "com.45drives_scheduler:scheduler_interval_tier"

ZFS_LIST_TIMEOUT = 600
ZFS_DESTROY_TIMEOUT = int(os.environ.get("ZFS_DESTROY_TIMEOUT", "120"))
PIPELINE_FINALIZE_TIMEOUT = int(os.environ.get("ZFS_REP_FINALIZE_TIMEOUT", "1800"))
TRANSFER_STALL_TIMEOUT = int(os.environ.get("ZFS_REP_STALL_TIMEOUT", "3600"))
MBUFFER_BLOCK_SIZE = os.environ.get("ZFS_REP_MBUFFER_BLOCK", "256k").strip()
NC_BIND_ADDRESS = os.environ.get("ZFS_REP_NC_BIND_ADDRESS", "").strip() or None
DIRECT_PIPE_ENABLED = os.environ.get("ZFS_REP_DIRECT_PIPE", "").strip().lower() in ("1", "true", "yes", "on")

