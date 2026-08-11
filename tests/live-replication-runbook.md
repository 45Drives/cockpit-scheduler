# Live Replication Harness Runbook

This is the complete live-test guide for `live-replication-harness.sh`.

It covers every harness command, what each command tests, when to use it, and what output means pass/fail.

## 1) Scope and safety

Run these tests only on disposable or non-production datasets.

All commands below assume you are already on the server and running as `root`.

```bash
cd /opt/45drives/houston/scheduler/tests
```

## 2) Quick setup variables

Set these once per session and reuse.

```bash
TASK=TaskName
DEST=pool/dataset
REMOTE_USER=root
REMOTE_HOST=192.168.X.X
REMOTE_PORT=22
UNIT="houston_scheduler_ZfsReplicationTask_${TASK}.service"
```

## 3) Full command reference

### 3.1 `preflight [pool]`

Command:

```bash
./live-replication-harness.sh preflight
./live-replication-harness.sh preflight tank
```

What it does:
- Verifies runtime dependencies and pool health (`python3`, `zfs`, `mbuffer`, `pv`, `nc`, `zpool status`).

What it tests:
- Host readiness for live replication tests.

Pass signals:
- Tools print versions/help successfully.
- `zpool status` reports healthy or expected state.

Fail signals:
- Missing binaries, unhealthy pools, or obvious runtime errors.

### 3.2 `start <task_name>`

Command:

```bash
./live-replication-harness.sh start "$TASK"
```

What it does:
- Starts the task service unit.

What it tests:
- Unit starts and enters normal lifecycle.

Pass signals:
- `started <unit>` output and active/running status soon after.

### 3.3 `stop <task_name>`

Command:

```bash
./live-replication-harness.sh stop "$TASK"
```

What it does:
- Stops the task service unit.

What it tests:
- Operator stop path and service termination behavior.

### 3.4 `status <task_name>`

Command:

```bash
./live-replication-harness.sh status "$TASK"
```

What it does:
- Shows key systemd properties (`ActiveState`, `SubState`, `Result`, `ExecMainStatus`, `StatusText`).

What it tests:
- Current state machine position and last run result.

### 3.5 `logs <task_name> [lines]`

Command:

```bash
./live-replication-harness.sh logs "$TASK"
./live-replication-harness.sh logs "$TASK" 300
```

What it does:
- Shows recent journald lines for the task unit.

What it tests:
- Detailed diagnosis of snapshot planning, send/recv, resume, and failures.

### 3.6 `set-flag <task_name> <dryRun|forceFullSend|resumeOnly> <true|false>`

Command:

```bash
./live-replication-harness.sh set-flag "$TASK" dryRun true
./live-replication-harness.sh set-flag "$TASK" forceFullSend true
./live-replication-harness.sh set-flag "$TASK" resumeOnly true
```

What it does:
- Mutates one-shot flags in `/etc/systemd/system/...env` and reloads systemd.

What it tests:
- One-shot control plane behavior before a run.

### 3.7 `clear-one-shots <task_name>`

Command:

```bash
./live-replication-harness.sh clear-one-shots "$TASK"
```

What it does:
- Sets all one-shot flags to `false`.

What it tests:
- Baseline state reset before scenario tests.

### 3.8 `token-local <dest_dataset>`

Command:

```bash
./live-replication-harness.sh token-local "$DEST"
```

What it does:
- Reads `receive_resume_token` from local destination dataset.

What it tests:
- Whether interrupted resumable receive state exists locally.

Pass signals:
- Long token string means resumable state exists.

Fail/neutral signals:
- `-` means no token exists.

### 3.9 `token-remote <dest_dataset> <remote_user> <remote_host> [remote_ssh_port]`

Command:

```bash
./live-replication-harness.sh token-remote "$DEST" "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_PORT"
```

What it does:
- Reads remote `receive_resume_token` over SSH.

What it tests:
- Resume token existence when destination is remote.

### 3.10 `discover-tasks`

Command:

```bash
./live-replication-harness.sh discover-tasks
```

What it does:
- Scans `/etc/systemd/system/houston_scheduler_ZfsReplicationTask_*.env` and prints each task's discovered direction, transfer method, source/destination dataset, and remote endpoint details.

What it tests:
- Whether scheduler task configuration can be auto-discovered without manually entering task names, hosts, or datasets.

### 3.11 `autotest-all [dry-run|live] [timeout_sec]`

Command:

```bash
./live-replication-harness.sh autotest-all
./live-replication-harness.sh autotest-all dry-run 900
./live-replication-harness.sh autotest-all live 1800
```

What it does:
- Auto-discovers all ZFS replication tasks and runs them sequentially with standardized checks.
- `dry-run` mode (default): clears one-shots, sets `dryRun=true`, runs each task, and validates success.
- `live` mode: clears one-shots and runs each task normally.

What it tests:
- End-to-end service start/finish and result status for every discovered task, without manual per-task input.

Pass criteria:
- `Result=success`
- `ExecMainStatus=0`

Fail criteria:
- SSH precheck failure for remote tasks.
- Timeout waiting for a task to finish.
- Non-success systemd result/exit status.

### 3.12 `get-flag <task_name> <dryRun|forceFullSend|resumeOnly>`

Command:

```bash
./live-replication-harness.sh get-flag "$TASK" dryRun
./live-replication-harness.sh get-flag "$TASK" forceFullSend
./live-replication-harness.sh get-flag "$TASK" resumeOnly
```

What it does:
- Reads the current one-shot flag value from env file.

What it tests:
- Whether one-shot flags auto-clear as expected after task runs.

### 3.13 `remote-mbuffer <remote_user> <remote_host> [remote_ssh_port]`

Command:

```bash
./live-replication-harness.sh remote-mbuffer "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_PORT"
```

What it does:
- Verifies whether `mbuffer` exists on the remote destination/source host and prints its version line.

What it tests:
- Whether two-ended mbuffer mode can activate for remote SSH/netcat transfers.

Pass signals:
- `PASS: mbuffer is installed ...`
- Version line such as `mbuffer version R20231216`

Fail signals:
- `FAIL: mbuffer is not installed ...`
- Task will still run with local-only buffering fallback.

### 3.14 `interrupt-main <task_name> [signal]`

Command:

```bash
./live-replication-harness.sh interrupt-main "$TASK"
./live-replication-harness.sh interrupt-main "$TASK" KILL
```

What it does:
- Sends signal to main process of the task service.

What it tests:
- Failure/interruption behavior, including resumable receive token creation.

## 4) Scenario tests (end-to-end)

### 4.1 `scenario-resume-token-local <task_name> <dest_dataset> [interrupt_after_sec] [token_wait_sec]`

Command:

```bash
./live-replication-harness.sh scenario-resume-token-local "$TASK" "$DEST" 25 60
```

What it does:
- Clears one-shots, starts task, waits N seconds, kills main process, and polls for local resume token.

What it tests:
- Local interrupted receive should leave resumable token.

Pass signals:
- `PASS: resume token present: <token>`

Fail signals:
- `FAIL: no resume token observed ...`

Recommended timing:
- Use 20-30 seconds for local tests.
- If prep is slow, use 30-45.
- Token wait 60 seconds is safer than 20.

### 4.2 `scenario-resume-token-remote <task_name> <dest_dataset> <remote_user> <remote_host> [remote_ssh_port] [interrupt_after_sec] [token_wait_sec]`

Command:

```bash
./live-replication-harness.sh scenario-resume-token-remote "$TASK" "$DEST" "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_PORT" 35 90
```

What it does:
- Same as local token scenario, but token polling is on remote destination over SSH.

What it tests:
- Remote resumable receive token creation after interruption.

Pass signals:
- `PASS: resume token present: <token>`

Fail signals:
- `FAIL: no remote resume token observed ...`

### 4.3 `scenario-resume-only-no-token-local <task_name> <dest_dataset> [finish_wait_sec]`

Command:

```bash
./live-replication-harness.sh scenario-resume-only-no-token-local "$TASK" "$DEST" 90
```

What it does:
- Verifies `resumeOnly=true` behavior when destination has no token.

What it tests:
- No-op resume path and one-shot auto-clear logic.

Pass criteria:
- No token before run.
- No token after run.
- `resumeOnly` flag is `false` after completion.

Fail criteria:
- Token unexpectedly appears.
- Flag does not clear.

### 4.4 `scenario-force-full-send-clears <task_name> [finish_wait_sec]`

Command:

```bash
./live-replication-harness.sh scenario-force-full-send-clears "$TASK" 900
```

What it does:
- Sets `forceFullSend=true`, runs task, waits for finish, checks success and auto-clear.

What it tests:
- One-shot force-full-send end-to-end behavior.

Pass criteria:
- Unit `Result=success`
- `ExecMainStatus=0`
- `forceFullSend=false` after run

Fail criteria:
- Run fails or flag remains set.

## 5) Known resume-token pitfalls

No token is most often caused by one of these:
- Kill happened before `zfs recv -s` accepted stream data.
- Transfer completed before interrupt.
- Dataset too small to sustain an in-flight receive.

To force token creation more reliably:

```bash
./live-replication-harness.sh clear-one-shots "$TASK"
./live-replication-harness.sh start "$TASK"
while ! pgrep -fa "zfs recv -s" >/dev/null; do sleep 1; done
sleep 8
./live-replication-harness.sh interrupt-main "$TASK" KILL
./live-replication-harness.sh token-local "$DEST"
```

If still no token, increase source change size and try again.

## 6) Two-ended mbuffer validation

Remote availability check:

```bash
./live-replication-harness.sh remote-mbuffer "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_PORT"
```

During task runs, check for one of these status lines:

- `Remote mbuffer detected ... enabling two-ended buffering`
- `Remote mbuffer not found ... using local-only buffering`

Example log filter:

```bash
./live-replication-harness.sh logs "$TASK" 400 | grep -E 'Remote mbuffer|CLI command|netcat|mbuffer'
```

## 7) Retry policy checks

Max attempts includes the first run.

- `start_limit_burst=1` means no retry run should happen.
- Service `Restart` policy should be `no` when burst is 1.

Check:

```bash
systemctl cat "$UNIT" | grep -E 'StartLimitBurst|Restart='
systemctl show "$UNIT" -p StartLimitBurst -p NRestarts -p Result -p ActiveState -p SubState
```

## 8) Distinguish systemd retry from internal script retry

```bash
journalctl -u "$UNIT" -n 250 --no-pager | grep -E 'Scheduled restart job|Start request repeated too quickly|dataset is busy|retrying in'
```

Interpretation:
- `Scheduled restart job` indicates systemd restart cycle.
- `dataset is busy ... retrying in` indicates internal script retry logic.

## 9) Cleanup and reset

```bash
systemctl stop "$UNIT" || true
systemctl reset-failed "$UNIT"
./live-replication-harness.sh clear-one-shots "$TASK"
```

Clear local resume token manually if needed:

```bash
zfs receive -A "$DEST"
zfs get -H -o value receive_resume_token "$DEST"
```

Expected after clear: `-`

## 10) Suggested execution order (full suite)

```bash
./live-replication-harness.sh preflight
./live-replication-harness.sh discover-tasks
./live-replication-harness.sh autotest-all dry-run 900
./live-replication-harness.sh remote-mbuffer "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_PORT"
./live-replication-harness.sh clear-one-shots "$TASK"
./live-replication-harness.sh scenario-resume-token-local "$TASK" "$DEST" 25 60
./live-replication-harness.sh scenario-resume-only-no-token-local "$TASK" "$DEST" 90
./live-replication-harness.sh scenario-force-full-send-clears "$TASK" 900
```

Remote variant:

```bash
./live-replication-harness.sh scenario-resume-token-remote "$TASK" "$DEST" "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_PORT" 35 90
```
