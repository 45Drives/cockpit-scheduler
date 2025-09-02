#!/usr/bin/env python3
import os, pwd, argparse, configparser, json
from typing import Optional, Tuple

def _expand_user_config(user_arg: Optional[str], config_arg: Optional[str]) -> Tuple[str, Optional[int], Optional[int]]:
    # Decide rclone.conf path, and return (path, uid, gid) for optional chown
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


def load_remotes_from_conf(conf_path: str):
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)
    remotes = []
    for section in cfg.sections():
        rtype = cfg.get(section, "type", fallback="unknown")
        params = {k: v for k, v in cfg.items(section) if k != "type"}
        remotes.append({"name": section, "type": rtype, "parameters": params})
    return json.dumps(remotes, indent=2)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="List rclone remotes")
    p.add_argument("--user")
    p.add_argument("--config")
    args = p.parse_args()

    path, _, _ = _expand_user_config(args.user, args.config)
    print(load_remotes_from_conf(path))