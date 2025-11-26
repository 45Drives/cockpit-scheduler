#!/usr/bin/env python3
import argparse
import configparser
import json
import os
import pwd
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


def load_remotes_from_conf(conf_path: str) -> str:
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)
    remotes = []
    for section in cfg.sections():
        rtype = cfg.get(section, "type", fallback="unknown")
        params = {k: v for k, v in cfg.items(section) if k != "type"}
        remotes.append(
            {
                "name": section,
                "type": rtype,
                "parameters": params,
            }
        )
    return json.dumps(remotes, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="List rclone remotes")
    parser.add_argument("--user")
    parser.add_argument("--config")
    args = parser.parse_args()

    path, _, _ = _expand_user_config(args.user, args.config)
    print(load_remotes_from_conf(path))


if __name__ == "__main__":
    main()
