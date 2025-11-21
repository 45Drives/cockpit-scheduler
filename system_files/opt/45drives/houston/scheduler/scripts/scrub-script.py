#!/usr/bin/env python3
import subprocess
import sys
import os
import re
import time

from notify import get_notifier

notifier = get_notifier()
SCAN_RE = re.compile(r"scan:\s+(?P<state>[\w\s]+)\s+(?P<rest>.*)", re.IGNORECASE)
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)%")

def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)

def start_scrub(pool: str):
    notifier.notify(f"STATUS=Starting scrub on pool {pool}…")
    p = run(["zpool", "scrub", pool])
    if p.returncode != 0:
        msg = p.stderr.strip() or p.stdout.strip() or "zpool scrub failed"
        print(f"ERROR: {msg}")
        notifier.notify(f"STATUS=Scrub start failed on {pool}: {msg}")
        sys.exit(1)
    print(f"Scrub requested on pool {pool}")

def get_scrub_progress(pool: str):
    p = run(["zpool", "status", pool])
    if p.returncode != 0:
        msg = p.stderr.strip() or p.stdout.strip()
        print(f"ERROR: zpool status {pool}: {msg}")
        return None, None

    for line in p.stdout.splitlines():
        m = SCAN_RE.search(line)
        if not m:
            continue
        state = m.group("state").strip().lower()
        rest = m.group("rest")

        pct = None
        m2 = PCT_RE.search(rest)
        if m2:
            try:
                pct = float(m2.group(1))
            except ValueError:
                pct = None

        return state, pct

    return None, None

def main():
    pool = os.environ.get("scrubConfig_pool_pool", "").strip()
    if not pool:
        msg = "No pool specified for scrubConfig_pool_pool"
        print(f"ERROR: {msg}")
        notifier.notify(f"STATUS={msg}")
        sys.exit(1)

    notifier.notify("STATUS=Starting scrub task…")
    notifier.notify("READY=1")
    notifier.notify("STATUS=Triggering scrub…")

    start_scrub(pool)

    # Poll progress until scrub is done
    last_pct_int = None
    while True:
        state, pct = get_scrub_progress(pool)
        if state is None:
            # Could not parse; just sleep a bit and retry
            time.sleep(5)
            continue

        if "in progress" in state or "resilver" in state:
            if pct is not None:
                pct_int = int(pct)
                if pct_int != last_pct_int:
                    last_pct_int = pct_int
                    notifier.notify(f"STATUS=Scrubbing {pool}… {pct_int}% complete")
            else:
                notifier.notify(f"STATUS=Scrubbing {pool}… in progress")
            time.sleep(10)
            continue

        # Not in progress anymore; treat as done or failed depending on state text
        if "completed" in state or "repaired" in state or "scrubbed" in state:
            notifier.notify(f"STATUS=Scrub on {pool} completed.")
            print(f"Scrub on {pool} completed.")
            break
        elif "canceled" in state or "cancelled" in state:
            notifier.notify(f"STATUS=Scrub on {pool} was canceled.")
            print(f"Scrub on {pool} was canceled.")
            break
        else:
            notifier.notify(f"STATUS=Scrub on {pool} ended: {state}")
            print(f"Scrub on {pool} ended: {state}")
            break

    sys.exit(0)


if __name__ == "__main__":
    main()
