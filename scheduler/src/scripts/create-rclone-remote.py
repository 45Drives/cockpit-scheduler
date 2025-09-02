#!/usr/bin/env python3
import os, pwd, argparse, configparser, json
import sys
from typing import Any

def _expand_user_config(user_arg: str | None, config_arg: str | None) -> tuple[str, int | None, int | None]:
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

def _ensure_parent(conf_path: str, uid: int | None, gid: int | None):
    d = os.path.dirname(conf_path)
    os.makedirs(d, mode=0o700, exist_ok=True)
    try:
        if uid is not None and os.geteuid() == 0:
            os.chown(d, uid, gid)
    except PermissionError:
        pass  # best-effort

def _write_config_atomic(conf_path: str, cfg: configparser.ConfigParser, uid: int | None, gid: int | None):
    _ensure_parent(conf_path, uid, gid)
    tmp = conf_path + ".tmp"
    with open(tmp, "w") as f:
        cfg.write(f)
    os.chmod(tmp, 0o600)
    try:
        if uid is not None and os.geteuid() == 0:
            os.chown(tmp, uid, gid)
    except PermissionError:
        pass
    os.replace(tmp, conf_path)

def save_remote_to_conf(remote: dict[str, Any], conf_path: str, uid, gid):
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)

    name = remote["name"]
    remote_type = remote["type"]
    auth_params = remote["authParams"]

    if cfg.has_section(name):
        raise ValueError(f"Remote '{name}' already exists")

    cfg.add_section(name)
    cfg.set(name, "type", remote_type)
    for k, v in auth_params.items():
        if isinstance(v, dict):
            v = v.get("value", v)
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        if v not in (None, "", []):
            cfg.set(name, k, str(v))

    _write_config_atomic(conf_path, cfg, uid, gid)
    print(f"Remote '{name}' saved to {conf_path}")

def main():
    p = argparse.ArgumentParser(description="Save a CloudSyncRemote to rclone.conf")
    p.add_argument("--data", required=True, help="JSON string of CloudSyncRemote data")
    p.add_argument("--user", help="Target username for ~user/.config/rclone/rclone.conf")
    p.add_argument("--config", help="Explicit rclone.conf path (overrides --user)")
    args = p.parse_args()

    conf_path, uid, gid = _expand_user_config(args.user, args.config)
    remote = json.loads(args.data)
    save_remote_to_conf(remote, conf_path, uid, gid)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        sys.exit(1)
