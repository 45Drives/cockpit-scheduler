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

def edit_remote_in_conf(old_name: str, updated_remote: dict[str, Any], conf_path: str, uid, gid):
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)

    new_name = updated_remote["name"]
    remote_type = updated_remote["type"]
    auth_params = updated_remote["authParams"]

    if not cfg.has_section(old_name):
        raise ValueError(f"Remote '{old_name}' not found")

    if old_name != new_name:
        cfg[new_name] = cfg[old_name]
        cfg.remove_section(old_name)

    cfg.set(new_name, "type", remote_type)
    # wipe old keys (except type) so removed fields don't linger
    for k in list(cfg[new_name].keys()):
        if k != "type":
            cfg.remove_option(new_name, k)

    for k, v in auth_params.items():
        if isinstance(v, dict):
            v = v.get("value", v)
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        if v not in (None, "", []):
            cfg.set(new_name, k, str(v))

    _write_config_atomic(conf_path, cfg, uid, gid)
    print(f"Remote '{old_name}' updated as '{new_name}' in {conf_path}")

def main():
    p = argparse.ArgumentParser(description="Edit CloudSyncRemote in rclone.conf")
    p.add_argument("--old_name", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--user")
    p.add_argument("--config")
    args = p.parse_args()

    path, uid, gid = _expand_user_config(args.user, args.config)
    updated = json.loads(args.data)
    edit_remote_in_conf(args.old_name, updated, path, uid, gid)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e)); sys.exit(1)