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


def _normalize_param_value(v: Any) -> Any:
    """
    Normalize how auth param values are represented:
    - If v is a dict with a 'value' key, return that.
    - Otherwise return v unchanged.
    """
    if isinstance(v, dict) and "value" in v:
        return v.get("value")
    return v


def _is_blank(v: Any) -> bool:
    """
    Return True if the value should be treated as 'not provided' by the user.
    """
    v = _normalize_param_value(v)

    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def _merge_default_client_creds(
    auth_params: Dict[str, Any],
    remote_type: str,
) -> None:
    """
    Merge in default client_id/client_secret from packaged creds
    if the user did not supply a non-blank value.
    """
    client_creds = load_client_creds()
    backend_key = str(remote_type).lower()
    defaults = client_creds.get(backend_key) or {}

    for field in ("client_id", "client_secret"):
        if _is_blank(auth_params.get(field)):
            default_value = defaults.get(field)
            if not _is_blank(default_value):
                auth_params[field] = default_value


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
    # but only if user did not supply their own (after normalization).
    _merge_default_client_creds(auth_params, remote_type)

    cfg.add_section(name)
    cfg.set(name, "type", remote_type)
    for k, v in auth_params.items():
        v = _normalize_param_value(v)
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
