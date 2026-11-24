#!/usr/bin/env bash
set -euo pipefail

# Task Scheduler failure-notification harness.
#
# Reproduces the "failed tasks never notify" report: the final attempt of a
# failing task exits with NO_RETRY_EXIT_CODE (90), which the unit lists in
# RestartPreventExitStatus, so systemd never logs "Start request repeated too
# quickly" / "Failed to start" and houston-scheduler-monitor used to wait forever.
#
# Each scenario renders a throwaway CustomTask unit from the installed
# templates/Task.service, runs it through the real run-custom-task.py and
# task_retry.py, and then checks three things:
#   - what systemd recorded (Result, ExecMainStatus, NRestarts)
#   - what houston-scheduler-monitor logged ("Notification sent: ...")
#   - what landed in the cockpit-alerts DB (notifications table)
#
# Units live under /run/systemd/system so they never show in the scheduler UI and
# vanish on reboot. Failure scenarios raise real alerts (and emails, if the
# schedulerTaskFailure level routes to a receiver group).
#
# Run as root on an appliance with cockpit-scheduler and cockpit-alerts installed.

usage() {
  cat <<'EOF'
Usage:
  scheduler-failure-notify-harness.sh single    fail with retries disabled (max attempts 1)
  scheduler-failure-notify-harness.sh retries   fail every attempt (max attempts 3)
  scheduler-failure-notify-harness.sh success   succeed first time (regression check)
  scheduler-failure-notify-harness.sh recover   fail once, then succeed on the retry
  scheduler-failure-notify-harness.sh all       every scenario above, then clean up
  scheduler-failure-notify-harness.sh clean     remove harness units (PURGE_ALERTS=1 also
                                                deletes the harness rows from the alerts DB)

Environment:
  RESTART_SEC    RestartSec for the probe units (default 3)
  SETTLE_TIMEOUT seconds to wait for a unit to settle (default 120)
  NOTIFY_WAIT    seconds to wait for the monitor to report (default 20)
  QUIET_WAIT     extra seconds to watch for unexpected notifications (default 8)
EOF
}

SCHED_DIR='/opt/45drives/houston/scheduler'
TEMPLATE="${SCHED_DIR}/templates/Task.service"
RUNNER="${SCHED_DIR}/scripts/run-custom-task.py"
MONITOR_UNIT='houston-scheduler-monitor.service'
ALERTS_DB='/var/lib/sqlite/45drives/notifications.db'
UNIT_DIR='/run/systemd/system'
WORK_DIR='/run/houston-notify-harness'
NAME_PREFIX='HarnessNotify'

RESTART_SEC="${RESTART_SEC:-3}"
SETTLE_TIMEOUT="${SETTLE_TIMEOUT:-120}"
NOTIFY_WAIT="${NOTIFY_WAIT:-20}"
QUIET_WAIT="${QUIET_WAIT:-8}"

failures=0

say()  { printf '%s\n' "$*"; }
pass() { printf '  ok    %s\n' "$*"; }
fail() { failures=$((failures + 1)); printf '  FAIL  %s\n' "$*"; }

require_env() {
  if [[ ${EUID} -ne 0 ]]; then
    say 'Must run as root (it writes unit files and drives systemctl).' >&2
    exit 1
  fi
  local missing=0 f
  for f in "${TEMPLATE}" "${RUNNER}" "${ALERTS_DB}"; do
    [[ -e ${f} ]] || { say "missing: ${f}" >&2; missing=1; }
  done
  command -v sqlite3 >/dev/null || { say 'missing: sqlite3' >&2; missing=1; }
  ((missing == 0)) || exit 1
  if ! systemctl is-active --quiet "${MONITOR_UNIT}"; then
    say "${MONITOR_UNIT} is not active; start it first." >&2
    exit 1
  fi
}

install_probe() {
  mkdir -p "${WORK_DIR}"
  cat >"${WORK_DIR}/probe.sh" <<'PROBE'
#!/bin/sh
# probe.sh <mode> <counter-file>
#   fail     always exit 1
#   succeed  always exit 0
#   recover  exit 1 on the first attempt, 0 afterwards
n=$(cat "$2" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" >"$2"
echo "harness probe: mode=$1 attempt=$n"
case "$1" in
  fail)    echo "harness probe: failing on purpose" >&2; exit 1 ;;
  succeed) exit 0 ;;
  recover) if [ "$n" -lt 2 ]; then echo "harness probe: failing first attempt" >&2; exit 1; fi; exit 0 ;;
esac
exit 2
PROBE
  chmod 755 "${WORK_DIR}/probe.sh"
}

# write_unit <task-name> <max-attempts> <probe-mode>
write_unit() {
  local name=$1 attempts=$2 mode=$3
  local unit="houston_scheduler_CustomTask_${name}"
  local env_path="${WORK_DIR}/${unit}.env"
  local exec_start="/usr/bin/python3 ${RUNNER} ${WORK_DIR}/probe.sh ${mode} ${WORK_DIR}/${name}.count"
  local tpl
  tpl=$(<"${TEMPLATE}")
  tpl=${tpl//\{task_name\}/${name}}
  tpl=${tpl//\{zfs_dependencies\}/}
  tpl=${tpl//\{start_limit_burst\}/${attempts}}
  tpl=${tpl//\{start_limit_interval_sec\}/3600}
  tpl=${tpl//\{env_path\}/${env_path}}
  tpl=${tpl//\{ExecStart\}/${exec_start}}
  tpl=${tpl//\{restart_sec\}/${RESTART_SEC}}
  if [[ ${tpl} == *'{'*'}'* ]]; then
    say "unrendered placeholder left in ${TEMPLATE}:" >&2
    grep -o '{[a-z_]*}' <<<"${tpl}" >&2
    exit 1
  fi
  printf 'taskName=%s\n' "${name}" >"${env_path}"
  printf '%s\n' "${tpl}" >"${UNIT_DIR}/${unit}.service"
  rm -f "${WORK_DIR}/${name}.count"
}

unit_prop() { systemctl show "$1" -p "$2" --value; }

wait_settled() {
  local unit=$1 deadline=$((SECONDS + SETTLE_TIMEOUT)) state
  while ((SECONDS < deadline)); do
    state=$(unit_prop "${unit}" ActiveState)
    if [[ ${state} == failed || ${state} == inactive ]]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# monitor_count <since-epoch> <event> <task-name>
monitor_lines() {
  journalctl -u "${MONITOR_UNIT}" --since "@$1" --no-pager -o cat 2>/dev/null \
    | grep -F "Notification sent: $2 for $3 (" || true
}

db_count() {
  sqlite3 "${ALERTS_DB}" \
    "SELECT COUNT(*) FROM notifications WHERE event='$2' AND taskName='$3' AND timestamp >= '$1';"
}

# run_scenario <label> <max-attempts> <probe-mode> <expect-event> <expect-retries> <expect-exit>
run_scenario() {
  local label=$1 attempts=$2 mode=$3 want_event=$4 want_retries=$5 want_exit=$6
  local name="${NAME_PREFIX}_${label}"
  local unit="houston_scheduler_CustomTask_${name}.service"
  local other_event=scheduler_task_success
  [[ ${want_event} == scheduler_task_success ]] && other_event=scheduler_task_failure

  say ""
  say "== ${label}: max_attempts=${attempts} mode=${mode} (expect ${want_event}, retries=${want_retries})"
  write_unit "${name}" "${attempts}" "${mode}"
  systemctl daemon-reload
  systemctl reset-failed "${unit}" 2>/dev/null || true

  local since_epoch since_iso
  since_epoch=$(date +%s)
  since_iso=$(date -u +%Y-%m-%dT%H:%M:%S)
  sleep 1
  systemctl start --no-block "${unit}"

  if ! wait_settled "${unit}"; then
    fail "${label}: unit did not settle within ${SETTLE_TIMEOUT}s"
    systemctl status --no-pager "${unit}" || true
    return
  fi

  local result exec_status nrestarts
  result=$(unit_prop "${unit}" Result)
  exec_status=$(unit_prop "${unit}" ExecMainStatus)
  nrestarts=$(unit_prop "${unit}" NRestarts)
  say "  systemd: Result=${result} ExecMainStatus=${exec_status} NRestarts=${nrestarts}"
  if [[ ${exec_status} == "${want_exit}" ]]; then
    pass "${label}: final attempt exited ${want_exit}"
  else
    fail "${label}: final attempt exited ${exec_status}, expected ${want_exit}"
  fi

  local deadline=$((SECONDS + NOTIFY_WAIT)) lines=''
  while ((SECONDS < deadline)); do
    lines=$(monitor_lines "${since_epoch}" "${want_event}" "${name}")
    [[ -n ${lines} ]] && break
    sleep 1
  done
  sleep "${QUIET_WAIT}"
  lines=$(monitor_lines "${since_epoch}" "${want_event}" "${name}")
  local others
  others=$(monitor_lines "${since_epoch}" "${other_event}" "${name}")

  local count=0
  [[ -n ${lines} ]] && count=$(wc -l <<<"${lines}")
  if ((count == 1)); then
    pass "${label}: monitor sent exactly one ${want_event}"
  else
    fail "${label}: monitor sent ${count} ${want_event} notification(s), expected 1"
  fi
  [[ -n ${lines} ]] && say "  monitor: ${lines//$'\n'/$'\n  monitor: '}"

  if [[ ${count} -ge 1 ]]; then
    if grep -q "retries=${want_retries}\$" <<<"${lines}"; then
      pass "${label}: reported retries=${want_retries}"
    else
      fail "${label}: retry count wrong, expected retries=${want_retries}"
    fi
  fi

  if [[ -z ${others} ]]; then
    pass "${label}: no ${other_event} sent"
  else
    fail "${label}: unexpected ${other_event}: ${others}"
  fi

  local rows
  rows=$(db_count "${since_iso}" "${want_event}" "${name}")
  if [[ ${rows} == 1 ]]; then
    pass "${label}: one ${want_event} row in alerts DB"
  else
    fail "${label}: ${rows} ${want_event} row(s) in alerts DB, expected 1"
  fi
}

clean() {
  local f unit
  for f in "${UNIT_DIR}"/houston_scheduler_CustomTask_"${NAME_PREFIX}"_*.service; do
    [[ -e ${f} ]] || continue
    unit=$(basename "${f}")
    systemctl stop "${unit}" 2>/dev/null || true
    systemctl reset-failed "${unit}" 2>/dev/null || true
    rm -f "${f}"
  done
  systemctl daemon-reload
  rm -rf "${WORK_DIR}"
  if [[ ${PURGE_ALERTS:-0} == 1 ]]; then
    sqlite3 "${ALERTS_DB}" "DELETE FROM notifications WHERE taskName LIKE '${NAME_PREFIX}\_%' ESCAPE '\\';"
    say "purged harness rows from ${ALERTS_DB}"
  fi
  say 'cleaned up harness units'
}

scenario() {
  case "$1" in
    single)  run_scenario single  1 fail    scheduler_task_failure 0 90 ;;
    retries) run_scenario retries 3 fail    scheduler_task_failure 2 90 ;;
    success) run_scenario success 3 succeed scheduler_task_success 0 0 ;;
    recover) run_scenario recover 3 recover scheduler_task_success 0 0 ;;
    *) usage; exit 2 ;;
  esac
}

main() {
  local cmd=${1:-}
  case "${cmd}" in
    -h|--help|help|'') usage; exit 0 ;;
    clean) require_env; clean; exit 0 ;;
  esac

  require_env
  install_probe
  say "monitor: $(systemctl show "${MONITOR_UNIT}" -p ActiveEnterTimestamp --value) (restart it after deploying a patched scheduler-monitor.py)"
  if [[ ${cmd} == all ]]; then
    local s
    for s in single retries success recover; do scenario "${s}"; done
    clean
  else
    scenario "${cmd}"
  fi

  say ""
  if ((failures == 0)); then
    say 'PASS: all checks passed'
  else
    say "FAIL: ${failures} check(s) failed"
    exit 1
  fi
}

main "$@"
