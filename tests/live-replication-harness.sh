#!/usr/bin/env bash
set -euo pipefail

# Live ZFS replication harness for server-side validation.
#
# This script automates high-friction replication checks (resume token creation,
# one-shot flags, and unit lifecycle) on disposable datasets.
#
# Run as root on the scheduler host.

usage() {
  cat <<'EOF'
Usage:
  live-replication-harness.sh preflight [pool]
  live-replication-harness.sh start <task_name>
  live-replication-harness.sh stop <task_name>
  live-replication-harness.sh status <task_name>
  live-replication-harness.sh logs <task_name> [lines]
  live-replication-harness.sh set-flag <task_name> <dryRun|forceFullSend|resumeOnly> <true|false>
  live-replication-harness.sh clear-one-shots <task_name>
  live-replication-harness.sh token-local <dest_dataset>
  live-replication-harness.sh token-remote <dest_dataset> <remote_user> <remote_host> [remote_ssh_port]
  live-replication-harness.sh remote-mbuffer <remote_user> <remote_host> [remote_ssh_port]
  live-replication-harness.sh discover-tasks
  live-replication-harness.sh autotest-all [dry-run|live] [timeout_sec]
  live-replication-harness.sh get-flag <task_name> <dryRun|forceFullSend|resumeOnly>
  live-replication-harness.sh interrupt-main <task_name> [signal]
  live-replication-harness.sh scenario-resume-token-local <task_name> <dest_dataset> [interrupt_after_sec] [token_wait_sec]
  live-replication-harness.sh scenario-resume-token-remote <task_name> <dest_dataset> <remote_user> <remote_host> [remote_ssh_port] [interrupt_after_sec] [token_wait_sec]
  live-replication-harness.sh scenario-resume-only-no-token-local <task_name> <dest_dataset> [finish_wait_sec]
  live-replication-harness.sh scenario-force-full-send-clears <task_name> [finish_wait_sec]

Hierarchy scenarios (root; build disposable hrepsrc/hrepdst pools under /var/tmp/hrep):
  live-replication-harness.sh scenario-hierarchy-all
  live-replication-harness.sh scenario-hierarchy-clean
  live-replication-harness.sh scenario-hierarchy-child-behind
  live-replication-harness.sh scenario-hierarchy-child-orphan
  live-replication-harness.sh scenario-hierarchy-child-no-snaps
  live-replication-harness.sh scenario-hierarchy-dest-ahead
  live-replication-harness.sh scenario-hierarchy-existing-data
  live-replication-harness.sh scenario-hierarchy-teardown

Examples:
  live-replication-harness.sh preflight tank
  live-replication-harness.sh set-flag TestLocalPush dryRun true
  live-replication-harness.sh scenario-resume-token-local TestLocalPush tank/sharebackup 8 45
  live-replication-harness.sh scenario-resume-token-remote TestRemotePush tank/backup root 192.168.0.1 22 8 45
  live-replication-harness.sh remote-mbuffer root 192.168.0.1 22
  live-replication-harness.sh discover-tasks
  live-replication-harness.sh autotest-all dry-run 900
  live-replication-harness.sh scenario-resume-only-no-token-local TestLocalPush tank/sharebackup 90
  live-replication-harness.sh scenario-force-full-send-clears TestLocalPush 900
  live-replication-harness.sh scenario-hierarchy-all
  ZFS_REP_SCRIPT=/opt/45drives/houston/scheduler/scripts/replication-script.py \
    live-replication-harness.sh scenario-hierarchy-child-behind
EOF
}

unit_for_task() {
  local task_name="$1"
  printf 'houston_scheduler_ZfsReplicationTask_%s.service' "$task_name"
}

env_file_for_task() {
  local task_name="$1"
  printf '/etc/systemd/system/houston_scheduler_ZfsReplicationTask_%s.env' "$task_name"
}

list_task_names() {
  local f base task
  shopt -s nullglob
  for f in /etc/systemd/system/houston_scheduler_ZfsReplicationTask_*.env; do
    base="$(basename "$f")"
    task="${base#houston_scheduler_ZfsReplicationTask_}"
    task="${task%.env}"
    echo "$task"
  done
  shopt -u nullglob
}

env_read_key() {
  local env_file="$1"
  local key="$2"
  if [[ ! -f "$env_file" ]]; then
    echo ""
    return 0
  fi

  awk -F= -v key="$key" '$1==key { v=$2 } END { print v }' "$env_file" | tr -d '\r' | sed 's/[[:space:]]*$//'
}

join_fs() {
  local pool="$1"
  local dataset="$2"

  pool="${pool:-}"
  dataset="${dataset:-}"

  if [[ -z "$pool" ]]; then
    echo "$dataset"
    return 0
  fi
  if [[ -z "$dataset" ]]; then
    echo "$pool"
    return 0
  fi
  if [[ "$dataset" == "$pool" || "$dataset" == "$pool/"* ]]; then
    echo "$dataset"
    return 0
  fi
  echo "$pool/$dataset"
}

describe_task_config() {
  local task_name="$1"
  local env_file
  env_file="$(env_file_for_task "$task_name")"

  local direction transfer host user data_port ssh_port src_pool src_ds dst_pool dst_ds src_fs dst_fs
  direction="$(env_read_key "$env_file" "zfsRepConfig_direction")"
  transfer="$(env_read_key "$env_file" "zfsRepConfig_sendOptions_transferMethod")"
  host="$(env_read_key "$env_file" "zfsRepConfig_destDataset_host")"
  user="$(env_read_key "$env_file" "zfsRepConfig_destDataset_user")"
  data_port="$(env_read_key "$env_file" "zfsRepConfig_destDataset_port")"
  ssh_port="$(env_read_key "$env_file" "zfsRepConfig_destDataset_sshPort")"
  src_pool="$(env_read_key "$env_file" "zfsRepConfig_sourceDataset_pool")"
  src_ds="$(env_read_key "$env_file" "zfsRepConfig_sourceDataset_dataset")"
  dst_pool="$(env_read_key "$env_file" "zfsRepConfig_destDataset_pool")"
  dst_ds="$(env_read_key "$env_file" "zfsRepConfig_destDataset_dataset")"

  direction="${direction:-push}"
  transfer="${transfer:-ssh}"
  user="${user:-root}"
  data_port="${data_port:-22}"
  ssh_port="${ssh_port:-}"
  if [[ -z "$ssh_port" ]]; then
    if [[ "$transfer" == "netcat" || "$transfer" == "mbuffer" ]]; then
      ssh_port="22"
    else
      ssh_port="$data_port"
    fi
  fi

  src_fs="$(join_fs "$src_pool" "$src_ds")"
  dst_fs="$(join_fs "$dst_pool" "$dst_ds")"

  printf 'task=%s direction=%s transfer=%s source=%s destination=%s remote_user=%s remote_host=%s ssh_port=%s data_port=%s\n' \
    "$task_name" "$direction" "$transfer" "$src_fs" "$dst_fs" "$user" "${host:--}" "$ssh_port" "$data_port"
}

set_env_flag() {
  local task_name="$1"
  local short_flag="$2"
  local value="$3"

  local full_key="zfsRepConfig_sendOptions_${short_flag}"
  local env_file
  env_file="$(env_file_for_task "$task_name")"

  if [[ ! -f "$env_file" ]]; then
    echo "error: env file not found: $env_file" >&2
    return 1
  fi

  local tmp
  tmp="$(mktemp)"
  awk -v key="$full_key" -v val="$value" '
    BEGIN { found=0 }
    {
      if ($0 ~ "^" key "=") {
        print key "=" val
        found=1
      } else {
        print $0
      }
    }
    END {
      if (!found) {
        print key "=" val
      }
    }
  ' "$env_file" > "$tmp"

  mv "$tmp" "$env_file"
  systemctl daemon-reload
  echo "set $full_key=$value in $env_file"
}

get_env_flag() {
  local task_name="$1"
  local short_flag="$2"
  local full_key="zfsRepConfig_sendOptions_${short_flag}"
  local env_file
  env_file="$(env_file_for_task "$task_name")"

  if [[ ! -f "$env_file" ]]; then
    echo "error: env file not found: $env_file" >&2
    return 1
  fi

  local value
  value="$(awk -F= -v key="$full_key" '$1==key { print $2 }' "$env_file" | tail -1 | tr -d '\r' | sed 's/[[:space:]]*$//')"
  if [[ -z "$value" ]]; then
    value="unset"
  fi
  echo "$value"
}

wait_for_unit_running() {
  local unit="$1"
  local timeout_sec="${2:-60}"
  local start_ts now active sub
  start_ts="$(date +%s)"

  while true; do
    active="$(systemctl show "$unit" -p ActiveState --value || true)"
    sub="$(systemctl show "$unit" -p SubState --value || true)"

    if [[ "$active" == "active" && "$sub" == "running" ]]; then
      return 0
    fi

    now="$(date +%s)"
    if (( now - start_ts >= timeout_sec )); then
      echo "timeout waiting for $unit to become active/running (last: ActiveState=$active SubState=$sub)" >&2
      return 1
    fi

    sleep 1
  done
}

wait_for_unit_finished() {
  local unit="$1"
  local timeout_sec="${2:-600}"
  local start_ts now active sub
  start_ts="$(date +%s)"

  while true; do
    active="$(systemctl show "$unit" -p ActiveState --value || true)"
    sub="$(systemctl show "$unit" -p SubState --value || true)"

    if [[ "$active" == "inactive" || "$active" == "failed" ]]; then
      return 0
    fi

    now="$(date +%s)"
    if (( now - start_ts >= timeout_sec )); then
      echo "timeout waiting for $unit to finish (last: ActiveState=$active SubState=$sub)" >&2
      return 1
    fi

    sleep 1
  done
}

wait_for_non_dash_token_local() {
  local dataset="$1"
  local timeout_sec="${2:-30}"
  local start_ts now token
  start_ts="$(date +%s)"

  while true; do
    token="$(zfs get -H -o value receive_resume_token "$dataset" 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]*$//' || true)"
    if [[ -n "$token" && "$token" != "-" ]]; then
      echo "$token"
      return 0
    fi

    now="$(date +%s)"
    if (( now - start_ts >= timeout_sec )); then
      return 1
    fi

    sleep 1
  done
}

wait_for_non_dash_token_remote() {
  local dataset="$1"
  local user="$2"
  local host="$3"
  local port="${4:-22}"
  local timeout_sec="${5:-30}"
  local start_ts now token
  start_ts="$(date +%s)"

  while true; do
    token="$(ssh -p "$port" -o BatchMode=yes -o ConnectTimeout=10 "$user@$host" \
      "zfs get -H -o value receive_resume_token '$dataset'" 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]*$//' || true)"
    if [[ -n "$token" && "$token" != "-" ]]; then
      echo "$token"
      return 0
    fi

    now="$(date +%s)"
    if (( now - start_ts >= timeout_sec )); then
      return 1
    fi

    sleep 1
  done
}

cmd_preflight() {
  local pool="${1:-}"

  echo "== preflight =="
  date -Is
  python3 --version || true
  zfs version || true
  mbuffer --version 2>&1 | head -1 || true
  pv --version 2>&1 | head -1 || true
  nc -h 2>&1 | head -5 || true

  if [[ -n "$pool" ]]; then
    zpool status "$pool"
  else
    zpool status
  fi
}

cmd_start() {
  local task_name="$1"
  local unit
  unit="$(unit_for_task "$task_name")"
  systemctl start "$unit"
  echo "started $unit"
}

cmd_stop() {
  local task_name="$1"
  local unit
  unit="$(unit_for_task "$task_name")"
  systemctl stop "$unit"
  echo "stopped $unit"
}

cmd_status() {
  local task_name="$1"
  local unit
  unit="$(unit_for_task "$task_name")"
  systemctl show "$unit" -p ActiveState -p SubState -p Result -p ExecMainStatus -p StatusText
}

cmd_logs() {
  local task_name="$1"
  local lines="${2:-120}"
  local unit
  unit="$(unit_for_task "$task_name")"
  journalctl -u "$unit" -n "$lines" --no-pager
}

cmd_set_flag() {
  local task_name="$1"
  local flag_name="$2"
  local flag_value="$3"

  case "$flag_name" in
    dryRun|forceFullSend|resumeOnly) ;;
    *)
      echo "error: unsupported flag '$flag_name'" >&2
      return 1
      ;;
  esac

  case "$flag_value" in
    true|false) ;;
    *)
      echo "error: flag value must be true|false" >&2
      return 1
      ;;
  esac

  set_env_flag "$task_name" "$flag_name" "$flag_value"
}

cmd_clear_one_shots() {
  local task_name="$1"
  set_env_flag "$task_name" "dryRun" "false"
  set_env_flag "$task_name" "forceFullSend" "false"
  set_env_flag "$task_name" "resumeOnly" "false"
  echo "cleared one-shot flags for $task_name"
}

cmd_token_local() {
  local dataset="$1"
  zfs get -H -o value receive_resume_token "$dataset"
}

cmd_token_remote() {
  local dataset="$1"
  local user="$2"
  local host="$3"
  local port="${4:-22}"
  ssh -p "$port" -o BatchMode=yes -o ConnectTimeout=10 "$user@$host" \
    "zfs get -H -o value receive_resume_token '$dataset'"
}

cmd_remote_mbuffer() {
  local user="$1"
  local host="$2"
  local port="${3:-22}"

  if ssh -p "$port" -o BatchMode=yes -o ConnectTimeout=10 "$user@$host" "command -v mbuffer >/dev/null 2>&1"; then
    echo "PASS: mbuffer is installed on $user@$host"
    ssh -p "$port" -o BatchMode=yes -o ConnectTimeout=10 "$user@$host" "mbuffer --version 2>&1 | head -1"
  else
    echo "FAIL: mbuffer is not installed (or not reachable) on $user@$host" >&2
    return 1
  fi
}

cmd_discover_tasks() {
  local tasks
  mapfile -t tasks < <(list_task_names)

  if [[ ${#tasks[@]} -eq 0 ]]; then
    echo "No ZFS replication task env files found under /etc/systemd/system."
    return 1
  fi

  echo "== discovered zfs replication tasks =="
  for t in "${tasks[@]}"; do
    describe_task_config "$t"
  done
}

cmd_autotest_all() {
  local mode="${1:-dry-run}"
  local timeout_sec="${2:-900}"
  local tasks
  local pass_count=0
  local fail_count=0
  local task

  case "$mode" in
    dry-run|live) ;;
    *)
      echo "error: mode must be dry-run or live" >&2
      return 1
      ;;
  esac

  mapfile -t tasks < <(list_task_names)
  if [[ ${#tasks[@]} -eq 0 ]]; then
    echo "No ZFS replication tasks found to test."
    return 1
  fi

  echo "== autotest-all mode=$mode timeout=${timeout_sec}s tasks=${#tasks[@]} =="

  for task in "${tasks[@]}"; do
    local unit env_file transfer host user data_port ssh_port result exec_status
    unit="$(unit_for_task "$task")"
    env_file="$(env_file_for_task "$task")"

    transfer="$(env_read_key "$env_file" "zfsRepConfig_sendOptions_transferMethod")"
    host="$(env_read_key "$env_file" "zfsRepConfig_destDataset_host")"
    user="$(env_read_key "$env_file" "zfsRepConfig_destDataset_user")"
    data_port="$(env_read_key "$env_file" "zfsRepConfig_destDataset_port")"
    ssh_port="$(env_read_key "$env_file" "zfsRepConfig_destDataset_sshPort")"

    transfer="${transfer:-ssh}"
    user="${user:-root}"
    data_port="${data_port:-22}"
    if [[ -z "$ssh_port" ]]; then
      if [[ "$transfer" == "netcat" || "$transfer" == "mbuffer" ]]; then
        ssh_port="22"
      else
        ssh_port="$data_port"
      fi
    fi

    echo
    echo "== autotest task: $task =="
    describe_task_config "$task"

    if [[ -n "$host" ]]; then
      if ! ssh -p "$ssh_port" -o BatchMode=yes -o ConnectTimeout=10 "$user@$host" "true" >/dev/null 2>&1; then
        echo "FAIL: SSH precheck failed for $user@$host:$ssh_port" >&2
        fail_count=$((fail_count + 1))
        continue
      fi

      if [[ "$transfer" == "netcat" || "$transfer" == "mbuffer" ]]; then
        if [[ "$data_port" == "22" ]]; then
          echo "FAIL: netcat/mbuffer transfer uses data port 22; choose a non-22 data port" >&2
          fail_count=$((fail_count + 1))
          continue
        fi
        if ! cmd_remote_mbuffer "$user" "$host" "$ssh_port"; then
          echo "WARN: remote mbuffer unavailable; task will fall back to local-only buffering"
        fi
      fi
    fi

    cmd_clear_one_shots "$task"
    if [[ "$mode" == "dry-run" ]]; then
      cmd_set_flag "$task" dryRun true
    fi

    cmd_start "$task"

    if ! wait_for_unit_finished "$unit" "$timeout_sec"; then
      echo "FAIL: timeout waiting for $unit to finish" >&2
      cmd_logs "$task" 160 || true
      fail_count=$((fail_count + 1))
      continue
    fi

    result="$(systemctl show "$unit" -p Result --value || true)"
    exec_status="$(systemctl show "$unit" -p ExecMainStatus --value || true)"

    if [[ "$result" == "success" && "$exec_status" == "0" ]]; then
      echo "PASS: $task (Result=$result ExecMainStatus=$exec_status)"
      pass_count=$((pass_count + 1))
    else
      echo "FAIL: $task (Result=$result ExecMainStatus=$exec_status)" >&2
      cmd_logs "$task" 180 || true
      fail_count=$((fail_count + 1))
    fi
  done

  echo
  echo "== autotest summary =="
  echo "mode=$mode pass=$pass_count fail=$fail_count total=${#tasks[@]}"

  if (( fail_count > 0 )); then
    return 1
  fi
}

cmd_get_flag() {
  local task_name="$1"
  local flag_name="$2"

  case "$flag_name" in
    dryRun|forceFullSend|resumeOnly) ;;
    *)
      echo "error: unsupported flag '$flag_name'" >&2
      return 1
      ;;
  esac

  get_env_flag "$task_name" "$flag_name"
}

cmd_interrupt_main() {
  local task_name="$1"
  local signal="${2:-KILL}"
  local unit
  unit="$(unit_for_task "$task_name")"
  systemctl kill --kill-who=main --signal="$signal" "$unit"
  echo "sent SIG${signal} to main process of $unit"
}

cmd_scenario_resume_token_local() {
  local task_name="$1"
  local dest_dataset="$2"
  local interrupt_after="${3:-8}"
  local token_wait="${4:-30}"

  local unit
  unit="$(unit_for_task "$task_name")"

  echo "== scenario: resume token (local destination) =="
  cmd_clear_one_shots "$task_name"
  cmd_start "$task_name"
  wait_for_unit_running "$unit" 60

  echo "unit is running; waiting ${interrupt_after}s before interruption"
  sleep "$interrupt_after"
  cmd_interrupt_main "$task_name" KILL

  echo "waiting up to ${token_wait}s for receive_resume_token on $dest_dataset"
  if token="$(wait_for_non_dash_token_local "$dest_dataset" "$token_wait")"; then
    echo "PASS: resume token present: $token"
  else
    echo "FAIL: no resume token observed on $dest_dataset" >&2
    return 1
  fi
}

cmd_scenario_resume_token_remote() {
  local task_name="$1"
  local dest_dataset="$2"
  local user="$3"
  local host="$4"
  local port="${5:-22}"
  local interrupt_after="${6:-8}"
  local token_wait="${7:-30}"

  local unit
  unit="$(unit_for_task "$task_name")"

  echo "== scenario: resume token (remote destination) =="
  cmd_clear_one_shots "$task_name"
  cmd_start "$task_name"
  wait_for_unit_running "$unit" 60

  echo "unit is running; waiting ${interrupt_after}s before interruption"
  sleep "$interrupt_after"
  cmd_interrupt_main "$task_name" KILL

  echo "waiting up to ${token_wait}s for remote receive_resume_token on $user@$host:$dest_dataset"
  if token="$(wait_for_non_dash_token_remote "$dest_dataset" "$user" "$host" "$port" "$token_wait")"; then
    echo "PASS: resume token present: $token"
  else
    echo "FAIL: no remote resume token observed on $user@$host:$dest_dataset" >&2
    return 1
  fi
}

cmd_scenario_resume_only_no_token_local() {
  local task_name="$1"
  local dest_dataset="$2"
  local finish_wait="${3:-90}"
  local unit
  local token_before token_after

  unit="$(unit_for_task "$task_name")"

  echo "== scenario: resumeOnly with no token (local destination) =="
  cmd_clear_one_shots "$task_name"
  token_before="$(cmd_token_local "$dest_dataset" | tr -d '\r' | sed 's/[[:space:]]*$//')"
  if [[ "$token_before" != "-" ]]; then
    echo "FAIL: destination has an existing token ($token_before); clear it before this scenario" >&2
    return 1
  fi

  cmd_set_flag "$task_name" "resumeOnly" "true"
  cmd_start "$task_name"
  wait_for_unit_finished "$unit" "$finish_wait"

  token_after="$(cmd_token_local "$dest_dataset" | tr -d '\r' | sed 's/[[:space:]]*$//')"
  if [[ "$token_after" != "-" ]]; then
    echo "FAIL: token unexpectedly appeared after resumeOnly run: $token_after" >&2
    return 1
  fi

  if [[ "$(cmd_get_flag "$task_name" "resumeOnly")" != "false" ]]; then
    echo "FAIL: resumeOnly one-shot did not clear back to false" >&2
    return 1
  fi

  echo "PASS: resumeOnly no-token path completed and one-shot flag cleared"
}

cmd_scenario_force_full_send_clears() {
  local task_name="$1"
  local finish_wait="${2:-900}"
  local unit
  local result exec_status flag_value

  unit="$(unit_for_task "$task_name")"

  echo "== scenario: forceFullSend clears after success =="
  cmd_clear_one_shots "$task_name"
  cmd_set_flag "$task_name" "forceFullSend" "true"
  cmd_start "$task_name"
  wait_for_unit_finished "$unit" "$finish_wait"

  result="$(systemctl show "$unit" -p Result --value || true)"
  exec_status="$(systemctl show "$unit" -p ExecMainStatus --value || true)"
  flag_value="$(cmd_get_flag "$task_name" "forceFullSend")"

  if [[ "$result" != "success" || "$exec_status" != "0" ]]; then
    echo "FAIL: run was not successful (Result=$result ExecMainStatus=$exec_status)" >&2
    return 1
  fi

  if [[ "$flag_value" != "false" ]]; then
    echo "FAIL: forceFullSend one-shot did not clear (value=$flag_value)" >&2
    return 1
  fi

  echo "PASS: successful run and forceFullSend one-shot flag cleared"
}

# ---------------------------------------------------------------------------
# Hierarchy scenarios
#
# Unlike the scenarios above, these do not drive a configured task. They build
# disposable file-backed pools because they must corrupt the destination to
# exercise planner recovery, which is never acceptable on real task data.
# Only the hrepsrc/hrepdst pools and /var/tmp/hrep are touched.
# ---------------------------------------------------------------------------

HIER_SRC_POOL="hrepsrc"
HIER_DST_POOL="hrepdst"
HIER_SRC_FS="${HIER_SRC_POOL}/data"
HIER_DST_FS="${HIER_DST_POOL}/backup"
HIER_WORK_DIR="/var/tmp/hrep"
HIER_IMG_SIZE="512M"
HIER_TASK="hrepharness"
HIER_LOG="/tmp/zfs_rep_debug_${HIER_TASK}.log"
HIER_FAILURES=0
HIER_RC=0
HIER_SNAP_BEFORE=""

hier_say()  { printf '\n== %s ==\n' "$*"; }
hier_info() { printf '   %s\n' "$*"; }
hier_pass() { printf '   PASS %s\n' "$*"; }
hier_fail() { printf '   FAIL %s\n' "$*"; HIER_FAILURES=$((HIER_FAILURES + 1)); }

# Snapshot names carry second resolution, so back-to-back runs collide on the
# name and trip the workflow's duplicate-start guard, which exits 0 silently.
hier_wait_tick() {
  local start
  start="$(date +%s)"
  while [[ "$(date +%s)" == "$start" ]]; do
    sleep 0.2
  done
}

hier_rep_script() {
  local base candidate
  base="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  for candidate in \
    "${ZFS_REP_SCRIPT:-}" \
    "$base/system_files/opt/45drives/houston/scheduler/scripts/replication-script.py" \
    "$base/scripts/replication-script.py" \
    "/opt/45drives/houston/scheduler/scripts/replication-script.py"
  do
    if [[ -n "$candidate" && -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  echo "error: cannot find replication-script.py; set ZFS_REP_SCRIPT" >&2
  return 1
}

hier_require_root() {
  if [[ ${EUID} -ne 0 ]]; then
    echo "error: hierarchy scenarios must run as root (they create and destroy zpools)" >&2
    exit 1
  fi
  hier_rep_script >/dev/null
}

hier_teardown() {
  zpool destroy -f "$HIER_SRC_POOL" 2>/dev/null || true
  zpool destroy -f "$HIER_DST_POOL" 2>/dev/null || true
  rm -rf "$HIER_WORK_DIR"
  rm -f "$HIER_LOG"
}

hier_create_pools() {
  hier_teardown
  mkdir -p "$HIER_WORK_DIR"
  truncate -s "$HIER_IMG_SIZE" "$HIER_WORK_DIR/src.img"
  truncate -s "$HIER_IMG_SIZE" "$HIER_WORK_DIR/dst.img"
  zpool create -f -m "$HIER_WORK_DIR/mnt-src" "$HIER_SRC_POOL" "$HIER_WORK_DIR/src.img"
  zpool create -f -m "$HIER_WORK_DIR/mnt-dst" "$HIER_DST_POOL" "$HIER_WORK_DIR/dst.img"
}

hier_write_data() {
  local tag="$1" fs mount
  shift
  for fs in "$@"; do
    mount="$(zfs get -H -o value mountpoint "$fs")"
    dd if=/dev/urandom of="$mount/${tag}.bin" bs=1M count=2 status=none
  done
  sync
}

hier_setup() {
  hier_create_pools
  zfs create "$HIER_SRC_FS"
  zfs create "$HIER_SRC_FS/samba"
  zfs create "$HIER_SRC_FS/media"
  hier_write_data seed "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
}

# hier_run_task <allowOverwrite> <useExistingDest> [forceFullSend] [quiet]
# Never aborts under `set -e`; the exit code lands in HIER_RC.
hier_run_task() {
  local allow_overwrite="$1" use_existing="$2" force_full="${3:-false}" quiet="${4:-}"
  local script
  script="$(hier_rep_script)"
  rm -f "$HIER_LOG"
  HIER_SNAP_BEFORE="$(hier_newest_snap "$HIER_SRC_FS")"
  hier_wait_tick

  local -a env_args=(
    taskName="$HIER_TASK"
    ZFS_REP_DEBUG=1
    ZFS_REP_DEBUG_LOG="$HIER_LOG"
    zfsRepConfig_direction=push
    zfsRepConfig_sourceDataset_pool="$HIER_SRC_POOL"
    zfsRepConfig_sourceDataset_dataset="$HIER_SRC_FS"
    zfsRepConfig_destDataset_pool="$HIER_DST_POOL"
    zfsRepConfig_destDataset_dataset="$HIER_DST_FS"
    zfsRepConfig_destDataset_host=""
    zfsRepConfig_destDataset_user=root
    zfsRepConfig_sendOptions_recursive_flag=true
    zfsRepConfig_sendOptions_includeIntermediateSnapshots=true
    zfsRepConfig_sendOptions_transferMethod=local
    zfsRepConfig_sendOptions_allowOverwrite="$allow_overwrite"
    zfsRepConfig_sendOptions_useExistingDest="$use_existing"
    zfsRepConfig_sendOptions_forceFullSend="$force_full"
  )

  set +e
  if [[ "$quiet" == "quiet" ]]; then
    env "${env_args[@]}" python3 "$script" >/dev/null 2>&1
  else
    env "${env_args[@]}" python3 "$script"
  fi
  HIER_RC=$?
  set -e
  return 0
}

hier_last_recv_cmd() {
  ( grep 'PIPE recv cmd=' "$HIER_LOG" 2>/dev/null || true ) | tail -1
}

hier_newest_snap() {
  ( zfs list -H -o name -t snapshot -s createtxg -d 1 "$1" 2>/dev/null || true ) | tail -1
}

hier_dest_snap_count() {
  ( zfs list -H -o name -t snapshot -r "$HIER_DST_FS" 2>/dev/null || true ) | wc -l
}

hier_dest_tree() {
  ( zfs list -H -o name -t snapshot -r "$HIER_DST_FS" 2>/dev/null || true ) | sed 's/^/     /'
}

hier_expect_rc() {
  local expected="$1" what="$2"
  if [[ "$HIER_RC" -eq "$expected" ]]; then
    hier_pass "$what (exit $HIER_RC)"
  else
    hier_fail "$what: expected exit $expected, got $HIER_RC"
  fi
}

# Exit 0 alone is not proof of work; the duplicate-start guard also exits 0.
hier_expect_new_snapshot() {
  local what="$1" now
  now="$(hier_newest_snap "$HIER_SRC_FS")"
  if [[ -n "$now" && "$now" != "$HIER_SNAP_BEFORE" ]]; then
    hier_pass "$what created ${now#*@}"
  else
    hier_fail "$what created no new snapshot (still ${HIER_SNAP_BEFORE:-none})"
  fi
}

hier_expect_force_flag() {
  local want="$1" line
  line="$(hier_last_recv_cmd)"
  if [[ -z "$line" ]]; then
    hier_fail "no 'PIPE recv cmd=' line in $HIER_LOG"
    return 0
  fi
  if [[ "$want" == "yes" ]]; then
    if [[ "$line" == *" -F"* ]]; then
      hier_pass "recv used -F: ${line##*cmd=}"
    else
      hier_fail "recv should have used -F: ${line##*cmd=}"
    fi
  else
    if [[ "$line" == *" -F"* ]]; then
      hier_fail "recv used -F but should not have: ${line##*cmd=}"
    else
      hier_pass "recv did not use -F: ${line##*cmd=}"
    fi
  fi
}

hier_expect_base() {
  local want="$1" line
  line="$( ( grep 'send_cmd:' "$HIER_LOG" 2>/dev/null || true ) | tail -1 )"
  if [[ "$line" == *"$want"* ]]; then
    hier_pass "incremental base is $want"
  else
    hier_fail "expected base $want in: $line"
  fi
}

cmd_scenario_hierarchy_clean() {
  hier_say "hierarchy clean: healthy recursive incremental must not use -F"
  hier_setup
  hier_run_task false false false quiet; hier_expect_rc 0 "initial full send"; hier_expect_new_snapshot "initial full send"
  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
  hier_run_task false false; hier_expect_rc 0 "second run (incremental)"; hier_expect_new_snapshot "second run"
  hier_expect_force_flag no
  hier_info "destination snapshots:"; hier_dest_tree
}

cmd_scenario_hierarchy_child_behind() {
  hier_say "hierarchy child-behind: must fall back to an older base the whole tree shares"
  hier_setup
  hier_run_task false false false quiet; hier_expect_rc 0 "run 1"; hier_expect_new_snapshot "run 1"
  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
  hier_run_task false false false quiet; hier_expect_rc 0 "run 2"; hier_expect_new_snapshot "run 2"

  local victim shared_suffix
  victim="$(hier_newest_snap "$HIER_DST_FS/samba")"
  hier_info "simulating a partial receive by destroying $victim"
  zfs destroy "$victim"
  shared_suffix="$(hier_newest_snap "$HIER_DST_FS/samba" | cut -d@ -f2)"

  hier_write_data third "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"

  hier_info "run 3 without Allow Overwrite (must refuse and change nothing):"
  hier_run_task false false false quiet; hier_expect_rc 2 "refuses rollback without Allow Overwrite"

  hier_info "run 3 with Allow Overwrite (must resync from the older shared base):"
  hier_run_task true false; hier_expect_rc 0 "resyncs incrementally"; hier_expect_new_snapshot "run 3"
  hier_expect_base "${HIER_SRC_FS}@${shared_suffix}"
  hier_expect_force_flag yes
  hier_info "destination snapshots:"; hier_dest_tree
}

cmd_scenario_hierarchy_child_orphan() {
  hier_say "hierarchy child-orphan: no shared base on a child must fail loudly, never full-send"
  hier_setup
  hier_run_task false false false quiet; hier_expect_rc 0 "run 1"; hier_expect_new_snapshot "run 1"

  hier_info "destroying every destination snapshot on the child and planting a foreign one"
  zfs destroy "$HIER_DST_FS/samba@%" 2>/dev/null || true
  zfs snapshot "$HIER_DST_FS/samba@foreign"
  local before after
  before="$(hier_dest_snap_count)"

  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
  hier_run_task true false; hier_expect_rc 2 "refuses even with Allow Overwrite enabled"

  after="$(hier_dest_snap_count)"
  if [[ "$before" -eq "$after" ]]; then
    hier_pass "destination untouched ($after snapshots)"
  else
    hier_fail "destination snapshot count changed $before -> $after"
  fi
}

cmd_scenario_hierarchy_child_no_snaps() {
  hier_say "hierarchy child-no-snaps: destination child with zero snapshots must be caught before send"
  hier_setup
  hier_run_task false false false quiet; hier_expect_rc 0 "run 1"; hier_expect_new_snapshot "run 1"

  hier_info "destroying every snapshot on $HIER_DST_FS/samba while leaving the dataset in place"
  zfs destroy "$HIER_DST_FS/samba@%" 2>/dev/null || true
  local before after
  before="$(hier_dest_snap_count)"

  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
  hier_run_task true false; hier_expect_rc 2 "refuses instead of sending an unreceivable stream"

  after="$(hier_dest_snap_count)"
  if [[ "$before" -eq "$after" ]]; then
    hier_pass "destination untouched ($after snapshots)"
  else
    hier_fail "destination snapshot count changed $before -> $after"
  fi
}

cmd_scenario_hierarchy_dest_ahead() {
  hier_say "hierarchy dest-ahead: destination-side snapshots require explicit Allow Overwrite"
  hier_setup
  hier_run_task false false false quiet; hier_expect_rc 0 "run 1"; hier_expect_new_snapshot "run 1"
  zfs snapshot "$HIER_DST_FS/samba@local-extra"
  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"

  hier_run_task false false false quiet; hier_expect_rc 2 "refuses to roll back without Allow Overwrite"
  if zfs list -t snapshot "$HIER_DST_FS/samba@local-extra" >/dev/null 2>&1; then
    hier_pass "destination-only snapshot survived the refusal"
  else
    hier_fail "destination-only snapshot was destroyed without Allow Overwrite"
  fi

  hier_run_task true false; hier_expect_rc 0 "proceeds with Allow Overwrite"; hier_expect_new_snapshot "overwrite run"
  hier_expect_force_flag yes
}

cmd_scenario_hierarchy_existing_data() {
  hier_say "hierarchy existing-data: an unexpected populated destination must not be wiped"
  hier_create_pools
  zfs create "$HIER_SRC_FS"
  zfs create "$HIER_SRC_FS/samba"
  hier_write_data seed "$HIER_SRC_FS" "$HIER_SRC_FS/samba"

  zfs create "$HIER_DST_FS"
  local dst_mount
  dst_mount="$(zfs get -H -o value mountpoint "$HIER_DST_FS")"
  echo "irreplaceable customer data" > "$dst_mount/precious.txt"
  sync

  hier_info "Allow Overwrite ON, Use Existing Destination OFF -> must refuse to force"
  hier_run_task true false
  if [[ "$HIER_RC" -ne 0 ]]; then
    hier_pass "run failed safely instead of forcing (exit $HIER_RC)"
  else
    hier_fail "run succeeded; check whether it overwrote the destination"
  fi
  hier_expect_force_flag no
  if [[ -f "$dst_mount/precious.txt" ]]; then
    hier_pass "unsnapshotted destination data survived"
  else
    hier_fail "unsnapshotted destination data was destroyed"
  fi

  hier_info "Use Existing Destination ON + Allow Overwrite ON -> destructive BY DESIGN"
  hier_run_task true true; hier_expect_rc 0 "explicit overwrite accepted"
  hier_expect_force_flag yes
}

cmd_scenario_hierarchy_all() {
  cmd_scenario_hierarchy_clean
  cmd_scenario_hierarchy_child_behind
  cmd_scenario_hierarchy_child_orphan
  cmd_scenario_hierarchy_child_no_snaps
  cmd_scenario_hierarchy_dest_ahead
  cmd_scenario_hierarchy_existing_data
  hier_teardown
  hier_say "hierarchy scenarios finished with $HIER_FAILURES failure(s)"
  [[ "$HIER_FAILURES" -eq 0 ]]
}

main() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi

  local cmd="$1"
  shift

  case "$cmd" in
    preflight)
      cmd_preflight "$@"
      ;;
    start)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      cmd_start "$1"
      ;;
    stop)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      cmd_stop "$1"
      ;;
    status)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      cmd_status "$1"
      ;;
    logs)
      [[ $# -ge 1 ]] || { usage; exit 1; }
      cmd_logs "$@"
      ;;
    set-flag)
      [[ $# -eq 3 ]] || { usage; exit 1; }
      cmd_set_flag "$1" "$2" "$3"
      ;;
    clear-one-shots)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      cmd_clear_one_shots "$1"
      ;;
    token-local)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      cmd_token_local "$1"
      ;;
    token-remote)
      [[ $# -ge 3 && $# -le 4 ]] || { usage; exit 1; }
      cmd_token_remote "$@"
      ;;
    remote-mbuffer)
      [[ $# -ge 2 && $# -le 3 ]] || { usage; exit 1; }
      cmd_remote_mbuffer "$@"
      ;;
    discover-tasks)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      cmd_discover_tasks
      ;;
    autotest-all)
      [[ $# -le 2 ]] || { usage; exit 1; }
      cmd_autotest_all "$@"
      ;;
    get-flag)
      [[ $# -eq 2 ]] || { usage; exit 1; }
      cmd_get_flag "$1" "$2"
      ;;
    interrupt-main)
      [[ $# -ge 1 && $# -le 2 ]] || { usage; exit 1; }
      cmd_interrupt_main "$@"
      ;;
    scenario-resume-token-local)
      [[ $# -ge 2 && $# -le 4 ]] || { usage; exit 1; }
      cmd_scenario_resume_token_local "$@"
      ;;
    scenario-resume-token-remote)
      [[ $# -ge 4 && $# -le 7 ]] || { usage; exit 1; }
      cmd_scenario_resume_token_remote "$@"
      ;;
    scenario-resume-only-no-token-local)
      [[ $# -ge 2 && $# -le 3 ]] || { usage; exit 1; }
      cmd_scenario_resume_only_no_token_local "$@"
      ;;
    scenario-force-full-send-clears)
      [[ $# -ge 1 && $# -le 2 ]] || { usage; exit 1; }
      cmd_scenario_force_full_send_clears "$@"
      ;;
    scenario-hierarchy-all)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      cmd_scenario_hierarchy_all
      ;;
    scenario-hierarchy-clean|scenario-hierarchy-child-behind|scenario-hierarchy-child-orphan|scenario-hierarchy-child-no-snaps|scenario-hierarchy-dest-ahead|scenario-hierarchy-existing-data)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      # Pools are left standing for inspection; use scenario-hierarchy-teardown.
      "cmd_${cmd//-/_}"
      hier_say "finished with $HIER_FAILURES failure(s)"
      [[ "$HIER_FAILURES" -eq 0 ]]
      ;;
    scenario-hierarchy-teardown)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      hier_teardown
      echo "torn down $HIER_SRC_POOL / $HIER_DST_POOL and $HIER_WORK_DIR"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
