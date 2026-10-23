"""ZFS send command planning."""

import os
import shlex

EXTRA_SEND_ARGS_ENV = "zfsRepConfig_sendOptions_extraSendArgs"
EXTRA_RECV_ARGS_ENV = "zfsRepConfig_sendOptions_extraRecvArgs"

# Flag -> whether it takes a value. Anything else is either already managed by the
# scheduler (-R -I -i -t -w -L -c -F -s ...) or would break its dataset/snapshot logic (-d -e -n).
EXTRA_SEND_FLAGS = {
    "-p": False, "--props": False,
    "-b": False, "--backup": False,
    "-h": False, "--holds": False,
    "-e": False, "--embed": False,
    "-L": False, "--large-block": False,
    "-c": False, "--compressed": False,
}
EXTRA_RECV_FLAGS = {
    "-o": True,
    "-x": True,
    "-u": False,
    "-h": False,
}
# Receiving as a clone would detach the destination from the task's snapshot chain.
_RESERVED_RECV_PROPERTIES = {"origin"}
# Keys are not managed by the task; overriding them on receive leaves a destination nobody can unlock.
_ENCRYPTION_PROPERTIES = {"encryption", "keyformat", "keylocation", "pbkdf2iters"}
# The task tags snapshots with these; dropping or overriding them breaks ownership and retention.
_TASK_PROPERTY_PREFIX = "com.45drives_scheduler:"
_FLAG_ALIASES = {
    "--props": "-p", "--backup": "-b", "--holds": "-h",
    "--embed": "-e", "--large-block": "-L", "--compressed": "-c",
}


class ExtraArgsError(ValueError):
    pass


def _checked_value(flag, value):
    if not value or value.startswith("-"):
        raise ExtraArgsError(f"{flag} needs a value")
    if flag in ("-o", "-x"):
        prop, eq, _ = value.partition("=")
        if flag == "-o" and not eq:
            raise ExtraArgsError(f"-o expects property=value, got {value!r}")
        if flag == "-x" and eq:
            raise ExtraArgsError(f"-x expects a property name, got {value!r}")
        if not prop:
            raise ExtraArgsError(f"{flag} needs a property name")
        if prop in _RESERVED_RECV_PROPERTIES:
            raise ExtraArgsError(f"{flag} {prop} is not allowed")
        if prop in _ENCRYPTION_PROPERTIES:
            raise ExtraArgsError(f"{flag} {prop} is not allowed; encryption settings can't be changed by a replication task")
        if prop.startswith(_TASK_PROPERTY_PREFIX):
            raise ExtraArgsError(f"{flag} {prop} is not allowed; the task relies on this property")
    return value


def _reject_duplicates(args):
    seen_flags = set()
    prop_owner = {}
    i = 0
    while i < len(args):
        flag = _FLAG_ALIASES.get(args[i], args[i])
        if flag in ("-o", "-x"):
            prop = args[i + 1].partition("=")[0]
            previous = prop_owner.get(prop)
            if previous == flag:
                raise ExtraArgsError(f"property {prop} is given more than once")
            if previous:
                raise ExtraArgsError(f"property {prop} can't be both set with -o and excluded with -x")
            prop_owner[prop] = flag
            i += 2
            continue
        if flag in seen_flags:
            raise ExtraArgsError(f"{flag} is given more than once")
        seen_flags.add(flag)
        i += 1


def parse_extra_zfs_args(text, allowed):
    """Split user-supplied extra arguments and reject anything outside the allowlist."""
    try:
        tokens = shlex.split(text or "")
    except ValueError as e:
        raise ExtraArgsError(f"cannot parse {text!r}: {e}") from e

    out = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if tok.startswith("--"):
            name, eq, value = tok.partition("=")
            if name not in allowed:
                raise ExtraArgsError(f"{name} is not an allowed option")
            if allowed[name]:
                if not eq:
                    if i >= len(tokens):
                        raise ExtraArgsError(f"{name} needs a value")
                    value = tokens[i]
                    i += 1
                out += [name, _checked_value(name, value)]
            elif eq:
                raise ExtraArgsError(f"{name} does not take a value")
            else:
                out.append(name)
        elif tok.startswith("-") and len(tok) > 1:
            letters = tok[1:]
            for j, ch in enumerate(letters):
                flag = "-" + ch
                if flag not in allowed:
                    raise ExtraArgsError(f"{flag} is not an allowed option")
                if allowed[flag]:
                    value = letters[j + 1:]
                    if not value:
                        if i >= len(tokens):
                            raise ExtraArgsError(f"{flag} needs a value")
                        value = tokens[i]
                        i += 1
                    out += [flag, _checked_value(flag, value)]
                    break
                out.append(flag)
        else:
            raise ExtraArgsError(f"unexpected argument {tok!r}; only options are allowed here")
    _reject_duplicates(out)
    return out


def canonical_send_flags(send_args):
    return {_FLAG_ALIASES.get(a, a) for a in send_args}


def check_extra_args_against_task(send_args, *, recursive, raw=False, compressed=False):
    """Reject extra arguments that repeat or contradict what the task's own settings already do."""
    flags = canonical_send_flags(send_args)
    if recursive and "-p" in flags:
        raise ExtraArgsError("-p is already included by Send Recursive")
    for flag in ("-L", "-c", "-e"):
        if raw and flag in flags:
            raise ExtraArgsError(f"{flag} is already implied by Send Raw")
    for flag in ("-L", "-c"):
        if compressed and flag in flags:
            raise ExtraArgsError(f"{flag} is already included by Send Compressed")
    # Found by the live matrix: zfs rejects a raw, non-recursive stream that carries holds but no properties.
    if raw and not recursive and "-h" in flags and "-p" not in flags:
        raise ExtraArgsError("-h with Send Raw also needs -p (or Send Recursive)")


def extra_send_args():
    return parse_extra_zfs_args(os.environ.get(EXTRA_SEND_ARGS_ENV, ""), EXTRA_SEND_FLAGS)


def extra_recv_args():
    return parse_extra_zfs_args(os.environ.get(EXTRA_RECV_ARGS_ENV, ""), EXTRA_RECV_FLAGS)


def build_zfs_recv_args(target, force_overwrite):
    """Receive argv for a new stream; resumed receives keep the options they started with."""
    args = ["zfs", "recv", "-s"]
    if force_overwrite:
        args.append("-F")
    args.extend(extra_recv_args())
    args.append(target)
    return args


def zfs_recv_shell(target, force_overwrite):
    return " ".join(shlex.quote(a) for a in build_zfs_recv_args(target, force_overwrite))


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
        # No -e by default: an encrypted destination rejects embedded-data records from a non-raw
        # stream. Users with unencrypted destinations can add it as an extra argument.
        args.append("-Lc")
    if raw:
        args.append("-w")
    args.extend(extra_send_args())
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

