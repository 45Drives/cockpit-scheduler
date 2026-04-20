#!/usr/bin/env python3
"""List directory entries for path auto-completion.

Usage:
    python3 list-directory.py <partial_path> [--dirs-only]

Prints JSON array of matching entries.
If partial_path ends with '/', lists contents of that directory.
Otherwise, lists sibling entries in the parent directory that match the prefix.
"""

import json
import os
import sys

def main():
    dirs_only = "--dirs-only" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dirs-only"]

    if not args:
        print(json.dumps([]))
        return

    partial = args[0]

    # Normalise: resolve ~
    partial = os.path.expanduser(partial)

    # If it ends with / we list inside that directory
    if partial.endswith("/"):
        parent = partial
        prefix = ""
    else:
        parent = os.path.dirname(partial) or "/"
        prefix = os.path.basename(partial).lower()

    if not os.path.isdir(parent):
        print(json.dumps([]))
        return

    results = []
    try:
        entries = sorted(os.listdir(parent))
    except PermissionError:
        print(json.dumps([]))
        return

    for entry in entries:
        # Skip hidden files/dirs
        if entry.startswith("."):
            continue
        if prefix and not entry.lower().startswith(prefix):
            continue

        full = os.path.join(parent, entry)
        is_dir = os.path.isdir(full)

        if dirs_only and not is_dir:
            continue

        # Normalise the path for display
        display = full
        if is_dir and not display.endswith("/"):
            display += "/"

        results.append({
            "path": display,
            "name": entry,
            "isDir": is_dir,
        })

        # Cap results to avoid flooding the UI
        if len(results) >= 50:
            break

    print(json.dumps(results))


if __name__ == "__main__":
    main()
