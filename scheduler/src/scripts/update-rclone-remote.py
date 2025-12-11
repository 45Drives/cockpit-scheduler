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


def edit_remote_in_conf(
    old_name: str,
    updated_remote: Dict[str, Any],
    conf_path: str,
    uid: Optional[int],
    gid: Optional[int],
) -> None:
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

    # Merge in default client_id/client_secret if user did not provide values
    # (handles dict-with-value and whitespace-only strings correctly)
    _merge_default_client_creds(auth_params, remote_type)

    for k, v in auth_params.items():
        v = _normalize_param_value(v)
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        if v not in (None, "", []):
            cfg.set(new_name, k, str(v))

    _write_config_atomic(conf_path, cfg, uid, gid)
    print(f"Remote '{old_name}' updated as '{new_name}' in {conf_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Edit CloudSyncRemote in rclone.conf"
    )
    parser.add_argument("--old_name", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--user")
    parser.add_argument("--config")
    args = parser.parse_args()

    path, uid, gid = _expand_user_config(args.user, args.config)
    updated = json.loads(args.data)
    edit_remote_in_conf(args.old_name, updated, path, uid, gid)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(str(e))
        sys.exit(1)
