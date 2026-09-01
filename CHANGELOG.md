## task scheduler 1.7.9-1

* fix: stop scheduler tasks looping forever on repeated failures

systemd's StartLimitBurst/StartLimitIntervalSec pair cannot bound retries for
a unit whose runtime is unbounded. The rate-limit window only counts starts,
so once a run takes longer than the window the limiter never trips and
Restart=on-failure retries indefinitely. A customer task reached 62 restarts,
and because the unit sat in activating (auto-restart) it never returned to
inactive, so its timer could not fire the next scheduled run and the UI
reported it as running forever.

Attempts are now counted from systemd's own NRestarts, which resets on every
explicit or timer start and persists across automatic restarts. The final
attempt exits 90, listed in RestartPreventExitStatus, so the unit settles
into failed and normal scheduling resumes.

- add replication/retry.py and task_retry.py sharing the exit-90 contract
- route replication/main.py exits through the retry policy
- apply retry accounting to the autosnap, cloudsync, rsync, scrub, smart-test
  and custom task scripts
- add RestartPreventExitStatus, HOUSTON_SCHEDULER_UNIT and
  HOUSTON_SCHEDULER_MAX_ATTEMPTS to templates/Task.service
- patch the same directives into existing units via migrate-retry-settings.py

Also fixes progress appearing stuck at 99.9%. The resume pipelines waited on
zfs send and remote zfs recv for up to 1800s with no status output; all five
paths in transfers/resume.py now emit a finalize heartbeat every 15s.

Reclassify four workflow.py failures from permanent (exit 2) to retryable
(exit 1): resume-token clear failures, which are transient over SSH, and
destination snapshot name collisions, which clear on the next
second-resolution timestamp.

dbg() no longer discards write errors silently, so an unwritable debug log
reports itself to the journal instead of leaving an empty file and no
explanation.

change: default Include Intermediate Snapshots to off for new ZFS replication tasks