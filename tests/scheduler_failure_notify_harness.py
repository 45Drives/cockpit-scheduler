#!/usr/bin/env python3
"""Live harness for Task Scheduler failure notifications.

Reproduces the "failed tasks never notify" report: the final attempt of a failing
task exits with NO_RETRY_EXIT_CODE (90), which the unit lists in
RestartPreventExitStatus, so systemd never logs "Start request repeated too
quickly" / "Failed to start" and houston-scheduler-monitor used to wait forever.

Each scenario renders a throwaway CustomTask unit from the installed
templates/Task.service, runs it through the real run-custom-task.py and
task_retry.py, then checks three things:
  - what systemd recorded (Result, ExecMainStatus, NRestarts)
  - what houston-scheduler-monitor logged ("Notification sent: ...")
  - what landed in the cockpit-alerts DB (notifications table)

Units live under /run/systemd/system so they never show in the scheduler UI and
vanish on reboot. Failure scenarios raise real alerts (and emails, if the
schedulerTaskFailure level routes to a receiver group).

Run as root on an appliance with cockpit-scheduler and cockpit-alerts installed.
This is a manual harness, not a pytest module; pytest does not collect it.
"""

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

SCHED_DIR = Path("/opt/45drives/houston/scheduler")
TEMPLATE = SCHED_DIR / "templates" / "Task.service"
RUNNER = SCHED_DIR / "scripts" / "run-custom-task.py"
MONITOR_UNIT = "houston-scheduler-monitor.service"
ALERTS_DB = Path("/var/lib/sqlite/45drives/notifications.db")
UNIT_DIR = Path("/run/systemd/system")
WORK_DIR = Path("/run/houston-notify-harness")
NAME_PREFIX = "HarnessNotify"

NO_RETRY_EXIT_CODE = 90
FAILURE = "scheduler_task_failure"
SUCCESS = "scheduler_task_success"

# The probe is what the Custom Task runs. Modes:
#   fail     always exit 1
#   succeed  always exit 0
#   recover  exit 1 on the first attempt, 0 afterwards
PROBE_SOURCE = '''\
#!/usr/bin/python3
import sys
mode, counter = sys.argv[1], sys.argv[2]
try:
    n = int(open(counter).read().strip() or 0)
except (OSError, ValueError):
    n = 0
n += 1
open(counter, "w").write(str(n))
print("harness probe: mode=%s attempt=%d" % (mode, n))
if mode == "fail" or (mode == "recover" and n < 2):
    print("harness probe: failing on purpose", file=sys.stderr)
    sys.exit(1)
sys.exit(0 if mode in ("succeed", "recover") else 2)
'''

# probe mode, systemd start-limit burst (max attempts), expected outcome
Scenario = namedtuple(
    "Scenario",
    "label mode max_attempts event retries exit_status error_contains",
)

SCENARIOS = {
    "single": Scenario("single", "fail", 1, FAILURE, 0, NO_RETRY_EXIT_CODE, "Exit code: 90"),
    "retries": Scenario("retries", "fail", 3, FAILURE, 2, NO_RETRY_EXIT_CODE, "Exit code: 90"),
    "success": Scenario("success", "succeed", 3, SUCCESS, 0, 0, None),
    "recover": Scenario("recover", "recover", 3, SUCCESS, 0, 0, None),
}

PLACEHOLDER = re.compile(r"\{[A-Za-z_]+\}")


class Harness:
    def __init__(self, args):
        self.args = args
        self.failures = 0

    def ok(self, msg):
        print("  ok    " + msg)

    def fail(self, msg):
        self.failures += 1
        print("  FAIL  " + msg)

    def check(self, condition, label, passed, failed):
        if condition:
            self.ok("%s: %s" % (label, passed))
        else:
            self.fail("%s: %s" % (label, failed))

    # --- systemd / journal / db helpers -------------------------------------

    @staticmethod
    def run(cmd, check=False):
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=check,
        )

    def show(self, unit, *props):
        cmd = ["systemctl", "show", unit]
        for prop in props:
            cmd += ["-p", prop]
        values = {}
        for line in self.run(cmd).stdout.splitlines():
            key, _, value = line.partition("=")
            values[key] = value
        return values

    def wait_settled(self, unit):
        """Wait for a terminal state with no pending job.

        --no-block only queues the start job, so the unit's previous inactive or
        failed state is not a result. ActiveState and Job are read in one
        snapshot; systemctl prints an empty Job= when no job is queued.
        """
        deadline = time.monotonic() + self.args.settle_timeout
        while time.monotonic() < deadline:
            props = self.show(unit, "ActiveState", "Job")
            if not props.get("Job") and props.get("ActiveState") in ("failed", "inactive"):
                return True
            time.sleep(1)
        return False

    def monitor_lines(self, since_epoch, event, task_name):
        out = self.run(
            ["journalctl", "-u", MONITOR_UNIT, "--since", "@%d" % since_epoch,
             "--no-pager", "-o", "cat"]
        ).stdout
        needle = "Notification sent: %s for %s (" % (event, task_name)
        return [line for line in out.splitlines() if needle in line]

    @staticmethod
    def db_rows(since_iso, event, task_name):
        conn = sqlite3.connect(str(ALERTS_DB))
        try:
            return conn.execute(
                "SELECT errors FROM notifications "
                "WHERE event = ? AND taskName = ? AND timestamp >= ?",
                (event, task_name, since_iso),
            ).fetchall()
        finally:
            conn.close()

    # --- setup / teardown ---------------------------------------------------

    def require_env(self):
        if os.geteuid() != 0:
            sys.exit("Must run as root (it writes unit files and drives systemctl).")
        missing = [str(p) for p in (TEMPLATE, RUNNER, ALERTS_DB) if not p.exists()]
        if missing:
            sys.exit("missing: " + ", ".join(missing))
        if self.run(["systemctl", "is-active", "--quiet", MONITOR_UNIT]).returncode != 0:
            sys.exit("%s is not active; start it first." % MONITOR_UNIT)

    def install_probe(self):
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        probe = WORK_DIR / "probe.py"
        probe.write_text(PROBE_SOURCE)
        probe.chmod(0o755)

    def write_unit(self, name, max_attempts, mode):
        unit = "houston_scheduler_CustomTask_%s" % name
        env_path = WORK_DIR / ("%s.env" % unit)
        counter = WORK_DIR / ("%s.count" % name)
        values = {
            "task_name": name,
            "zfs_dependencies": "",
            "start_limit_burst": str(max_attempts),
            "start_limit_interval_sec": "3600",
            "env_path": str(env_path),
            "ExecStart": "/usr/bin/python3 %s %s %s %s" % (
                RUNNER, WORK_DIR / "probe.py", mode, counter),
            "restart_sec": str(self.args.restart_sec),
        }
        text = TEMPLATE.read_text()
        for key, value in values.items():
            text = text.replace("{%s}" % key, value)
        leftover = PLACEHOLDER.findall(text)
        if leftover:
            sys.exit("unrendered placeholder(s) in %s: %s" % (TEMPLATE, ", ".join(leftover)))
        env_path.write_text("taskName=%s\n" % name)
        (UNIT_DIR / ("%s.service" % unit)).write_text(text)
        if counter.exists():
            counter.unlink()

    def clean(self):
        for path in sorted(UNIT_DIR.glob("houston_scheduler_CustomTask_%s_*.service" % NAME_PREFIX)):
            self.run(["systemctl", "stop", path.name])
            self.run(["systemctl", "reset-failed", path.name])
            path.unlink()
        self.run(["systemctl", "daemon-reload"])
        shutil.rmtree(str(WORK_DIR), ignore_errors=True)
        if self.args.purge_alerts:
            conn = sqlite3.connect(str(ALERTS_DB))
            try:
                with conn:
                    conn.execute(
                        "DELETE FROM notifications WHERE taskName LIKE ? ESCAPE '\\'",
                        (NAME_PREFIX + "\\_%",),
                    )
            finally:
                conn.close()
            print("purged harness rows from %s" % ALERTS_DB)
        print("cleaned up harness units")

    # --- scenarios ----------------------------------------------------------

    def run_scenario(self, sc):
        name = "%s_%s" % (NAME_PREFIX, sc.label)
        unit = "houston_scheduler_CustomTask_%s.service" % name
        label = sc.label
        other_event = SUCCESS if sc.event == FAILURE else FAILURE

        print("\n== %s: max_attempts=%d mode=%s (expect %s, retries=%d)" % (
            label, sc.max_attempts, sc.mode, sc.event, sc.retries))
        self.write_unit(name, sc.max_attempts, sc.mode)
        self.run(["systemctl", "daemon-reload"])
        self.run(["systemctl", "reset-failed", unit])

        since_epoch = int(time.time())
        since_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        time.sleep(1)
        self.run(["systemctl", "start", "--no-block", unit])

        if not self.wait_settled(unit):
            self.fail("%s: unit did not settle within %ds" % (label, self.args.settle_timeout))
            print(self.run(["systemctl", "status", "--no-pager", unit]).stdout)
            return

        props = self.show(unit, "Result", "ExecMainStatus", "NRestarts")
        print("  systemd: Result=%s ExecMainStatus=%s NRestarts=%s" % (
            props["Result"], props["ExecMainStatus"], props["NRestarts"]))
        self.check(props["ExecMainStatus"] == str(sc.exit_status), label,
                   "final attempt exited %d" % sc.exit_status,
                   "final attempt exited %s, expected %d" % (props["ExecMainStatus"], sc.exit_status))

        deadline = time.monotonic() + self.args.notify_wait
        while time.monotonic() < deadline and not self.monitor_lines(since_epoch, sc.event, name):
            time.sleep(1)
        # Keep watching so a duplicate or unexpected notification is caught too.
        time.sleep(self.args.quiet_wait)
        sent = self.monitor_lines(since_epoch, sc.event, name)
        unexpected = self.monitor_lines(since_epoch, other_event, name)

        self.check(len(sent) == 1, label, "monitor sent exactly one %s" % sc.event,
                   "monitor sent %d %s notification(s), expected 1" % (len(sent), sc.event))
        for line in sent:
            print("  monitor: " + line)
        if sent:
            self.check(sent[0].endswith("retries=%d" % sc.retries), label,
                       "reported retries=%d" % sc.retries,
                       "retry count wrong, expected retries=%d" % sc.retries)
        self.check(not unexpected, label, "no %s sent" % other_event,
                   "unexpected %s: %s" % (other_event, "; ".join(unexpected)))

        rows = self.db_rows(since_iso, sc.event, name)
        self.check(len(rows) == 1, label, "one %s row in alerts DB" % sc.event,
                   "%d %s row(s) in alerts DB, expected 1" % (len(rows), sc.event))
        if sc.error_contains and len(rows) == 1:
            errors = rows[0][0] or ""
            self.check(sc.error_contains in errors, label,
                       "alert error text %r" % errors,
                       "alert error text %r lacks %r" % (errors, sc.error_contains))


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Live check that failed Task Scheduler runs raise notifications.")
    parser.add_argument(
        "command", choices=sorted(SCENARIOS) + ["all", "clean"],
        help="single: fail with max attempts 1; retries: fail every attempt (3); "
             "success: succeed first time; recover: fail once then succeed; "
             "all: every scenario then clean up; clean: remove harness units")
    parser.add_argument("--restart-sec", type=int, default=3,
                        help="RestartSec for the probe units (default 3)")
    parser.add_argument("--settle-timeout", type=int, default=120,
                        help="seconds to wait for a unit to settle (default 120)")
    parser.add_argument("--notify-wait", type=int, default=20,
                        help="seconds to wait for the monitor to report (default 20)")
    parser.add_argument("--quiet-wait", type=int, default=8,
                        help="extra seconds to watch for unexpected notifications (default 8)")
    parser.add_argument("--purge-alerts", action="store_true",
                        help="with clean/all, also delete the harness rows from the alerts DB")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    harness = Harness(args)
    harness.require_env()

    if args.command == "clean":
        harness.clean()
        return 0

    harness.install_probe()
    started = harness.show(MONITOR_UNIT, "ActiveEnterTimestamp")["ActiveEnterTimestamp"]
    print("monitor active since %s (restart it after deploying a patched scheduler-monitor.py)"
          % started)

    names = list(SCENARIOS) if args.command == "all" else [args.command]
    for name in names:
        harness.run_scenario(SCENARIOS[name])
    if args.command == "all":
        harness.clean()

    print()
    if harness.failures:
        print("FAIL: %d check(s) failed" % harness.failures)
        return 1
    print("PASS: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
