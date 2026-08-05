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
  live-replication-harness.sh get-flag <task_name> <dryRun|forceFullSend|resumeOnly>
  live-replication-harness.sh interrupt-main <task_name> [signal]
  live-replication-harness.sh scenario-resume-token-local <task_name> <dest_dataset> [interrupt_after_sec] [token_wait_sec]
  live-replication-harness.sh scenario-resume-token-remote <task_name> <dest_dataset> <remote_user> <remote_host> [remote_ssh_port] [interrupt_after_sec] [token_wait_sec]
  live-replication-harness.sh scenario-resume-only-no-token-local <task_name> <dest_dataset> [finish_wait_sec]
  live-replication-harness.sh scenario-force-full-send-clears <task_name> [finish_wait_sec]

Examples:
  live-replication-harness.sh preflight tank
  live-replication-harness.sh set-flag TestLocalPush dryRun true
  live-replication-harness.sh scenario-resume-token-local TestLocalPush tank/sharebackup 8 45
  live-replication-harness.sh scenario-resume-token-remote TestRemotePush tank/backup root 192.168.0.1 22 8 45
  live-replication-harness.sh scenario-resume-only-no-token-local TestLocalPush tank/sharebackup 90
  live-replication-harness.sh scenario-force-full-send-clears TestLocalPush 900
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
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
