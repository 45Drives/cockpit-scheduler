#!/usr/bin/env python3
import argparse
import configparser
import json
import sys
from typing import Optional, Tuple, Dict, Any

from rclone_utils import _expand_user_config, _write_config_atomic


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

    for k, v in auth_params.items():
        if isinstance(v, dict):
            v = v.get("value", v)
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
