#!/usr/bin/env bash
set -euo pipefail

# File-descriptor pressure harness for the Cockpit scheduler UI.
#
# Reproduces and measures the "OSError: [Errno 24] Too many open files" failure
# that cockpit-bridge hits when the scheduler's pollers spawn processes faster
# than they are reaped.
#
# The harness cannot drive the browser. It seeds disposable tasks, then samples
# every cockpit-bridge process while YOU keep the scheduler page open. It prints
# a live table and a pass/fail verdict at the end.
#
# Run as root on the scheduler host.

usage() {
  cat <<'EOF'
Usage:
  fd-pressure-harness.sh seed <count>            create <count> disposable CustomTasks
  fd-pressure-harness.sh list                    show seeded tasks
  fd-pressure-harness.sh clean                   remove every seeded task
  fd-pressure-harness.sh baseline                one-shot snapshot of bridge FD usage
  fd-pressure-harness.sh watch [secs] [interval] live monitor + verdict (default 120 1)
  fd-pressure-harness.sh exectrace [secs]        log EVERY command the bridge spawns
  fd-pressure-harness.sh busy <count>            start <count> seeded tasks so they run
  fd-pressure-harness.sh soak <count> [secs]     seed + watch + verdict, then leave tasks
  fd-pressure-harness.sh run-all [secs]          full sequence: 8 tasks, then 60, then clean
  fd-pressure-harness.sh squeeze [limit]         lower bridge RLIMIT_NOFILE (forcing function)
  fd-pressure-harness.sh unsqueeze [limit]       restore bridge RLIMIT_NOFILE (default 1024)

The two soak sizes matter because they exercise different code paths:

  8 tasks   below BULK_THRESHOLD, so the UI takes the per-task refreshOne path
            at the fastest poll interval. This is where the old per-task
            journalctl storm was worst.
  60 tasks  the batched getBulkDisplayMeta path, including the .lastrun read
            that used to be one `cat` per task.

Environment:
  GATE_LIMIT        expected max concurrent scheduler spawns (default 6)
  CHILD_FAIL        children-per-bridge that counts as a failure (default 12)
  FD_FAIL           FDs-per-bridge that counts as a failure (default 400)
  SEED_PREFIX       task name prefix (default fdtest)
  BUSY_SECONDS      how long a started task stays running (default 300)
  SEED_ENABLED      1 to also enable the generated timers (default 0, off)
  SEED_TIMERS       all | none | mixed — which tasks get a .timer (default all).
                    'mixed' gives every other task no timer, matching a real host
                    where some tasks are manual-only. getBulkDisplayMeta pairs
                    `systemctl show` output blocks to tasks by position, so this
                    is what proves a timerless unit does not shift the mapping.
  SEED_LASTRUN      none | all | mixed — seed .lastrun markers (default none).
                    'mixed' writes a marker for every other task, alternating
                    success and failed, so one batched `tail -v` call sees
                    present and missing files and both outcomes at once.

Examples:
  ./fd-pressure-harness.sh run-all
  ./fd-pressure-harness.sh soak 8 180
  ./fd-pressure-harness.sh soak 60 180
  ./fd-pressure-harness.sh busy 5
  ./fd-pressure-harness.sh exectrace 60
  ./fd-pressure-harness.sh clean

Note: a squeezed bridge that has already hit EMFILE cannot recover. Log out of
Cockpit and back in to get a fresh bridge before measuring anything.
EOF
}

# ---------------------------------------------------------------- config ----

TEMPLATE='CustomTask'
SYSTEMD_DIR='/etc/systemd/system'
SCRIPT_DIR='/opt/45drives/houston/scheduler/user_scripts'
TPL_DIR='/opt/45drives/houston/scheduler/templates'
WRAPPER='/opt/45drives/houston/scheduler/scripts/run-custom-task.py'

GATE_LIMIT="${GATE_LIMIT:-6}"
CHILD_FAIL="${CHILD_FAIL:-12}"
FD_FAIL="${FD_FAIL:-400}"
SEED_PREFIX="${SEED_PREFIX:-fdtest}"
BUSY_SECONDS="${BUSY_SECONDS:-300}"
SEED_ENABLED="${SEED_ENABLED:-0}"
SEED_TIMERS="${SEED_TIMERS:-all}"
SEED_LASTRUN="${SEED_LASTRUN:-none}"
WORK="${FDTEST_DIR:-${TMPDIR:-/tmp}/fd-pressure-harness}"

RED=$'\033[0;31m'; GRN=$'\033[0;32m'; YEL=$'\033[0;33m'; CYA=$'\033[0;36m'; BLD=$'\033[1m'; RST=$'\033[0m'

info() { printf '%s==>%s %s\n' "$CYA" "$RST" "$*"; }
warn() { printf '%s[warn]%s %s\n' "$YEL" "$RST" "$*"; }
die()  { printf '%s[fail]%s %s\n' "$RED" "$RST" "$*" >&2; exit 1; }

require_root() {
  [[ ${EUID:-$(id -u)} -eq 0 ]] || die "must run as root"
}

unit_base() { printf 'houston_scheduler_%s_%s' "$TEMPLATE" "$1"; }

# ------------------------------------------------------------ bridge info ----

bridge_pids() {
  pgrep -x cockpit-bridge 2>/dev/null || true
}

fd_count()    { ls /proc/"$1"/fd 2>/dev/null | wc -l; }
fifo_count()  { ls -l /proc/"$1"/fd 2>/dev/null | grep -c 'pipe:' || true; }
child_count() { pgrep -P "$1" 2>/dev/null | wc -l; }
proc_user()   { stat -c %U /proc/"$1" 2>/dev/null || echo '?'; }
soft_limit()  { awk -F'  +' '/Max open files/ {print $2}' /proc/"$1"/limits 2>/dev/null || echo '?'; }

pipe_inodes() {
  ls -l /proc/"$1"/fd 2>/dev/null | sed -n 's/.*pipe:\[\([0-9]*\)\].*/\1/p' | sort -u
}

child_cmds() {
  local kids
  kids=$(pgrep -P "$1" 2>/dev/null | tr '\n' ',' | sed 's/,$//')
  [[ -z "$kids" ]] && return 0
  ps -o etimes=,args= -p "$kids" 2>/dev/null || true
}

# ------------------------------------------------------------------ seed ----

write_user_script() {
  local name="$1" path="$SCRIPT_DIR/${name}.sh"
  cat >"$path" <<EOF
#!/bin/bash
# Disposable workload created by fd-pressure-harness.sh
end=\$(( SECONDS + ${BUSY_SECONDS} ))
i=0
while (( SECONDS < end )); do
  i=\$(( i + 1 ))
  echo "fdtest heartbeat \$i"
  sleep 1
done
echo "fdtest finished"
EOF
  chmod +x "$path"
}

write_env() {
  local name="$1" base="$2"
  cat >"$SYSTEMD_DIR/${base}.env" <<EOF
customTaskConfig_filePath_flag=true
customTaskConfig_command_flag=false
customTaskConfig_filePath=$SCRIPT_DIR/${name}.sh
customTaskConfig_executionMode=sequential
taskName=${name}
EOF
}

write_schedule_json() {
  local base="$1" enabled='false'
  [[ "$SEED_ENABLED" == '1' ]] && enabled='true'
  cat >"$SYSTEMD_DIR/${base}.json" <<EOF
{
  "enabled": ${enabled},
  "runOnBoot": false,
  "intervals": [
    {
      "minute": { "value": "0" },
      "hour": { "value": "4" },
      "day": { "value": "1" },
      "month": { "value": "*" },
      "year": { "value": "*" },
      "dayOfWeek": []
    }
  ]
}
EOF
}

write_service() {
  local name="$1" base="$2"
  local exec_start="python3 -u $WRAPPER bash $SCRIPT_DIR/${name}.sh"
  local locked="/bin/sh -c 'exec 9>/run/%n.lock && flock -n 9 || { echo \"Already running, skipping.\" >&2; systemd-notify --status=\"Skipped: previous run still active\" 2>/dev/null; exit 0; }; exec ${exec_start}'"

  if [[ -f "$TPL_DIR/Task.service" ]]; then
    # Same substitutions the UI's task-file-creation script performs, so the
    # generated units are byte-comparable to real ones.
    python3 - "$TPL_DIR/Task.service" "$SYSTEMD_DIR/${base}.service" \
             "${TEMPLATE}_${name}" "$SYSTEMD_DIR/${base}.env" "$locked" <<'PY'
import sys
tpl, out, task_name, env_path, exec_start = sys.argv[1:6]
c = open(tpl).read()
c = c.replace('{task_name}', task_name)
c = c.replace('{env_path}', env_path)
c = c.replace('{zfs_dependencies}', '')
c = c.replace('{restart_sec}', '5')
c = c.replace('{start_limit_burst}', '3')
c = c.replace('{start_limit_interval_sec}', '20')
c = c.replace('{ExecStart}', exec_start)
open(out, 'w').write(c)
PY
  else
    warn "missing $TPL_DIR/Task.service — writing a minimal equivalent"
    cat >"$SYSTEMD_DIR/${base}.service" <<EOF
[Unit]
Description=Service for ${TEMPLATE}_${name}
StartLimitBurst=3
StartLimitIntervalSec=20

[Service]
Type=notify
NotifyAccess=all
Environment=PYTHONUNBUFFERED=1
Environment=HOUSTON_SCHEDULER_UNIT=%n
StandardOutput=journal
StandardError=journal
EnvironmentFile=$SYSTEMD_DIR/${base}.env
ExecStart=${locked}
Restart=on-failure
RestartSec=5sec
RestartPreventExitStatus=90
TimeoutStartSec=0
TimeoutStopSec=90

[Install]
EOF
  fi
}

write_timer() {
  local base="$1"
  cat >"$SYSTEMD_DIR/${base}.timer" <<EOF
[Unit]
Description=Timer for ${base}

[Timer]
OnCalendar=*-*-01 04:00:00
Persistent=false
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF
}

write_lastrun() {
  local base="$1" outcome="$2"
  # Same format the task scripts write: "<epoch> <outcome>" on one line, so
  # `tail -n 1` in the bulk reader sees the whole record.
  printf '%s %s\n' "$(( $(date +%s) - 3600 ))" "$outcome" >"$SYSTEMD_DIR/${base}.lastrun"
}

cmd_seed() {
  require_root
  local count="${1:?count required}"
  [[ "$count" =~ ^[0-9]+$ ]] || die "count must be a number"

  case "$SEED_TIMERS" in all|none|mixed) ;; *) die "SEED_TIMERS must be all, none or mixed" ;; esac
  case "$SEED_LASTRUN" in all|none|mixed) ;; *) die "SEED_LASTRUN must be all, none or mixed" ;; esac

  [[ -f "$WRAPPER" ]] || warn "missing $WRAPPER — tasks will fail if you run them (seeding anyway)"
  mkdir -p "$SCRIPT_DIR"

  info "seeding $count disposable ${TEMPLATE}s (prefix ${SEED_PREFIX}, timers=${SEED_TIMERS}, lastrun=${SEED_LASTRUN})"
  local i name base timers=0 markers=0
  for (( i = 1; i <= count; i++ )); do
    name=$(printf '%s_%03d' "$SEED_PREFIX" "$i")
    base=$(unit_base "$name")
    write_user_script "$name"
    write_env "$name" "$base"
    write_schedule_json "$base"
    write_service "$name" "$base"
    if [[ "$SEED_TIMERS" == 'all' ]] || { [[ "$SEED_TIMERS" == 'mixed' ]] && (( i % 2 == 1 )); }; then
      write_timer "$base"
      timers=$(( timers + 1 ))
    else
      rm -f "$SYSTEMD_DIR/${base}.timer"
    fi
    if [[ "$SEED_LASTRUN" == 'all' ]]; then
      write_lastrun "$base" success
      markers=$(( markers + 1 ))
    elif [[ "$SEED_LASTRUN" == 'mixed' ]] && (( i % 2 == 1 )); then
      if (( i % 4 == 1 )); then write_lastrun "$base" success; else write_lastrun "$base" failed; fi
      markers=$(( markers + 1 ))
    else
      rm -f "$SYSTEMD_DIR/${base}.lastrun"
    fi
    printf 'Seeded by fd-pressure-harness.sh — safe to delete\n' >"$SYSTEMD_DIR/${base}.txt"
  done

  systemctl daemon-reload

  if [[ "$SEED_ENABLED" == '1' ]]; then
    info "enabling timers (SEED_ENABLED=1)"
    for (( i = 1; i <= count; i++ )); do
      base=$(unit_base "$(printf '%s_%03d' "$SEED_PREFIX" "$i")")
      [[ -f "$SYSTEMD_DIR/${base}.timer" ]] || continue
      systemctl enable "${base}.timer" >/dev/null 2>&1 || true
    done
  fi

  info "done — $timers timer(s), $markers marker(s); reload the scheduler page and confirm $count tasks appear"
}

seeded_names() {
  local f b
  shopt -s nullglob
  for f in "$SYSTEMD_DIR/$(unit_base "${SEED_PREFIX}")"*.env; do
    b="$(basename "$f" .env)"
    printf '%s\n' "${b#houston_scheduler_${TEMPLATE}_}"
  done
  shopt -u nullglob
}

cmd_list() {
  local n=0 name
  while read -r name; do
    [[ -z "$name" ]] && continue
    n=$(( n + 1 ))
    printf '  %-20s %s\n' "$name" "$(systemctl is-active "$(unit_base "$name").service" 2>/dev/null || true)"
  done < <(seeded_names)
  info "$n seeded task(s)"
}

cmd_clean() {
  require_root
  local name base n=0
  while read -r name; do
    [[ -z "$name" ]] && continue
    base=$(unit_base "$name")
    systemctl stop "${base}.timer" >/dev/null 2>&1 || true
    systemctl disable "${base}.timer" >/dev/null 2>&1 || true
    systemctl stop "${base}.service" >/dev/null 2>&1 || true
    systemctl reset-failed "${base}.service" >/dev/null 2>&1 || true
    rm -f "$SYSTEMD_DIR/${base}".{service,timer,env,json,txt,lastrun}
    rm -f "$SCRIPT_DIR/${name}.sh"
    n=$(( n + 1 ))
  done < <(seeded_names)
  systemctl daemon-reload
  info "removed $n seeded task(s)"
}

cmd_busy() {
  require_root
  local count="${1:-5}" n=0 name base
  while read -r name; do
    [[ -z "$name" ]] && continue
    (( n >= count )) && break
    base=$(unit_base "$name")
    # --no-block: Type=notify with TimeoutStartSec=0 would otherwise block here.
    systemctl start --no-block "${base}.service" >/dev/null 2>&1 || true
    n=$(( n + 1 ))
  done < <(seeded_names)
  info "started $n task(s); each runs ~${BUSY_SECONDS}s"
}

# --------------------------------------------------------------- monitor ----

cmd_baseline() {
  local p
  printf '%-8s %-10s %-7s %-7s %-9s %s\n' PID USER FDS FIFOS CHILDREN LIMIT
  for p in $(bridge_pids); do
    printf '%-8s %-10s %-7s %-7s %-9s %s\n' \
      "$p" "$(proc_user "$p")" "$(fd_count "$p")" "$(fifo_count "$p")" \
      "$(child_count "$p")" "$(soft_limit "$p")"
  done
}

cmd_watch() {
  local secs="${1:-120}" interval="${2:-1}"
  check_squeezed
  local start_ts; start_ts=$(date '+%Y-%m-%d %H:%M:%S')
  local deadline=$(( SECONDS + secs ))

  local peak_fd=0 peak_fifo=0 peak_child=0 first_fd=0 last_fd=0 samples=0

  rm -rf "$WORK"; mkdir -p "$WORK"
  : >"$WORK/bursts.log"

  printf '\n%s%s┌─ FD pressure monitor ─────────────────────────────────────────┐%s\n' "$BLD" "$CYA" "$RST"
  printf '%s│%s Keep the Cockpit scheduler page OPEN in a browser for %-6s %s│%s\n' "$CYA" "$RST" "${secs}s" "$CYA" "$RST"
  printf '%s│%s Expand a row, open a log modal, toggle the debug log.          %s│%s\n' "$CYA" "$RST" "$CYA" "$RST"
  printf '%s└───────────────────────────────────────────────────────────────┘%s\n\n' "$CYA" "$RST"

  printf '%-10s %-8s %-10s %-7s %-7s %-9s\n' TIME PID USER FDS FIFOS CHILDREN
  while (( SECONDS < deadline )); do
    local p total_fd=0 total_child=0
    for p in $(bridge_pids); do
      local f fi c
      f=$(fd_count "$p"); fi=$(fifo_count "$p"); c=$(child_count "$p")
      total_fd=$(( total_fd + f )); total_child=$(( total_child + c ))
      (( f  > peak_fd    )) && peak_fd=$f
      (( fi > peak_fifo  )) && peak_fifo=$fi
      (( c  > peak_child )) && peak_child=$c

      local mark=''
      if (( c > GATE_LIMIT )); then
        child_cmds "$p" >>"$WORK/bursts.log"
        (( c > CHILD_FAIL )) && mark=" ${RED}<-- burst${RST}"
      fi
      [[ -f "$WORK/pipes.first" ]] || pipe_inodes "$p" >"$WORK/pipes.first"
      pipe_inodes "$p" >"$WORK/pipes.last"
      printf '%-10s %-8s %-10s %-7s %-7s %-9s%s\n' \
        "$(date '+%H:%M:%S')" "$p" "$(proc_user "$p")" "$f" "$fi" "$c" "$mark"
    done
    (( samples == 0 )) && first_fd=$total_fd
    last_fd=$total_fd
    samples=$(( samples + 1 ))
    sleep "$interval"
  done

  local emfile
  emfile=$(journalctl --since "$start_ts" --no-pager 2>/dev/null | grep -ci 'too many open files' || true)

  local stale=0
  if [[ -s "$WORK/pipes.first" && -s "$WORK/pipes.last" ]]; then
    stale=$(comm -12 "$WORK/pipes.first" "$WORK/pipes.last" | wc -l)
  fi

  if [[ -s "$WORK/bursts.log" ]]; then
    printf '\n%s── what was spawning (samples above the gate limit) ──%s\n' "$BLD" "$RST"
    sed 's/^ *[0-9]* *//' "$WORK/bursts.log" \
      | awk '{ print $1, $2, $3 }' | sort | uniq -c | sort -rn | head -15
    printf '  (full capture: %s)\n' "$WORK/bursts.log"
  fi

  printf '\n%s── verdict ──────────────────────────────────────────────%s\n' "$BLD" "$RST"
  printf '  peak FDs (single bridge)   : %s\n' "$peak_fd"
  printf '  peak FIFOs (single bridge) : %s\n' "$peak_fifo"
  printf '  peak children (single)     : %s   (gate limit %s)\n' "$peak_child" "$GATE_LIMIT"
  printf '  FD total first -> last     : %s -> %s\n' "$first_fd" "$last_fd"
  printf '  pipes alive whole run      : %s   (should be near 0)\n' "$stale"
  printf '  EMFILE lines in journal    : %s\n' "$emfile"
  echo

  local rc=0
  if (( emfile > 0 )); then
    printf '  %s[FAIL]%s "too many open files" appeared in the journal\n' "$RED" "$RST"; rc=1
  fi
  if (( peak_child > CHILD_FAIL )); then
    printf '  %s[FAIL]%s peak children %s exceeded %s — spawns are not bounded\n' "$RED" "$RST" "$peak_child" "$CHILD_FAIL"; rc=1
  elif (( peak_child > GATE_LIMIT + 4 )); then
    printf '  %s[WARN]%s peak children %s is above the gate limit %s\n' "$YEL" "$RST" "$peak_child" "$GATE_LIMIT"
  else
    printf '  %s[ok]%s   concurrent spawns stayed within the gate\n' "$GRN" "$RST"
  fi
  if (( peak_fd > FD_FAIL )); then
    printf '  %s[FAIL]%s peak FDs %s exceeded %s\n' "$RED" "$RST" "$peak_fd" "$FD_FAIL"; rc=1
  else
    printf '  %s[ok]%s   FD ceiling stayed well below the 1024 limit\n' "$GRN" "$RST"
  fi
  if (( samples > 4 && first_fd > 0 && last_fd > first_fd * 2 )); then
    printf '  %s[WARN]%s FD total more than doubled over the run — possible leak\n' "$YEL" "$RST"
  fi
  if (( stale > 20 )); then
    printf '  %s[FAIL]%s %s pipes survived the entire run — channels are not being closed\n' "$RED" "$RST" "$stale"; rc=1
  fi
  echo
  return $rc
}

cmd_exectrace() {
  require_root
  local secs="${1:-60}" p sp=()
  mkdir -p "$WORK"
  local log="$WORK/exec.log"

  local pids; pids=$(bridge_pids | tr '\n' ' ')
  [[ -n "${pids// /}" ]] || die "no cockpit-bridge running — log into Cockpit first"

  info "open the scheduler page now; tracing every bridge spawn for ${secs}s (Ctrl-C to stop early)"
  if command -v bpftrace >/dev/null 2>&1; then
    # --foreground keeps the child in our process group so Ctrl-C reaches it.
    timeout --foreground -k 5 "$secs" bpftrace -e '
      tracepoint:syscalls:sys_enter_execve /comm == "cockpit-bridge"/ {
        printf("%s ", strftime("%H:%M:%S", nsecs)); join(args->argv);
      }' 2>/dev/null | grep -v '^Attaching' >"$log" || true
  elif [[ "${EXECTRACE_ALLOW_STRACE:-0}" == '1' ]] && command -v strace >/dev/null 2>&1; then
    warn "using strace — this slows the bridge badly and can make the UI time out"
    for p in $pids; do sp+=(-p "$p"); done
    timeout --foreground -k 5 "$secs" strace -f -qq -s 200 -e trace=execve "${sp[@]}" >"$log" 2>&1 || true
  else
    die "install bpftrace: dnf install -y bpftrace
       (strace fallback is opt-in: EXECTRACE_ALLOW_STRACE=1 $0 exectrace $secs)"
  fi

  # join() re-emits newlines embedded in inline scripts; only timestamped lines
  # are real exec events.
  local real="$WORK/exec.real"
  grep -E '^[0-9]{2}:[0-9]{2}:[0-9]{2} ' "$log" >"$real" 2>/dev/null || cp "$log" "$real"

  printf '\n%s── commands spawned, by frequency ──%s\n' "$BLD" "$RST"
  sed 's/^[0-9:]* //' "$real" | cut -c1-260 | sort | uniq -c | sort -rn | head -25
  printf '\n  total spawns : %s over %ss\n' "$(wc -l <"$real")" "$secs"
  printf '  full log     : %s\n\n' "$log"
}

cmd_squeeze() {
  require_root
  local limit="${1:-128}" p
  command -v prlimit >/dev/null || die "prlimit not installed (util-linux)"
  for p in $(bridge_pids); do
    # Soft limit only. Lowering the hard limit makes this irreversible.
    prlimit --pid "$p" --nofile="${limit}:" && \
      info "bridge $p ($(proc_user "$p")) soft limit -> $limit"
  done
  warn "a bridge that hits EMFILE stays broken — log out of Cockpit to replace it"
  warn "run 'unsqueeze' before any normal measurement"
}

cmd_unsqueeze() {
  require_root
  local limit="${1:-1024}" p
  command -v prlimit >/dev/null || die "prlimit not installed (util-linux)"
  for p in $(bridge_pids); do
    if prlimit --pid "$p" --nofile="${limit}:${limit}" 2>/dev/null; then
      info "bridge $p ($(proc_user "$p")) limit -> $limit"
    else
      warn "bridge $p: could not raise limit (hard limit already lowered); log out of Cockpit"
    fi
  done
}

check_squeezed() {
  local p lim squeezed=0
  for p in $(bridge_pids); do
    lim=$(soft_limit "$p")
    [[ "$lim" =~ ^[0-9]+$ ]] || continue
    if (( lim < 1024 )); then
      warn "bridge $p ($(proc_user "$p")) has RLIMIT_NOFILE=$lim — left over from 'squeeze'"
      squeezed=1
    fi
  done
  if (( squeezed )); then
    warn "results will be meaningless. Run 'unsqueeze', or log out of Cockpit for a fresh bridge."
  fi
}

# --------------------------------------------------------------- drivers ----

cmd_soak() {
  local count="${1:?count required}" secs="${2:-120}"
  cmd_clean
  cmd_seed "$count"
  echo
  info "waiting 10s for you to reload the scheduler page..."
  sleep 10
  cmd_watch "$secs" 1
}

cmd_run_all() {
  local secs="${1:-120}" rc=0
  printf '\n%s===== PHASE 1: 8 tasks (per-task refreshOne path) =====%s\n' "$BLD" "$RST"
  cmd_soak 8 "$secs" || rc=1
  printf '\n%s===== PHASE 2: 60 tasks (bulk getBulkDisplayMeta path) =====%s\n' "$BLD" "$RST"
  cmd_soak 60 "$secs" || rc=1
  printf '\n%s===== CLEANUP =====%s\n' "$BLD" "$RST"
  cmd_clean
  if (( rc == 0 )); then
    printf '\n%s[PASS]%s both phases stayed within bounds\n\n' "$GRN" "$RST"
  else
    printf '\n%s[FAIL]%s see phase output above\n\n' "$RED" "$RST"
  fi
  return $rc
}

main() {
  local sub="${1:-}"; shift || true
  case "$sub" in
    seed)     cmd_seed "$@" ;;
    list)     cmd_list "$@" ;;
    clean)    cmd_clean "$@" ;;
    baseline) cmd_baseline "$@" ;;
    watch)     cmd_watch "$@" ;;
    exectrace) cmd_exectrace "$@" ;;
    busy)     cmd_busy "$@" ;;
    soak)      cmd_soak "$@" ;;
    run-all)   cmd_run_all "$@" ;;
    squeeze)   cmd_squeeze "$@" ;;
    unsqueeze) cmd_unsqueeze "$@" ;;
    -h|--help|help|'') usage ;;
    *) usage; die "unknown command: $sub" ;;
  esac
}

main "$@"
