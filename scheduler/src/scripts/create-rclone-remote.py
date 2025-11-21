#!/usr/bin/env python3
import argparse
import configparser
import json
import sys
from typing import Optional, Tuple, Dict, Any
import os
import pwd

CLIENT_CREDS_PATH = "/etc/45drives/houston/scheduler/cloud-sync-client-creds.json"


def load_client_creds() -> Dict[str, Any]:
    """
    Load packaged OAuth client credentials from JSON.
    Returns {} if the file is missing or invalid.
    """
    try:
        with open(CLIENT_CREDS_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If the file isn't there or is bad, just behave as before
        return {}


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


def save_remote_to_conf(
    remote: Dict[str, Any],
    conf_path: str,
    uid: Optional[int],
    gid: Optional[int],
) -> None:
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)

    name = remote["name"]
    remote_type = remote["type"]
    auth_params = remote["authParams"]

    if cfg.has_section(name):
        raise ValueError(f"Remote '{name}' already exists")

    # Merge in default client_id/client_secret from packaged creds,
    # but only if user did not supply their own.
    client_creds = load_client_creds()
    backend_key = str(remote_type).lower()
    if backend_key in client_creds:
        defaults = client_creds[backend_key] or {}
        if not auth_params.get("client_id"):
            auth_params["client_id"] = defaults.get("client_id")
        if not auth_params.get("client_secret"):
            auth_params["client_secret"] = defaults.get("client_secret")

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save a CloudSyncRemote to rclone.conf"
    )
    parser.add_argument(
        "--data",
        required=True,
        help="JSON string of CloudSyncRemote data",
    )
    parser.add_argument(
        "--user",
        help="Target username for ~user/.config/rclone/rclone.conf",
    )
    parser.add_argument(
        "--config",
        help="Explicit rclone.conf path (overrides --user)",
    )
    args = parser.parse_args()

    conf_path, uid, gid = _expand_user_config(args.user, args.config)
    remote = json.loads(args.data)
    save_remote_to_conf(remote, conf_path, uid, gid)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        sys.exit(1)
