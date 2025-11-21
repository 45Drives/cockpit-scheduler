#!/usr/bin/env python3
import argparse
import sys
import os
import pwd
import configparser
from typing import Optional, Tuple


def _expand_user_config(
    user_arg: Optional[str],
    config_arg: Optional[str],
) -> Tuple[str, Optional[int], Optional[int]]:
    """
    Decide rclone.conf path, and return (path, uid, gid) for optional chown.
    If config_arg is given, use that and do not chown.
    If user_arg is given, use that user's XDG config dir and chown to that user (if run as root).
    Otherwise, use current euid's home / XDG without chown.
    """
    if config_arg:
        return (config_arg, None, None)

    if user_arg:
        p = pwd.getpwnam(user_arg)
        home = p.pw_dir
        xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        return (os.path.join(xdg, "rclone", "rclone.conf"), p.pw_uid, p.pw_gid)

    # Default: current euid's home / XDG
    home = os.path.expanduser("~")
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return (os.path.join(xdg, "rclone", "rclone.conf"), None, None)


def _ensure_parent(conf_path: str, uid: Optional[int], gid: Optional[int]) -> None:
    """
    Ensure parent directory exists with restrictive permissions and optionally chown it.
    """
    d = os.path.dirname(conf_path)
    os.makedirs(d, mode=0o700, exist_ok=True)
    try:
        if uid is not None and os.geteuid() == 0:
            # gid may be None; os.chown requires int, so default to uid if gid is None
            os.chown(d, uid, gid if gid is not None else uid)
    except PermissionError:
        # best-effort; ignore if we can't chown
        pass


def _write_config_atomic(
    conf_path: str,
    cfg: configparser.ConfigParser,
    uid: Optional[int],
    gid: Optional[int],
) -> None:
    """
    Write config to a temp file then atomically replace the target.
    Optionally chown the file when running as root.
    """
    _ensure_parent(conf_path, uid, gid)
    tmp = conf_path + ".tmp"
    with open(tmp, "w") as f:
        cfg.write(f)
    os.chmod(tmp, 0o600)
    try:
        if uid is not None and os.geteuid() == 0:
            os.chown(tmp, uid, gid if gid is not None else uid)
    except PermissionError:
        # best-effort; ignore if we can't chown
        pass
    os.replace(tmp, conf_path)



def delete_remote(
    remote_name: str,
    conf_path: str,
    uid: Optional[int],
    gid: Optional[int],
) -> None:
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)

    if remote_name not in cfg.sections():
        print(f"Remote '{remote_name}' not found.")
        return

    cfg.remove_section(remote_name)
    _write_config_atomic(conf_path, cfg, uid, gid)
    print(f"Remote '{remote_name}' deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete rclone remote")
    parser.add_argument("remote_name")
    parser.add_argument("--user")
    parser.add_argument("--config")
    args = parser.parse_args()

    path, uid, gid = _expand_user_config(args.user, args.config)
    delete_remote(args.remote_name, path, uid, gid)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        sys.exit(1)
