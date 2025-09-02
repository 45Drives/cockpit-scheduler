#!/usr/bin/env python3
import os, pwd, argparse, configparser, json
import sys

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

def delete_remote(remote_name: str, conf_path: str, uid, gid):
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)

    if remote_name not in cfg.sections():
        print(f"Remote '{remote_name}' not found.")
        return

    cfg.remove_section(remote_name)
    _write_config_atomic(conf_path, cfg, uid, gid)
    print(f"Remote '{remote_name}' deleted.")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Delete rclone remote")
    p.add_argument("remote_name")
    p.add_argument("--user")
    p.add_argument("--config")
    args = p.parse_args()

    path, uid, gid = _expand_user_config(args.user, args.config)
    delete_remote(args.remote_name, path, uid, gid)