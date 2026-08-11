"""ZFS send command planning."""

def build_zfs_send_args(sendName, sendName2, *, recursive, compressed, raw, include_intermediates=None):
    """Build zfs send argument list.

    include_intermediates controls -I vs -i independently of recursive:
      - None (default): legacy behavior (recursive implies -I)
      - True: use -I (all intermediate snapshots)
      - False: use -i (only delta from base to target)
    """
    args = ["zfs", "send"]
    if recursive:
        args.append("-R")
    if compressed:
        args.append("-Lce")
    if raw:
        args.append("-w")
    if sendName2:
        if include_intermediates is None:
            # Legacy: recursive implies -I
            flag = "-I" if recursive else "-i"
        elif include_intermediates:
            flag = "-I"
        else:
            flag = "-i"
        args.extend([flag, sendName2])
    args.append(sendName)
    return args

