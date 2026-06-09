#!/usr/bin/env python3
"""Fetch all rclone provider options for supported backends.

Usage:
    python3 get-rclone-provider-options.py [--providers type1,type2,...]

If --providers is omitted, fetches options for all providers rclone supports.

Output: JSON object keyed by provider type, each containing an array of option objects:
{
    "s3": [
        {
            "name": "provider",
            "help": "Choose your S3 provider.",
            "default": "",
            "type": "string",
            "required": false,
            "is_password": false,
            "advanced": false,
            "examples": [{"value": "AWS", "help": "Amazon Web Services"}, ...]
        },
        ...
    ],
    ...
}
"""

import json
import subprocess
import sys


def get_rclone_providers(filter_types=None):
    """Get provider options from rclone using 'rclone config providers'."""
    try:
        result = subprocess.run(
            ["rclone", "config", "providers"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=30
        )
        if result.returncode != 0:
            print(json.dumps({"error": f"rclone failed: {result.stderr.strip()}"}))
            sys.exit(1)

        data = json.loads(result.stdout)

        providers = {}
        for provider in data:
            ptype = provider.get("Prefix", provider.get("Name", ""))
            if filter_types and ptype not in filter_types:
                continue

            # Deduplicate options by name.
            # Some backends (notably S3) have provider-specific variants of the
            # same option (e.g. "region" appears 12 times, once per sub-provider).
            # We merge them: keep one entry per name, combine all examples, and
            # record which sub-providers each variant targets.
            seen = {}  # name -> merged option dict
            for opt in provider.get("Options", []):
                name = opt.get("Name", "")
                sub_provider = opt.get("Provider", "")

                if name not in seen:
                    option = {
                        "name": name,
                        "help": (opt.get("Help", "") or "").strip(),
                        "default": opt.get("Default"),
                        "type": _map_type(opt),
                        "required": opt.get("Required", False),
                        "is_password": opt.get("IsPassword", False),
                        "advanced": opt.get("Advanced", False),
                        "exclusive": opt.get("Exclusive", False),
                        "_providers": [],
                    }

                    examples = opt.get("Examples")
                    if examples:
                        option["examples"] = [
                            {"value": ex.get("Value", ""), "help": ex.get("Help", ""),
                             "provider": ex.get("Provider", sub_provider)}
                            for ex in examples
                        ]
                    else:
                        option["examples"] = []

                    if sub_provider:
                        option["_providers"].append(sub_provider)

                    seen[name] = option
                else:
                    # Merge: add examples from this variant
                    existing = seen[name]
                    examples = opt.get("Examples")
                    if examples:
                        for ex in examples:
                            existing["examples"].append({
                                "value": ex.get("Value", ""),
                                "help": ex.get("Help", ""),
                                "provider": ex.get("Provider", sub_provider),
                            })
                    if sub_provider:
                        existing["_providers"].append(sub_provider)
                    # Use the longer help text
                    new_help = (opt.get("Help", "") or "").strip()
                    if len(new_help) > len(existing["help"]):
                        existing["help"] = new_help

            # Build final options list, dedup examples by value
            options = []
            for opt in seen.values():
                # Deduplicate examples by value
                if opt.get("examples"):
                    seen_vals = set()
                    deduped = []
                    for ex in opt["examples"]:
                        if ex["value"] not in seen_vals:
                            seen_vals.add(ex["value"])
                            deduped.append({"value": ex["value"], "help": ex["help"]})
                    opt["examples"] = deduped if deduped else None
                else:
                    opt["examples"] = None

                # Store sub-provider info for filtering
                if opt["_providers"]:
                    opt["providers"] = list(set(opt["_providers"]))
                del opt["_providers"]

                # Remove examples key if None
                if opt["examples"] is None:
                    del opt["examples"]

                options.append(opt)

            providers[ptype] = {
                "name": provider.get("Name", ptype),
                "description": provider.get("Description", ""),
                "options": options,
            }

        print(json.dumps(providers))

    except FileNotFoundError:
        print(json.dumps({"error": "rclone not found in PATH"}))
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(json.dumps({"error": "rclone timed out"}))
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Failed to parse rclone output: {str(e)}"}))
        sys.exit(1)


def _map_type(opt):
    """Map rclone option types to UI-friendly types."""
    # If there are examples with Value fields, treat as select
    examples = opt.get("Examples", [])
    exclusive = opt.get("Exclusive", False)
    if exclusive and examples:
        return "select"

    # Check the Type field from rclone
    rtype = opt.get("Type", "string")
    if rtype == "bool":
        return "bool"
    elif rtype in ("int", "SizeSuffix", "Duration"):
        return rtype.lower()
    elif rtype == "SpaceSepList" or rtype == "CommaSepList":
        return "string"

    return "string"


def main():
    filter_types = None
    args = sys.argv[1:]

    i = 0
    while i < len(args):
        if args[i] == "--providers" and i + 1 < len(args):
            filter_types = set(args[i + 1].split(","))
            i += 2
        else:
            i += 1

    get_rclone_providers(filter_types)


if __name__ == "__main__":
    main()
