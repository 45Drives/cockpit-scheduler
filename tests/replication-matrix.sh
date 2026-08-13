#!/usr/bin/env bash
# Automated ZFS replication matrix test.
#
# Provisions disposable datasets, generates every replication task variant
# (push/pull x local/ssh/netcat/mbuffer), then drives each task through
# dry-run, full send, incremental, force-full, resume-without-token and
# interrupt+resume phases, verifying results with snapshot GUID comparison.
#
# Run as root on the SCHEDULER host (the "local" side for both directions).

set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration (override via environment)
# ---------------------------------------------------------------------------
REMOTE_HOST="${REMOTE_HOST:-192.168.207.49}"
REMOTE_USER="${REMOTE_USER:-root}"
SSH_PORT="${SSH_PORT:-22}"

LOCAL_POOL="${LOCAL_POOL:-tank}"
REMOTE_POOL="${REMOTE_POOL:-tank}"
TEST_PREFIX="${TEST_PREFIX:-reptest}"
TASK_PREFIX="${TASK_PREFIX:-RepMatrix}"

SEED_MB="${SEED_MB:-256}"
INCREMENT_MB="${INCREMENT_MB:-64}"
RESUME_SEED_MB="${RESUME_SEED_MB:-4096}"

DATA_PORT_BASE="${DATA_PORT_BASE:-9200}"
RUN_TIMEOUT="${RUN_TIMEOUT:-3600}"
INTERRUPT_AFTER="${INTERRUPT_AFTER:-2}"
TOKEN_WAIT="${TOKEN_WAIT:-90}"
# Interrupt only once the receiver has committed this much, otherwise ZFS has
# nothing to write a resume token for.
MIN_RECV_BYTES="${MIN_RECV_BYTES:-134217728}"
RECV_PROGRESS_TIMEOUT="${RECV_PROGRESS_TIMEOUT:-300}"

MBUFFER_CALLBACK_HOST="${MBUFFER_CALLBACK_HOST:-}"
SCRIPT_PATH="${SCRIPT_PATH:-/opt/45drives/houston/scheduler/scripts/replication-script.py}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
LOGDIR="${LOGDIR:-/var/log/zfs-rep-matrix}"

SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"

# case_name:direction:transferMethod
ALL_CASES=(
  "push_local:push:local"
  "push_ssh:push:ssh"
  "push_netcat:push:netcat"
  "push_mbuffer:push:mbuffer"
  "pull_ssh:pull:ssh"
  "pull_netcat:pull:netcat"
  "pull_mbuffer:pull:mbuffer"
)

ALL_PHASES=(dryrun full incremental force-full resume-no-token interrupt-resume)

SELECTED_CASES=()
SELECTED_PHASES=()

RESULT_LINES=()
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
log()  { printf '%s %s\n' "$(date '+%H:%M:%S')" "$*"; }
info() { log "     $*"; }
head1() { printf '\n===== %s =====\n' "$*"; }
head2() { printf '\n--- %s ---\n' "$*"; }

record() { # status case phase detail
  local status="$1" c="$2" p="$3" detail="${4:-}"
  RESULT_LINES+=("$(printf '%-6s %-14s %-18s %s' "$status" "$c" "$p" "$detail")")
  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    SKIP) SKIP_COUNT=$((SKIP_COUNT + 1)) ;;
  esac
  printf '  [%s] %s / %s %s\n' "$status" "$c" "$p" "${detail:+- $detail}"
}

usage() {
  cat <<EOF
Usage: replication-matrix.sh <command> [options]

Commands:
  preflight            Check tooling, SSH and pools on both hosts
  provision            Create and seed the disposable test datasets
  create-tasks         Write env + systemd unit files for every matrix case
  run                  Execute the phase suite against the created tasks
  report               Print the last run summary (implied by 'run')
  teardown --yes       Destroy all matrix tasks and datasets
  all                  preflight + provision + create-tasks + run

Options:
  --case <name>        Restrict to a case (repeatable)
  --phase <name>       Restrict to a phase (repeatable)
  --list               Show the case/phase matrix and exit

Cases:  ${ALL_CASES[*]%%:*}
Phases: ${ALL_PHASES[*]}

Key environment overrides:
  REMOTE_HOST=$REMOTE_HOST  REMOTE_USER=$REMOTE_USER  SSH_PORT=$SSH_PORT
  LOCAL_POOL=$LOCAL_POOL  REMOTE_POOL=$REMOTE_POOL  TEST_PREFIX=$TEST_PREFIX
  SEED_MB=$SEED_MB  RESUME_SEED_MB=$RESUME_SEED_MB  DATA_PORT_BASE=$DATA_PORT_BASE
  INTERRUPT_AFTER=$INTERRUPT_AFTER  RUN_TIMEOUT=$RUN_TIMEOUT
  MBUFFER_CALLBACK_HOST=(auto via SSH_CLIENT when empty)

Examples:
  ./replication-matrix.sh all
  ./replication-matrix.sh run --case pull_netcat
  ./replication-matrix.sh run --phase full --phase incremental
  REMOTE_HOST=192.168.207.49 ./replication-matrix.sh preflight

Run this on the host where the scheduler package is installed. REMOTE_HOST is
the OTHER box; it only needs zfs, mbuffer, pv, nc and key-based SSH access.
EOF
}

# ---------------------------------------------------------------------------
# Remote / local execution
# ---------------------------------------------------------------------------
rsh() { # single command string; -n keeps ssh from eating the caller's stdin
  ssh -n -p "$SSH_PORT" -o BatchMode=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=accept-new "$REMOTE_USER@$REMOTE_HOST" "$1"
}

on_side() { # side command-string
  if [[ "$1" == local ]]; then
    bash -c "$2" </dev/null
  else
    rsh "$2"
  fi
}

# ---------------------------------------------------------------------------
# Case metadata
# ---------------------------------------------------------------------------
case_direction() { local c="$1"; local e; for e in "${ALL_CASES[@]}"; do [[ "${e%%:*}" == "$c" ]] && { echo "$e" | cut -d: -f2; return; }; done; }
case_method()    { local c="$1"; local e; for e in "${ALL_CASES[@]}"; do [[ "${e%%:*}" == "$c" ]] && { echo "$e" | cut -d: -f3; return; }; done; }

case_index() {
  local c="$1" i=0 e
  for e in "${ALL_CASES[@]}"; do
    [[ "${e%%:*}" == "$c" ]] && { echo "$i"; return; }
    i=$((i + 1))
  done
  echo 0
}

case_src_side() { [[ "$(case_direction "$1")" == pull ]] && echo remote || echo local; }

case_dst_side() {
  local c="$1"
  if [[ "$(case_direction "$c")" == pull ]]; then
    echo local
  elif [[ "$(case_method "$c")" == local ]]; then
    echo local
  else
    echo remote
  fi
}

case_src_pool() { [[ "$(case_src_side "$1")" == remote ]] && echo "$REMOTE_POOL" || echo "$LOCAL_POOL"; }
case_dst_pool() { [[ "$(case_dst_side "$1")" == remote ]] && echo "$REMOTE_POOL" || echo "$LOCAL_POOL"; }

case_src_fs() { echo "$(case_src_pool "$1")/$TEST_PREFIX/src_$1"; }
case_dst_fs() { echo "$(case_dst_pool "$1")/$TEST_PREFIX/dst_$1"; }

case_host() { [[ "$(case_method "$1")" == local ]] && echo "" || echo "$REMOTE_HOST"; }
case_data_port() { echo $((DATA_PORT_BASE + $(case_index "$1"))); }

task_name()  { echo "${TASK_PREFIX}_$1"; }
unit_for()   { echo "houston_scheduler_ZfsReplicationTask_$(task_name "$1").service"; }
env_for()    { echo "$SYSTEMD_DIR/houston_scheduler_ZfsReplicationTask_$(task_name "$1").env"; }
svc_for()    { echo "$SYSTEMD_DIR/houston_scheduler_ZfsReplicationTask_$(task_name "$1").service"; }

selected_cases() {
  if [[ ${#SELECTED_CASES[@]} -gt 0 ]]; then
    printf '%s\n' "${SELECTED_CASES[@]}"
  else
    local e; for e in "${ALL_CASES[@]}"; do echo "${e%%:*}"; done
  fi
}

phase_selected() {
  [[ ${#SELECTED_PHASES[@]} -eq 0 ]] && return 0
  local p; for p in "${SELECTED_PHASES[@]}"; do [[ "$p" == "$1" ]] && return 0; done
  return 1
}

# ---------------------------------------------------------------------------
# ZFS helpers
# ---------------------------------------------------------------------------
zfs_exists() { # side dataset
  on_side "$1" "zfs list -H -o name '$2'" >/dev/null 2>&1
}

zfs_mountpoint() { # side dataset
  on_side "$1" "zfs get -H -o value mountpoint '$2'" 2>/dev/null | tr -d '\r'
}

zfs_create() { # side dataset
  on_side "$1" "zfs create -p '$2'" >/dev/null 2>&1
}

assert_test_dataset() { # dataset pool -- refuse to touch anything outside the sandbox
  local ds="$1" pool="$2"
  if [[ "$ds" != "$pool/$TEST_PREFIX" && "$ds" != "$pool/$TEST_PREFIX/"* ]]; then
    echo "refusing to operate on '$ds' (outside $pool/$TEST_PREFIX)" >&2
    return 1
  fi
}

zfs_destroy_tree() { # side dataset pool
  assert_test_dataset "$2" "$3" || return 1
  on_side "$1" "zfs destroy -r '$2'" >/dev/null 2>&1
}

snap_list() { # side dataset  -> full snapshot names, oldest first
  on_side "$1" "zfs list -H -o name -t snapshot -r -d 1 -s creation '$2'" 2>/dev/null | tr -d '\r'
}

snap_count() { snap_list "$1" "$2" | grep -c . ; }

snap_guid() { # side dataset@snap
  on_side "$1" "zfs get -H -o value guid '$2'" 2>/dev/null | tr -d '\r'
}

resume_token() { # side dataset
  on_side "$1" "zfs get -H -o value receive_resume_token '$2'" 2>/dev/null | tr -d '\r'
}

recv_bytes() { # side dataset -> bytes committed by an in-flight receive
  local side="$1" ds="$2" v
  # An in-progress receive parks data in the hidden %recv clone.
  v="$(on_side "$side" "zfs get -Hp -o value used '$ds/%recv' 2>/dev/null" | tr -d '\r')"
  [[ "$v" =~ ^[0-9]+$ ]] || v="$(on_side "$side" "zfs get -Hp -o value used '$ds' 2>/dev/null" | tr -d '\r')"
  [[ "$v" =~ ^[0-9]+$ ]] || v=0
  echo "$v"
}

human_bytes() { numfmt --to=iec-i --suffix=B "${1:-0}" 2>/dev/null || echo "${1:-0}B"; }

port_busy() { # side port
  on_side "$1" "ss -lnt 2>/dev/null | grep -q ':$2 '" >/dev/null 2>&1
}

free_data_port() { # case
  # A SIGKILLed run leaves the listener orphaned; the next run then either fails
  # to bind or, worse, connects to the stale socket and reads nothing.
  local c="$1" port ssid dsid reap side pp tp
  port="$(case_data_port "$c")"
  ssid="$(case_src_side "$c")"; dsid="$(case_dst_side "$c")"

  # Bracket the first character so the pattern cannot match the reaping shell.
  pp="[${port:0:1}]${port:1}"
  tp="[${TEST_PREFIX:0:1}]${TEST_PREFIX:1}"
  reap="fuser -k -n tcp $port >/dev/null 2>&1; pkill -f 'nc(at)? .*$pp' >/dev/null 2>&1; pkill -f 'mbuffer.*$pp' >/dev/null 2>&1; pkill -f 'zfs (send|recv).*$tp/' >/dev/null 2>&1; true"

  on_side "$ssid" "$reap" >/dev/null 2>&1
  [[ "$dsid" != "$ssid" ]] && on_side "$dsid" "$reap" >/dev/null 2>&1

  local waited=0
  for side in "$ssid" "$dsid"; do
    waited=0
    while port_busy "$side" "$port" && (( waited < 20 )); do
      sleep 1; waited=$((waited + 1))
    done
    if port_busy "$side" "$port"; then
      info "WARNING: $side still has a listener on port $port" >&2
    fi
  done
  return 0
}

seed_data() { # side dataset megabytes tag
  local side="$1" ds="$2" mb="$3" tag="$4" mnt
  mnt="$(zfs_mountpoint "$side" "$ds")"
  if [[ -z "$mnt" || "$mnt" == "-" || "$mnt" == "legacy" || "$mnt" == "none" ]]; then
    echo "no usable mountpoint for $ds on $side" >&2
    return 1
  fi
  on_side "$side" "dd if=/dev/urandom of='$mnt/$tag.bin' bs=1M count=$mb status=none && sync"
}

# ---------------------------------------------------------------------------
# Task file generation
# ---------------------------------------------------------------------------
write_env_file() { # case
  local c="$1"
  local env_path direction method src_fs dst_fs host data_port
  env_path="$(env_for "$c")"
  direction="$(case_direction "$c")"
  method="$(case_method "$c")"
  src_fs="$(case_src_fs "$c")"
  dst_fs="$(case_dst_fs "$c")"
  host="$(case_host "$c")"
  data_port="$(case_data_port "$c")"

  cat >"$env_path" <<EOF
taskName=$(task_name "$c")
zfsRepConfig_direction=$direction
zfsRepConfig_sendOptions_transferMethod=$method
zfsRepConfig_sendOptions_recursive_flag=false
zfsRepConfig_sendOptions_compressed_flag=false
zfsRepConfig_sendOptions_raw_flag=false
zfsRepConfig_sendOptions_customName_flag=false
zfsRepConfig_sendOptions_customName=
zfsRepConfig_sendOptions_includeIntermediateSnapshots=false
zfsRepConfig_sendOptions_allowOverwrite=false
zfsRepConfig_sendOptions_useExistingDest=false
zfsRepConfig_sendOptions_forceFullSend=false
zfsRepConfig_sendOptions_dryRun=false
zfsRepConfig_sendOptions_resumeOnly=false
zfsRepConfig_sendOptions_resumeFailAllowOverwrite=false
zfsRepConfig_sendOptions_resumeStallTimeout=600
zfsRepConfig_sendOptions_mbufferSize=1
zfsRepConfig_sendOptions_mbufferUnit=G
zfsRepConfig_sendOptions_mbufferBlockSize=256
zfsRepConfig_sendOptions_mbufferBlockUnit=k
zfsRepConfig_sendOptions_mbufferCallbackHost=$MBUFFER_CALLBACK_HOST
zfsRepConfig_sourceDataset_pool=$(case_src_pool "$c")
zfsRepConfig_sourceDataset_dataset=$src_fs
zfsRepConfig_destDataset_pool=$(case_dst_pool "$c")
zfsRepConfig_destDataset_dataset=$dst_fs
zfsRepConfig_destDataset_user=$REMOTE_USER
zfsRepConfig_destDataset_host=$host
zfsRepConfig_destDataset_port=$data_port
zfsRepConfig_destDataset_sshPort=$SSH_PORT
zfsRepConfig_snapshotRetention_source_retentionTime=0
zfsRepConfig_snapshotRetention_source_retentionUnit=
zfsRepConfig_snapshotRetention_destination_retentionTime=0
zfsRepConfig_snapshotRetention_destination_retentionUnit=
ZFS_REP_DEBUG=1
EOF
  chmod 0600 "$env_path"
}

write_unit_file() { # case
  local c="$1" svc_path env_path
  svc_path="$(svc_for "$c")"
  env_path="$(env_for "$c")"

  # Restart=no so a failing matrix run reports once instead of retrying.
  cat >"$svc_path" <<EOF
[Unit]
Description=ZFS replication matrix test task $(task_name "$c")
After=zfs-mount.service zfs-import.target
Wants=zfs-import.target

[Service]
Type=notify
NotifyAccess=all
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
StandardOutput=journal
StandardError=journal
EnvironmentFile=$env_path
ExecStart=$PYTHON_BIN -u $SCRIPT_PATH
Restart=no
TimeoutStartSec=0
TimeoutStopSec=90
EOF
}

set_flag() { # case flag value
  local env_path key tmp
  env_path="$(env_for "$1")"
  key="zfsRepConfig_sendOptions_$2"
  tmp="$(mktemp)"
  awk -v key="$key" -v val="$3" '
    BEGIN { found = 0 }
    { if ($0 ~ "^" key "=") { print key "=" val; found = 1 } else { print } }
    END { if (!found) print key "=" val }
  ' "$env_path" >"$tmp" && mv "$tmp" "$env_path"
  chmod 0600 "$env_path"
}

get_flag() { # case flag
  local env_path key value
  env_path="$(env_for "$1")"
  key="zfsRepConfig_sendOptions_$2"
  value="$(awk -F= -v key="$key" '$1 == key { v = $2 } END { print v }' "$env_path" | tr -d '\r')"
  echo "${value:-unset}"
}

clear_one_shots() {
  set_flag "$1" dryRun false
  set_flag "$1" forceFullSend false
  set_flag "$1" resumeOnly false
}

# ---------------------------------------------------------------------------
# Unit lifecycle
# ---------------------------------------------------------------------------
unit_active() { systemctl show "$1" -p ActiveState --value 2>/dev/null; }
unit_sub()    { systemctl show "$1" -p SubState --value 2>/dev/null; }

wait_unit_running() { # unit timeout
  local unit="$1" timeout="$2" start
  start="$(date +%s)"
  while true; do
    [[ "$(unit_active "$unit")" == active && "$(unit_sub "$unit")" == running ]] && return 0
    [[ "$(unit_active "$unit")" == failed ]] && return 1
    (( $(date +%s) - start >= timeout )) && return 1
    sleep 1
  done
}

wait_unit_finished() { # unit timeout
  local unit="$1" timeout="$2" start state
  start="$(date +%s)"
  while true; do
    state="$(unit_active "$unit")"
    [[ "$state" == inactive || "$state" == failed ]] && return 0
    (( $(date +%s) - start >= timeout )) && return 1
    sleep 2
  done
}

run_unit() { # case phase -> echoes "<result>:<exec_status>"
  local c="$1" phase="$2" unit since log
  unit="$(unit_for "$c")"
  log="$LOGDIR/${c}-${phase}.log"

  free_data_port "$c"
  since="$(date '+%Y-%m-%d %H:%M:%S')"

  systemctl reset-failed "$unit" >/dev/null 2>&1
  systemctl start "$unit" >/dev/null 2>&1

  if ! wait_unit_finished "$unit" "$RUN_TIMEOUT"; then
    systemctl stop "$unit" >/dev/null 2>&1
    journalctl -u "$unit" --since "$since" --no-pager >"$log" 2>&1
    echo "timeout:-1"
    return
  fi

  journalctl -u "$unit" --since "$since" --no-pager >"$log" 2>&1
  printf '%s:%s\n' \
    "$(systemctl show "$unit" -p Result --value)" \
    "$(systemctl show "$unit" -p ExecMainStatus --value)"
}

tail_log() { # case phase lines
  local log="$LOGDIR/${1}-${2}.log"
  [[ -f "$log" ]] && tail -n "${3:-25}" "$log" | sed 's/^/        | /'
  return 0
}

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
verify_replica() { # case -> 0 when latest source snapshot exists on dest with same GUID
  local c="$1" ssid dsid src_fs dst_fs latest short src_guid dst_guid
  ssid="$(case_src_side "$c")"; dsid="$(case_dst_side "$c")"
  src_fs="$(case_src_fs "$c")"; dst_fs="$(case_dst_fs "$c")"

  latest="$(snap_list "$ssid" "$src_fs" | tail -1)"
  if [[ -z "$latest" ]]; then
    VERIFY_DETAIL="source $src_fs has no snapshots"
    return 1
  fi
  short="${latest#*@}"

  src_guid="$(snap_guid "$ssid" "$latest")"
  dst_guid="$(snap_guid "$dsid" "$dst_fs@$short")"

  if [[ -z "$dst_guid" || "$dst_guid" == "-" ]]; then
    VERIFY_DETAIL="destination is missing snapshot @$short"
    return 1
  fi
  if [[ "$src_guid" != "$dst_guid" ]]; then
    VERIFY_DETAIL="GUID mismatch for @$short (src=$src_guid dst=$dst_guid)"
    return 1
  fi
  VERIFY_DETAIL="@$short guid=$src_guid"
  return 0
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
cmd_preflight() {
  head1 "preflight"
  local rc=0

  info "local:  $(uname -n)  python=$(python3 -V 2>&1)"
  for tool in zfs mbuffer pv nc; do
    if command -v "$tool" >/dev/null 2>&1; then
      info "local:  $tool OK"
    else
      echo "  MISSING local tool: $tool" >&2; rc=1
    fi
  done

  if ! rsh true >/dev/null 2>&1; then
    echo "  FAIL: cannot ssh $REMOTE_USER@$REMOTE_HOST:$SSH_PORT with BatchMode (install the key first)" >&2
    return 1
  fi
  info "remote: $(rsh 'uname -n') python=$(rsh 'python3 -V 2>&1')"
  for tool in zfs mbuffer pv nc; do
    if rsh "command -v $tool >/dev/null 2>&1"; then
      info "remote: $tool OK"
    else
      echo "  MISSING remote tool: $tool" >&2; rc=1
    fi
  done

  if ! zpool list -H -o name "$LOCAL_POOL" >/dev/null 2>&1; then
    echo "  FAIL: local pool '$LOCAL_POOL' not found" >&2; rc=1
  fi
  if ! rsh "zpool list -H -o name '$REMOTE_POOL'" >/dev/null 2>&1; then
    echo "  FAIL: remote pool '$REMOTE_POOL' not found" >&2; rc=1
  fi

  local callback
  callback="$(rsh 'printf "%s" "${SSH_CLIENT%% *}"')"
  info "remote sees this host as: ${callback:-<unknown>} (mbuffer pull callback target)"
  [[ -z "$callback" ]] && info "set MBUFFER_CALLBACK_HOST explicitly if mbuffer pull fails"

  info "netcat/mbuffer data ports: $DATA_PORT_BASE-$((DATA_PORT_BASE + ${#ALL_CASES[@]} - 1)) must be open between hosts"
  [[ $rc -eq 0 ]] && info "preflight OK"
  return $rc
}

cmd_provision() {
  head1 "provision"
  mkdir -p "$LOGDIR"

  zfs_create local "$LOCAL_POOL/$TEST_PREFIX"
  zfs_create remote "$REMOTE_POOL/$TEST_PREFIX"

  local c side src_fs dst_fs dst_side
  local cases=(); mapfile -t cases < <(selected_cases)
  for c in "${cases[@]}"; do
    side="$(case_src_side "$c")"
    src_fs="$(case_src_fs "$c")"
    dst_fs="$(case_dst_fs "$c")"
    dst_side="$(case_dst_side "$c")"

    # Start from a clean slate so 'full' is genuinely a first send.
    zfs_destroy_tree "$side" "$src_fs" "$(case_src_pool "$c")"
    zfs_destroy_tree "$dst_side" "$dst_fs" "$(case_dst_pool "$c")"

    zfs_create "$side" "$src_fs" || { echo "  failed to create $src_fs on $side" >&2; return 1; }
    info "seeding $side:$src_fs with ${SEED_MB}MB"
    seed_data "$side" "$src_fs" "$SEED_MB" base || return 1
  done

  info "provision complete"
}

cmd_create_tasks() {
  head1 "create-tasks"
  local c host
  local cases=(); mapfile -t cases < <(selected_cases)
  for c in "${cases[@]}"; do
    write_env_file "$c"
    write_unit_file "$c"
    host="$(case_host "$c")"
    info "$(task_name "$c"): $(case_direction "$c")/$(case_method "$c")  $(case_src_fs "$c") -> $(case_dst_fs "$c")  host=${host:-<local>} data_port=$(case_data_port "$c")"
  done
  systemctl daemon-reload
  info "units written to $SYSTEMD_DIR and daemon reloaded"
}

phase_dryrun() { # case
  local c="$1" out result status dst_side dst_fs
  dst_side="$(case_dst_side "$c")"; dst_fs="$(case_dst_fs "$c")"

  clear_one_shots "$c"
  set_flag "$c" dryRun true
  out="$(run_unit "$c" dryrun)"
  result="${out%%:*}"; status="${out##*:}"

  if [[ "$result" != success || "$status" != 0 ]]; then
    record FAIL "$c" dryrun "Result=$result ExecMainStatus=$status"
    tail_log "$c" dryrun 30
    return 1
  fi
  if zfs_exists "$dst_side" "$dst_fs"; then
    record FAIL "$c" dryrun "dry run created destination $dst_fs"
    return 1
  fi
  if [[ "$(get_flag "$c" dryRun)" != false ]]; then
    record FAIL "$c" dryrun "dryRun one-shot did not clear"
    return 1
  fi
  record PASS "$c" dryrun "no data moved, one-shot cleared"
}

phase_full() { # case
  local c="$1" out result status
  clear_one_shots "$c"
  out="$(run_unit "$c" full)"
  result="${out%%:*}"; status="${out##*:}"

  if [[ "$result" != success || "$status" != 0 ]]; then
    record FAIL "$c" full "Result=$result ExecMainStatus=$status"
    tail_log "$c" full 40
    return 1
  fi
  if verify_replica "$c"; then
    record PASS "$c" full "$VERIFY_DETAIL"
  else
    record FAIL "$c" full "$VERIFY_DETAIL"
    tail_log "$c" full 40
    return 1
  fi
}

phase_incremental() { # case
  local c="$1" out result status before after
  local ssid dsid
  ssid="$(case_src_side "$c")"; dsid="$(case_dst_side "$c")"

  before="$(snap_count "$dsid" "$(case_dst_fs "$c")")"
  seed_data "$ssid" "$(case_src_fs "$c")" "$INCREMENT_MB" "inc$(date +%s)" || {
    record FAIL "$c" incremental "could not write new source data"; return 1; }

  clear_one_shots "$c"
  out="$(run_unit "$c" incremental)"
  result="${out%%:*}"; status="${out##*:}"

  if [[ "$result" != success || "$status" != 0 ]]; then
    record FAIL "$c" incremental "Result=$result ExecMainStatus=$status"
    tail_log "$c" incremental 40
    return 1
  fi

  after="$(snap_count "$dsid" "$(case_dst_fs "$c")")"
  if (( after <= before )); then
    record FAIL "$c" incremental "destination snapshot count did not grow ($before -> $after)"
    tail_log "$c" incremental 40
    return 1
  fi
  if verify_replica "$c"; then
    record PASS "$c" incremental "snapshots $before -> $after, $VERIFY_DETAIL"
  else
    record FAIL "$c" incremental "$VERIFY_DETAIL"
    tail_log "$c" incremental 40
    return 1
  fi
}

phase_force_full() { # case
  local c="$1" out result status
  clear_one_shots "$c"
  set_flag "$c" forceFullSend true
  set_flag "$c" allowOverwrite true
  out="$(run_unit "$c" force-full)"
  result="${out%%:*}"; status="${out##*:}"
  set_flag "$c" allowOverwrite false

  if [[ "$result" != success || "$status" != 0 ]]; then
    record FAIL "$c" force-full "Result=$result ExecMainStatus=$status"
    tail_log "$c" force-full 40
    return 1
  fi
  if [[ "$(get_flag "$c" forceFullSend)" != false ]]; then
    record FAIL "$c" force-full "forceFullSend one-shot did not clear"
    return 1
  fi
  if verify_replica "$c"; then
    record PASS "$c" force-full "one-shot cleared, $VERIFY_DETAIL"
  else
    record FAIL "$c" force-full "$VERIFY_DETAIL"
    tail_log "$c" force-full 40
    return 1
  fi
}

phase_resume_no_token() { # case
  local c="$1" out result status dst_side dst_fs token before after
  dst_side="$(case_dst_side "$c")"; dst_fs="$(case_dst_fs "$c")"

  token="$(resume_token "$dst_side" "$dst_fs")"
  if [[ -n "$token" && "$token" != "-" ]]; then
    record SKIP "$c" resume-no-token "destination already holds a token"
    return 0
  fi

  before="$(snap_count "$dst_side" "$dst_fs")"
  clear_one_shots "$c"
  set_flag "$c" resumeOnly true
  out="$(run_unit "$c" resume-no-token)"
  result="${out%%:*}"; status="${out##*:}"

  if [[ "$result" != success || "$status" != 0 ]]; then
    record FAIL "$c" resume-no-token "expected clean exit, got Result=$result ExecMainStatus=$status"
    tail_log "$c" resume-no-token 30
    return 1
  fi
  if ! grep -q "no resume token found" "$LOGDIR/${c}-resume-no-token.log"; then
    record FAIL "$c" resume-no-token "missing the 'no resume token found' explanation in the log"
    tail_log "$c" resume-no-token 30
    return 1
  fi
  if [[ "$(get_flag "$c" resumeOnly)" != false ]]; then
    record FAIL "$c" resume-no-token "resumeOnly one-shot did not clear"
    return 1
  fi
  after="$(snap_count "$dst_side" "$dst_fs")"
  if (( after != before )); then
    record FAIL "$c" resume-no-token "destination changed ($before -> $after)"
    return 1
  fi
  record PASS "$c" resume-no-token "clean exit with actionable message, one-shot cleared"
}

phase_interrupt_resume() { # case
  local c="$1" unit ssid dsid src_fs dst_fs token out result status waited
  unit="$(unit_for "$c")"
  ssid="$(case_src_side "$c")"; dsid="$(case_dst_side "$c")"
  src_fs="$(case_src_fs "$c")"; dst_fs="$(case_dst_fs "$c")"

  head2 "$c: building an interruptible full send (${RESUME_SEED_MB}MB)"
  zfs_destroy_tree "$dsid" "$dst_fs" "$(case_dst_pool "$c")"
  seed_data "$ssid" "$src_fs" "$RESUME_SEED_MB" "bulk$(date +%s)" || {
    record FAIL "$c" interrupt-resume "could not write bulk source data"; return 1; }

  clear_one_shots "$c"
  free_data_port "$c"
  systemctl reset-failed "$unit" >/dev/null 2>&1
  local since; since="$(date '+%Y-%m-%d %H:%M:%S')"
  systemctl start "$unit" >/dev/null 2>&1

  if ! wait_unit_running "$unit" 120; then
    journalctl -u "$unit" --since "$since" --no-pager >"$LOGDIR/${c}-interrupt-resume.log" 2>&1
    record FAIL "$c" interrupt-resume "task never reached running state"
    tail_log "$c" interrupt-resume 40
    return 1
  fi

  # Netcat/mbuffer spend several seconds on listener setup before any data
  # lands, and ZFS writes no resume token until the receiver commits bytes.
  local got=0 elapsed=0
  while (( elapsed < RECV_PROGRESS_TIMEOUT )); do
    [[ "$(unit_active "$unit")" != active ]] && break
    got="$(recv_bytes "$dsid" "$dst_fs")"
    (( got >= MIN_RECV_BYTES )) && break
    sleep 2; elapsed=$((elapsed + 2))
  done

  if [[ "$(unit_active "$unit")" != active ]]; then
    journalctl -u "$unit" --since "$since" --no-pager >"$LOGDIR/${c}-interrupt-resume.log" 2>&1
    result="$(systemctl show "$unit" -p Result --value)"
    status="$(systemctl show "$unit" -p ExecMainStatus --value)"
    systemctl reset-failed "$unit" >/dev/null 2>&1
    if [[ "$result" != success || "$status" != 0 ]]; then
      record FAIL "$c" interrupt-resume "task died before it could be interrupted (Result=$result ExecMainStatus=$status)"
      tail_log "$c" interrupt-resume 40
      return 1
    fi
    record SKIP "$c" interrupt-resume "transfer finished before it could be interrupted; raise RESUME_SEED_MB or lower MIN_RECV_BYTES"
    return 0
  fi
  if (( got < MIN_RECV_BYTES )); then
    journalctl -u "$unit" --since "$since" --no-pager >"$LOGDIR/${c}-interrupt-resume.log" 2>&1
    record FAIL "$c" interrupt-resume "receiver committed only $(human_bytes "$got") in ${RECV_PROGRESS_TIMEOUT}s (need $(human_bytes "$MIN_RECV_BYTES"))"
    tail_log "$c" interrupt-resume 40
    return 1
  fi

  info "receiver has committed $(human_bytes "$got"); interrupting in ${INTERRUPT_AFTER}s"
  sleep "$INTERRUPT_AFTER"

  info "killing main process of $unit"
  systemctl kill --kill-who=main --signal=KILL "$unit" >/dev/null 2>&1
  wait_unit_finished "$unit" 120
  journalctl -u "$unit" --since "$since" --no-pager >"$LOGDIR/${c}-interrupt-kill.log" 2>&1
  systemctl reset-failed "$unit" >/dev/null 2>&1

  waited=0
  while (( waited < TOKEN_WAIT )); do
    token="$(resume_token "$dsid" "$dst_fs")"
    [[ -n "$token" && "$token" != "-" ]] && break
    sleep 2; waited=$((waited + 2))
  done

  if [[ -z "${token:-}" || "$token" == "-" ]]; then
    record FAIL "$c" interrupt-resume "no receive_resume_token appeared on $dsid:$dst_fs after ${TOKEN_WAIT}s"
    return 1
  fi
  info "resume token present (${#token} chars)"

  clear_one_shots "$c"
  set_flag "$c" resumeOnly true
  out="$(run_unit "$c" interrupt-resume)"
  result="${out%%:*}"; status="${out##*:}"

  if [[ "$result" != success || "$status" != 0 ]]; then
    record FAIL "$c" interrupt-resume "resume run failed: Result=$result ExecMainStatus=$status"
    tail_log "$c" interrupt-resume 60
    return 1
  fi

  token="$(resume_token "$dsid" "$dst_fs")"
  if [[ -n "$token" && "$token" != "-" ]]; then
    record FAIL "$c" interrupt-resume "token still present after a successful resume"
    return 1
  fi
  if verify_replica "$c"; then
    record PASS "$c" interrupt-resume "resumed and completed, $VERIFY_DETAIL"
  else
    record FAIL "$c" interrupt-resume "$VERIFY_DETAIL"
    tail_log "$c" interrupt-resume 60
    return 1
  fi
}

cmd_run() {
  head1 "run"
  mkdir -p "$LOGDIR"
  local c phase
  local cases=(); mapfile -t cases < <(selected_cases)
  for c in "${cases[@]}"; do
    head2 "case $c  ($(case_direction "$c") / $(case_method "$c"))"
    if [[ ! -f "$(env_for "$c")" ]]; then
      record FAIL "$c" setup "task env file missing; run create-tasks first"
      continue
    fi
    for phase in "${ALL_PHASES[@]}"; do
      phase_selected "$phase" || continue
      case "$phase" in
        dryrun)           phase_dryrun "$c" ;;
        full)             phase_full "$c" ;;
        incremental)      phase_incremental "$c" ;;
        force-full)       phase_force_full "$c" ;;
        resume-no-token)  phase_resume_no_token "$c" ;;
        interrupt-resume) phase_interrupt_resume "$c" ;;
      esac
    done
    clear_one_shots "$c"
  done
  cmd_report
}

cmd_report() {
  head1 "summary"
  local line
  for line in "${RESULT_LINES[@]:-}"; do [[ -n "$line" ]] && echo "  $line"; done
  printf '\n  pass=%d fail=%d skip=%d\n' "$PASS_COUNT" "$FAIL_COUNT" "$SKIP_COUNT"
  printf '  logs: %s\n' "$LOGDIR"
  (( FAIL_COUNT > 0 )) && return 1
  return 0
}

cmd_teardown() {
  if [[ "${1:-}" != "--yes" ]]; then
    echo "teardown destroys $LOCAL_POOL/$TEST_PREFIX and $REMOTE_POOL/$TEST_PREFIX plus all ${TASK_PREFIX}_* units." >&2
    echo "re-run with: teardown --yes" >&2
    return 1
  fi
  head1 "teardown"
  local c unit
  local cases=(); mapfile -t cases < <(selected_cases)
  for c in "${cases[@]}"; do
    unit="$(unit_for "$c")"
    systemctl stop "$unit" >/dev/null 2>&1
    systemctl reset-failed "$unit" >/dev/null 2>&1
    rm -f "$(svc_for "$c")" "$(env_for "$c")" \
          "$SYSTEMD_DIR/houston_scheduler_ZfsReplicationTask_$(task_name "$c").lastrun"
    info "removed $unit"
  done
  systemctl daemon-reload

  zfs_destroy_tree local "$LOCAL_POOL/$TEST_PREFIX" "$LOCAL_POOL" && info "destroyed $LOCAL_POOL/$TEST_PREFIX"
  zfs_destroy_tree remote "$REMOTE_POOL/$TEST_PREFIX" "$REMOTE_POOL" && info "destroyed $REMOTE_POOL/$TEST_PREFIX (remote)"
  info "teardown complete"
}

cmd_list() {
  head1 "matrix"
  local c
  local cases=(); mapfile -t cases < <(selected_cases)
  for c in "${cases[@]}"; do
    printf '  %-14s %-5s %-8s src=%-8s %-40s dst=%-8s %-40s port=%s\n' \
      "$c" "$(case_direction "$c")" "$(case_method "$c")" \
      "$(case_src_side "$c")" "$(case_src_fs "$c")" \
      "$(case_dst_side "$c")" "$(case_dst_fs "$c")" "$(case_data_port "$c")"
  done
  printf '\n  phases: %s\n' "${ALL_PHASES[*]}"
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
main() {
  [[ $# -lt 1 ]] && { usage; exit 1; }
  local cmd="$1"; shift

  local extra=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --case)  SELECTED_CASES+=("$2"); shift 2 ;;
      --phase) SELECTED_PHASES+=("$2"); shift 2 ;;
      --list)  cmd_list; exit 0 ;;
      *)       extra+=("$1"); shift ;;
    esac
  done

  local c valid
  for c in "${SELECTED_CASES[@]:-}"; do
    [[ -z "$c" ]] && continue
    valid=0
    local e; for e in "${ALL_CASES[@]}"; do [[ "${e%%:*}" == "$c" ]] && valid=1; done
    (( valid )) || { echo "unknown case: $c" >&2; exit 1; }
  done

  if [[ "$cmd" != list && "$cmd" != help && $EUID -ne 0 ]]; then
    echo "must run as root" >&2
    exit 1
  fi

  case "$cmd" in
    preflight)    cmd_preflight ;;
    provision)    cmd_provision ;;
    create-tasks) cmd_create_tasks ;;
    run)          cmd_run ;;
    report)       cmd_report ;;
    teardown)     cmd_teardown "${extra[@]:-}" ;;
    list)         cmd_list ;;
    all)          cmd_preflight && cmd_provision && cmd_create_tasks && cmd_run ;;
    help|-h|--help) usage ;;
    *)            usage; exit 1 ;;
  esac
}

main "$@"
