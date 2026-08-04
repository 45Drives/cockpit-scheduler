"""Environment parsing and filesystem path helpers."""

import os

def as_bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def clamp_mbuffer(size_value, unit_value):
    """Return a positive mbuffer size and a supported unit."""
    try:
        size = int(str(size_value).strip() or "0")
    except (TypeError, ValueError):
        size = 0

    unit = (unit_value or "G").strip().upper()
    if unit not in ("K", "M", "G"):
        unit = "G"
    if size <= 0:
        size = 1
    return str(size), unit


def join_zfs_path(pool: str, dataset: str) -> str:
    pool = (pool or "").strip()
    ds = (dataset or "").strip()

    if not pool:
        return ds
    if not ds:
        return pool

    if ds == pool or ds.startswith(pool + "/"):
        return ds

    first = ds.split("/", 1)[0]
    if first == pool:
        return ds

    return f"{pool}/{ds}"


def get_dest_ports(transfer_method: str):
    """
    Returns (ssh_port, data_port).
    - ssh_port: control-plane operations (list/prune/start listener)
    - data_port: data-plane for netcat transfers
    """
    data_port = os.environ.get("zfsRepConfig_destDataset_port", "22")
    ssh_port = os.environ.get("zfsRepConfig_destDataset_sshPort", "")

    transfer_method = (transfer_method or "").strip().lower()

    if transfer_method == "netcat":
        if not ssh_port:
            ssh_port = "22"
        return (ssh_port, data_port)

    if not ssh_port:
        ssh_port = data_port or "22"
    return (ssh_port, data_port)
