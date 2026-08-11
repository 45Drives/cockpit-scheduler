"""Data models used by replication planning."""

from typing import Any, Dict, List, Optional, Union


RetentionValue = Union[str, int]


class Snapshot:
    def __init__(self, name, guid, creation, creation_epoch=0, order_key=0, task_tag=None, tier_tag=None):
        self.name = name
        self.guid = guid
        self.creation = creation
        self.creation_epoch = creation_epoch
        self.order_key = order_key
        self.task_tag = task_tag
        self.tier_tag = tier_tag


class ReplicationRun:
    """Mutable state shared by the small orchestration phases."""

    def __init__(self):
        self.taskName = ""
        self.direction = "push"
        self.isRecursiveSnap = False
        self.useCustomName = False
        self.customName = ""
        self.isRaw = False
        self.isCompressed = False
        self.includeIntermediateSnapshots: Optional[bool] = None
        self.transferMethod = ""
        self.sshPort = "22"
        self.dataPort = "22"
        self.allowOverwrite = False
        self.useExistingDest = False
        self.forceFullSend = False
        self.dryRun = False
        self.resumeOnly = False
        self.resumeFailAllowOverwrite = False
        self.resumeStallTimeout = 3600
        self.remoteUser = "root"
        self.remoteHost = ""
        self.mBufferSize = "1"
        self.mBufferUnit = "G"
        self.sourceRetentionTime: RetentionValue = 0
        self.sourceRetentionUnit = ""
        self.destinationRetentionTime: RetentionValue = 0
        self.destinationRetentionUnit = ""
        self.tier_idx: Optional[int] = None
        self.schedule_data: Optional[Dict[str, Any]] = None
        self.sourceFilesystem = ""
        self.destFilesystem = ""
        self.sourceSnapshots: List[Snapshot] = []
        self.destinationSnapshots: Optional[List[Snapshot]] = None
        self.forceOverwrite = False
        self.incrementalSnapName = ""
        self.pending_state: Optional[Dict[str, Any]] = None
        self.newSnap = "unknown"
        self.current_pct = 0
