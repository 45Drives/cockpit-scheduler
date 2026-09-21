#!/usr/bin/env bash
set -euo pipefail

# systemd run-timestamp semantics harness.
#
# The LogView "finished before it started" bug and its fix both rest on claims
# about when systemd updates each timestamp property. This harness proves those
# claims on the actual host kernel/systemd instead of taking them on faith, using
# a throwaway unit that mirrors templates/Task.service (Type=notify, NotifyAccess=all,
# Restart=on-failure, RestartPreventExitStatus=90).
#
# Claims under test:
#   1. ExecMainExitTimestamp is CLEARED while a new main process is alive, so
#      falling back to InactiveEnterTimestamp pairs this run's start with the
#      PREVIOUS run's stop and renders a negative duration.
#   2. InactiveExitTimestamp is NOT reset by Restart=on-failure retries, so it is
#      the true start of the whole run while ExecMainStartTimestamp is only the
#      last attempt.
#   3. NRestarts is cleared on every explicit start and counts retries in the
#      current cycle.
#
# Run as root on any systemd host. Nothing here touches real scheduler units.

usage() {
  cat <<'EOF'
Usage:
  timestamp-semantics-harness.sh midrun     prove claim 1 (the reported bug)
  timestamp-semantics-harness.sh retries    prove claims 2 and 3
  timestamp-semantics-harness.sh all        both scenarios, then clean up
  timestamp-semantics-harness.sh parse      feed the last capture through pairRunTimestamps
  timestamp-semantics-harness.sh clean      remove the probe unit and its files

Environment:
  RUN_SECONDS   how long one attempt sleeps (default 20)
  RESTART_SEC   RestartSec for the probe unit (default 10)
  FAIL_UNTIL    attempts that exit 1 before one succeeds (default 3, retries only)
EOF
}

UNIT='houston-ts-probe.service'
UNIT_PATH="/etc/systemd/system/${UNIT}"
SCRIPT_PATH='/usr/local/lib/houston-ts-probe.sh'
COUNT_FILE='/run/houston-ts-probe.attempts'
CAPTURE='/tmp/houston-ts-probe.capture'

RUN_SECONDS="${RUN_SECONDS:-20}"
RESTART_SEC="${RESTART_SEC:-10}"
FAIL_UNTIL="${FAIL_UNTIL:-3}"

failures=0

say()  { printf '%s\n' "$*"; }
pass() { printf '  ok    %s\n' "$*"; }
fail() { failures=$((failures + 1)); printf '  FAIL  %s\n' "$*"; }

require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    say 'Must run as root (it writes a unit file and drives systemctl).' >&2
    exit 1
  fi
}

install_probe() {
  cat >"${SCRIPT_PATH}" <<'PROBE'
#!/bin/sh
# Announces readiness like the real task scripts, then burns time and either
# fails (so systemd retries) or succeeds.
systemd-notify --ready 2>/dev/null || true
n=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" >"$COUNT_FILE"
echo "probe attempt $n (fail_until=$FAIL_UNTIL, sleep=$RUN_SECONDS)"
sleep "$RUN_SECONDS"
if [ "$n" -lt "$FAIL_UNTIL" ]; then
    echo "probe attempt $n failing on purpose" >&2
    exit 1
fi
echo "probe attempt $n succeeded"
exit 0
PROBE
  chmod 0755 "${SCRIPT_PATH}"

  cat >"${UNIT_PATH}" <<UNITFILE
[Unit]
Description=Houston scheduler timestamp semantics probe
StartLimitBurst=10
StartLimitIntervalSec=0

[Service]
Type=notify
NotifyAccess=all
Environment=COUNT_FILE=${COUNT_FILE}
Environment=RUN_SECONDS=${RUN_SECONDS}
Environment=FAIL_UNTIL=${FAIL_UNTIL}
StandardOutput=journal
StandardError=journal
ExecStart=${SCRIPT_PATH}
Restart=on-failure
RestartSec=${RESTART_SEC}sec
RestartPreventExitStatus=90
TimeoutStartSec=0
TimeoutStopSec=90
UNITFILE

  systemctl daemon-reload
}

reset_probe() {
  systemctl stop "${UNIT}" >/dev/null 2>&1 || true
  systemctl reset-failed "${UNIT}" >/dev/null 2>&1 || true
  rm -f "${COUNT_FILE}"
}

props() {
  systemctl show "${UNIT}" --no-pager -p \
    ActiveState,SubState,Result,NRestarts,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp,ActiveEnterTimestamp,InactiveEnterTimestamp,InactiveExitTimestamp,ExecMainStartTimestampUSec,ExecMainExitTimestampUSec,InactiveEnterTimestampUSec,InactiveExitTimestampUSec
}

prop() { systemctl show "${UNIT}" -p "$1" --value; }

# systemd renders an unset *USec property as 0 or as the string "0"/"n/a".
us() {
  local v
  v="$(prop "$1")"
  case "${v}" in
    ''|n/a|0) echo 0 ;;
    *[!0-9]*) echo 0 ;;
    *) echo "${v}" ;;
  esac
}

wait_for_state() {
  local want="$1" limit="${2:-600}" waited=0
  while [[ "$(prop ActiveState)" != "${want}" ]]; do
    sleep 1
    waited=$((waited + 1))
    if (( waited >= limit )); then
      say "  timed out waiting for ActiveState=${want} (currently $(prop ActiveState))" >&2
      return 1
    fi
  done
}

capture() {
  props >"${CAPTURE}"
  say ''
  say "  captured -> ${CAPTURE}"
  sed 's/^/    /' "${CAPTURE}"
  say ''
}

scenario_midrun() {
  say ''
  say 'Claim 1: a live run has no ExecMainExitTimestamp, so the old fallback'
  say '         paired it with the PREVIOUS run{s stop.' | tr '{' "'"
  reset_probe
  FAIL_UNTIL=0 install_probe

  say "  run 1: starting (sleeps ${RUN_SECONDS}s, succeeds)"
  systemctl start "${UNIT}"
  wait_for_state inactive
  local first_exit first_inactive
  first_exit="$(us ExecMainExitTimestampUSec)"
  first_inactive="$(us InactiveEnterTimestampUSec)"
  say "  run 1 finished: ExecMainExit=$(prop ExecMainExitTimestamp)"

  if (( first_exit > 0 )); then
    pass 'a completed run does record ExecMainExitTimestamp'
  else
    fail 'completed run left ExecMainExitTimestamp empty'
  fi

  say "  run 2: starting, sampling ${RUN_SECONDS}s mid-flight"
  systemctl start "${UNIT}"
  sleep 3
  capture

  local live_start live_exit live_inactive
  live_start="$(us ExecMainStartTimestampUSec)"
  live_exit="$(us ExecMainExitTimestampUSec)"
  live_inactive="$(us InactiveEnterTimestampUSec)"

  if (( live_exit == 0 )); then
    pass 'ExecMainExitTimestamp is cleared while the main process is alive'
  else
    fail "ExecMainExitTimestamp is populated mid-run (${live_exit})"
  fi

  if (( live_inactive == first_inactive && live_inactive > 0 )); then
    pass 'InactiveEnterTimestamp still holds the PREVIOUS cycle value'
  else
    fail 'InactiveEnterTimestamp did not retain the previous cycle value'
  fi

  if (( live_start > live_inactive )); then
    pass "old fallback would render $(( (live_start - live_inactive) / 1000000 ))s of time travel"
  else
    fail 'could not reproduce the negative duration'
  fi

  say '  letting run 2 finish...'
  wait_for_state inactive
}

scenario_retries() {
  say ''
  say 'Claims 2 and 3: InactiveExitTimestamp survives Restart=on-failure;'
  say '                ExecMainStartTimestamp does not; NRestarts counts them.'
  reset_probe
  install_probe

  local expected_restarts=$((FAIL_UNTIL - 1))
  say "  starting: ${FAIL_UNTIL} attempts, ${RUN_SECONDS}s each, RestartSec=${RESTART_SEC}"
  systemctl start "${UNIT}"
  sleep 2
  local cycle_start_seen
  cycle_start_seen="$(us InactiveExitTimestampUSec)"
  say "  cycle start observed at first attempt: $(prop InactiveExitTimestamp)"

  local limit=$(( (RUN_SECONDS + RESTART_SEC + 10) * (FAIL_UNTIL + 1) ))
  local waited=0
  while [[ "$(prop ActiveState)" == 'active' || "$(prop ActiveState)" == 'activating' ]]; do
    sleep 1
    waited=$((waited + 1))
    (( waited < limit )) || break
  done
  capture

  local restarts cycle_start attempt_start finish
  restarts="$(prop NRestarts)"
  cycle_start="$(us InactiveExitTimestampUSec)"
  attempt_start="$(us ExecMainStartTimestampUSec)"
  finish="$(us ExecMainExitTimestampUSec)"

  if [[ "${restarts}" == "${expected_restarts}" ]]; then
    pass "NRestarts=${restarts} matches the ${expected_restarts} forced failures"
  else
    fail "NRestarts=${restarts}, expected ${expected_restarts}"
  fi

  if (( cycle_start > 0 && cycle_start == cycle_start_seen )); then
    pass 'InactiveExitTimestamp is unchanged across every retry'
  else
    fail 'InactiveExitTimestamp moved during the retry cycle'
  fi

  if (( attempt_start > cycle_start )); then
    pass "ExecMainStartTimestamp advanced to the last attempt (+$(( (attempt_start - cycle_start) / 1000000 ))s)"
  else
    fail 'ExecMainStartTimestamp did not advance past the cycle start'
  fi

  if (( finish >= attempt_start )); then
    pass "attempt duration $(( (finish - attempt_start) / 1000000 ))s vs total $(( (finish - cycle_start) / 1000000 ))s"
  else
    fail 'ExecMainExitTimestamp is before ExecMainStartTimestamp after settling'
  fi
}

# Runs the captured properties through the shipping parser so the harness proves
# the code path, not just the systemd behaviour.
scenario_parse() {
  if [[ ! -s "${CAPTURE}" ]]; then
    say "No capture at ${CAPTURE}. Run midrun or retries first." >&2
    exit 1
  fi
  if ! command -v node >/dev/null 2>&1; then
    say "node not found on this host. Copy ${CAPTURE} to a dev box and run:" >&2
    say "  node tests/timestamp-semantics-harness.mjs <capture>" >&2
    exit 1
  fi

  local repo
  repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  CAPTURE="${CAPTURE}" node --input-type=module -e "
import { readFileSync } from 'node:fs';
import { pairRunTimestamps, isUnitRunning, parseRestartCount } from '${repo}/scheduler/src/models/systemdParsing.ts';

const kv = Object.fromEntries(
    readFileSync(process.env.CAPTURE, 'utf8')
        .split('\n')
        .filter((l) => l.includes('='))
        .map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)])
);
const running = isUnitRunning(kv.ActiveState);
console.log(JSON.stringify({
    activeState: kv.ActiveState,
    running,
    restarts: parseRestartCount(kv.NRestarts),
    ...pairRunTimestamps(kv, running),
}, null, 2));
"
}

clean() {
  reset_probe
  rm -f "${UNIT_PATH}" "${SCRIPT_PATH}" "${CAPTURE}"
  systemctl daemon-reload
  say "Removed ${UNIT}."
}

case "${1:-}" in
  midrun)  require_root; scenario_midrun ;;
  retries) require_root; scenario_retries ;;
  all)     require_root; scenario_midrun; scenario_retries; clean ;;
  parse)   scenario_parse ;;
  clean)   require_root; clean ;;
  *)       usage; exit 1 ;;
esac

if (( failures )); then
  say ''
  say "${failures} failure(s) — the timestamp assumptions do not hold on this systemd."
  exit 1
fi

if [[ "${1:-}" != 'parse' && "${1:-}" != 'clean' ]]; then
  say ''
  say 'all checks passed'
fi
