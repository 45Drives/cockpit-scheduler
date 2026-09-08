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
  live-replication-harness.sh list-disks
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

Hierarchy scenarios (root; build disposable hrepsrc/hrepdst pools):
  live-replication-harness.sh scenario-hierarchy-all
  live-replication-harness.sh scenario-hierarchy-matrix
  live-replication-harness.sh scenario-hierarchy-clean [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-child-behind [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-child-orphan [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-child-no-snaps [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-dest-ahead [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-existing-data [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-tags [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-retention [direction] [transport]
  live-replication-harness.sh scenario-hierarchy-teardown
  live-replication-harness.sh hier-notify-run [direction] [transport]

  hier-notify-run replays one replication over the pools an earlier scenario left
  standing, inside a transient Type=notify unit, so systemd StatusText carries the
  live progress percentage. The scenarios themselves exec the script directly and
  therefore show no percentage at all.

Regression suite for the resume + SSH cipher work (also disposable pools):
  live-replication-harness.sh verify-fixes
  live-replication-harness.sh unit-tests
  live-replication-harness.sh scenario-resume-all
  live-replication-harness.sh scenario-resume-continues
  live-replication-harness.sh scenario-resume-only-stops
  live-replication-harness.sh scenario-cipher-all
  live-replication-harness.sh scenario-cipher-availability [host] [user] [port]
  live-replication-harness.sh scenario-cipher-send <cipher>
  live-replication-harness.sh scenario-cipher-send-all
  live-replication-harness.sh scenario-cipher-bench [cipher ...]

  verify-fixes is the one-shot entry point: it runs pytest (source checkout only),
  the resume-continuation scenarios, and the cipher scenarios, skipping the cipher
  group when loopback SSH is unavailable. scenario-cipher-bench times a full send
  per cipher over loopback SSH; set CIPHER_BENCH_MB to change the 256 MiB payload.

  direction is push|pull (default push); transport is local|ssh|netcat|mbuffer
  (default local). Every non-local transport talks to loopback SSH, overridable
  with HIER_REMOTE_HOST. scenario-hierarchy-matrix sweeps the whole grid and
  skips modes whose prerequisites (SSH keys, nc, mbuffer) are missing.

Backing store for the hierarchy pools:
  By default hrepsrc/hrepdst are sparse files under /var/tmp/hrep, sized by
  HIER_IMG_SIZE (default 512M). That is only large enough for smoke tests; any
  workload with real volume should use spare disks instead:

    HIER_SRC_DISKS   space/comma separated devices for hrepsrc (e.g. 'sdb sdc')
    HIER_DST_DISKS   space/comma separated devices for hrepdst
    HIER_VDEV        optional vdev type applied to both pools (mirror, raidz...)
    HIER_SEED_MB     MiB of random data seeded per dataset (default 2)
    HIER_DISK_FORCE  1 to skip the mounted/foreign-pool/root-disk guards

  Devices are wiped on every setup and labelcleared on teardown. Run list-disks
  to see which devices are free.

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
  live-replication-harness.sh scenario-hierarchy-matrix
  live-replication-harness.sh scenario-hierarchy-tags pull mbuffer
  live-replication-harness.sh verify-fixes
  live-replication-harness.sh scenario-cipher-bench aes128-gcm@openssh.com aes128-ctr
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

# Candidate block devices for HIER_SRC_DISKS / HIER_DST_DISKS, annotated with
# why each one is or is not safe to hand to the hierarchy scenarios.
cmd_list_disks() {
  local name size model root_disk dev status mounts labels

  root_disk="$(hier_root_disk)"
  printf '%-12s %-10s %-24s %s\n' DEVICE SIZE MODEL STATUS

  while read -r name size model; do
    dev="/dev/$name"
    status="free"

    if [[ -n "$root_disk" && "$name" == "$root_disk"* ]]; then
      status="IN USE (root filesystem)"
    else
      mounts="$(lsblk -nro MOUNTPOINT "$dev" 2>/dev/null | grep -v '^$' | paste -sd, - || true)"
      labels="$(lsblk -nro FSTYPE,LABEL "$dev" 2>/dev/null | awk '$1 == "zfs_member" {print $2}' | sort -u | paste -sd, - || true)"
      if [[ -n "$mounts" ]]; then
        status="IN USE (mounted: $mounts)"
      elif [[ -n "$labels" ]]; then
        status="zpool label: $labels"
      fi
    fi

    printf '%-12s %-10s %-24s %s\n' "$name" "$size" "${model:--}" "$status"
  done < <(lsblk -dno NAME,SIZE,MODEL 2>/dev/null | grep -Ev '^(loop|sr|zd|ram)')

  echo
  echo "Example:"
  echo "  HIER_SRC_DISKS='sdb sdc' HIER_DST_DISKS='sdd sde' HIER_SEED_MB=512 \\"
  echo "    ./live-replication-harness.sh scenario-hierarchy-clean push local"
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
# disposable pools because they must corrupt the destination to exercise planner
# recovery, which is never acceptable on real task data.
# Only the hrepsrc/hrepdst pools and /var/tmp/hrep are touched.
#
# Backing store: sparse files under /var/tmp/hrep by default, or real block
# devices when HIER_SRC_DISKS/HIER_DST_DISKS are set. Prefer real disks for
# anything that needs volume — file vdevs on the boot drive run out of space
# long before a realistic snapshot workload finishes.
# ---------------------------------------------------------------------------

HIER_SRC_POOL="hrepsrc"
HIER_DST_POOL="hrepdst"
HIER_SRC_FS="${HIER_SRC_POOL}/data"
HIER_DST_FS="${HIER_DST_POOL}/backup"
HIER_WORK_DIR="/var/tmp/hrep"
HIER_IMG_SIZE="${HIER_IMG_SIZE:-512M}"
HIER_SRC_DISKS="${HIER_SRC_DISKS:-}"
HIER_DST_DISKS="${HIER_DST_DISKS:-}"
HIER_VDEV="${HIER_VDEV:-}"
HIER_DISK_FORCE="${HIER_DISK_FORCE:-0}"
HIER_TASK="hrepharness"
HIER_LOG="/tmp/zfs_rep_debug_${HIER_TASK}.log"
HIER_OUT="/tmp/zfs_rep_out_${HIER_TASK}.log"
HIER_FAILURES=0
HIER_RC=0
HIER_SNAP_BEFORE=""

# Transport/direction matrix. Remote modes use loopback SSH so a single box can
# exercise the remote code paths; both pools stay local, so every zfs query in
# this file keeps working unchanged regardless of mode.
HIER_DIRECTION="push"
HIER_TRANSPORT="local"
HIER_HOST=""
HIER_USER="root"
HIER_SSH_PORT="22"
HIER_DATA_PORT="31337"
HIER_SCHEDULE_JSON=""
HIER_SRC_RET_TIME="0"
HIER_SRC_RET_UNIT=""
HIER_DST_RET_TIME="0"
HIER_DST_RET_UNIT=""
HIER_RECURSIVE="true"
HIER_RESUME_ONLY="false"
HIER_SSH_CIPHER=""
HIER_RESUME_SNAP="resumeseed"
HIER_LASTRUN="/etc/systemd/system/houston_scheduler_ZfsReplicationTask_${HIER_TASK}.lastrun"

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

hier_mode_label() {
  printf '%s/%s' "$HIER_DIRECTION" "$HIER_TRANSPORT"
}

# hier_set_mode <push|pull> <local|ssh|netcat|mbuffer>
# `local` means no peer at all; every other transport talks to loopback SSH.
hier_set_mode() {
  HIER_DIRECTION="$1"
  HIER_TRANSPORT="$2"
  if [[ "$HIER_TRANSPORT" == "local" ]]; then
    HIER_HOST=""
  else
    HIER_HOST="${HIER_REMOTE_HOST:-127.0.0.1}"
  fi
}

hier_reset_mode() {
  hier_set_mode push local
  HIER_SCHEDULE_JSON=""
  HIER_RECURSIVE="true"
  HIER_RESUME_ONLY="false"
  HIER_SSH_CIPHER=""
}

# Returns 1 with a reason on stdout when the current mode cannot run here.
hier_mode_unavailable() {
  if [[ "$HIER_DIRECTION" == "pull" && "$HIER_TRANSPORT" == "local" ]]; then
    echo "pull requires a remote source; 'local' is not a pull transport"
    return 0
  fi
  if [[ -n "$HIER_HOST" ]]; then
    if ! ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
         -p "$HIER_SSH_PORT" "${HIER_USER}@${HIER_HOST}" true >/dev/null 2>&1; then
      echo "no passwordless SSH to ${HIER_USER}@${HIER_HOST}:${HIER_SSH_PORT}"
      return 0
    fi
  fi
  case "$HIER_TRANSPORT" in
    netcat)  command -v nc      >/dev/null 2>&1 || { echo "nc not installed"; return 0; } ;;
    mbuffer) command -v mbuffer >/dev/null 2>&1 || { echo "mbuffer not installed"; return 0; } ;;
  esac
  return 1
}

# A two-interval all-wildcard schedule ties on specificity, so tier 0 is chosen
# and every snapshot gets the tier property — which is what we want to assert.
hier_write_schedule() {
  mkdir -p "$HIER_WORK_DIR"
  cat > "$HIER_WORK_DIR/schedule.json" <<'EOF'
{
  "intervals": [
    {"minute": {"value": "*"}, "hour": {"value": "*"}, "day": {"value": "*"}, "month": {"value": "*"}, "year": {"value": "*"}, "dayOfWeek": []},
    {"minute": {"value": "*"}, "hour": {"value": "*"}, "day": {"value": "*"}, "month": {"value": "*"}, "year": {"value": "*"}, "dayOfWeek": []}
  ]
}
EOF
  HIER_SCHEDULE_JSON="$HIER_WORK_DIR/schedule.json"
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
  if hier_disk_mode; then
    local dev
    for dev in $(hier_disk_list "$HIER_SRC_DISKS") $(hier_disk_list "$HIER_DST_DISKS"); do
      zpool labelclear -f "$dev" 2>/dev/null || true
      wipefs -a "$dev" >/dev/null 2>&1 || true
    done
  fi
  rm -rf "$HIER_WORK_DIR"
  rm -f "$HIER_LOG" "$HIER_OUT" "$HIER_LASTRUN"
}

hier_disk_mode() {
  [[ -n "$HIER_SRC_DISKS" && -n "$HIER_DST_DISKS" ]]
}

# Accepts "sdb sdc" or "/dev/sdb,/dev/disk/by-id/..."; emits absolute paths.
hier_disk_list() {
  local raw dev
  raw="${1//,/ }"
  for dev in $raw; do
    [[ "$dev" == /* ]] || dev="/dev/$dev"
    printf '%s\n' "$dev"
  done
}

hier_root_disk() {
  local src
  src="$(findmnt -no SOURCE / 2>/dev/null || true)"
  [[ -n "$src" ]] || return 0
  lsblk -no PKNAME "$src" 2>/dev/null | head -1
}

# Refuse anything that is mounted, holds a foreign zpool label, or backs /.
# HIER_DISK_FORCE=1 skips the checks; it will destroy whatever is on the device.
hier_assert_disk_safe() {
  local dev="$1" root_disk base mp fstype label

  if [[ ! -b "$dev" ]]; then
    echo "error: $dev is not a block device" >&2
    exit 1
  fi
  [[ "$HIER_DISK_FORCE" == "1" ]] && return 0

  base="$(basename "$(readlink -f "$dev")")"
  root_disk="$(hier_root_disk)"
  if [[ -n "$root_disk" && "$base" == "$root_disk"* ]]; then
    echo "error: $dev backs the root filesystem; refusing to use it" >&2
    exit 1
  fi

  while read -r mp; do
    if [[ -n "$mp" ]]; then
      echo "error: $dev (or a partition of it) is mounted at $mp; refusing to use it" >&2
      exit 1
    fi
  done < <(lsblk -nro MOUNTPOINT "$dev" 2>/dev/null)

  while read -r fstype label; do
    if [[ "$fstype" == "zfs_member" && -n "$label" \
          && "$label" != "$HIER_SRC_POOL" && "$label" != "$HIER_DST_POOL" ]]; then
      echo "error: $dev carries a label for foreign zpool '$label'; refusing to use it" >&2
      echo "       set HIER_DISK_FORCE=1 only if that pool is genuinely disposable" >&2
      exit 1
    fi
  done < <(lsblk -nro FSTYPE,LABEL "$dev" 2>/dev/null)
}

hier_img_size_mb() {
  case "$HIER_IMG_SIZE" in
    *[Gg]) echo $(( ${HIER_IMG_SIZE%[Gg]} * 1024 )) ;;
    *[Mm]) echo "${HIER_IMG_SIZE%[Mm]}" ;;
    *) echo "" ;;
  esac
}

# The images are sparse, so ZFS only discovers a short filesystem mid-write, and a
# file vdev that runs out of space suspends the pool — wedging every writer in
# uninterruptible sleep that no signal can clear. Refuse up front instead.
hier_require_space() {
  local need_mb avail_mb size_mb
  size_mb="$(hier_img_size_mb)"
  if [[ -z "$size_mb" ]]; then
    echo "error: unrecognised HIER_IMG_SIZE '$HIER_IMG_SIZE' (use an M or G suffix)" >&2
    exit 1
  fi
  need_mb=$(( size_mb * 2 + 512 ))
  avail_mb="$(df -Pm "$HIER_WORK_DIR" | awk 'NR==2 {print $4}')"
  if [[ -z "$avail_mb" ]] || (( avail_mb < need_mb )); then
    echo "error: $HIER_WORK_DIR has ${avail_mb:-0} MiB free but src.img + dst.img need ${need_mb} MiB" >&2
    echo "       free space, or lower the payload (CIPHER_BENCH_MB), before retrying" >&2
    exit 1
  fi
}

hier_create_pools() {
  hier_teardown
  mkdir -p "$HIER_WORK_DIR"

  # failmode=continue so a disposable pool returns EIO instead of suspending and hanging the run.
  if hier_disk_mode; then
    local dev
    local -a src_devs=() dst_devs=()
    mapfile -t src_devs < <(hier_disk_list "$HIER_SRC_DISKS")
    mapfile -t dst_devs < <(hier_disk_list "$HIER_DST_DISKS")
    for dev in "${src_devs[@]}" "${dst_devs[@]}"; do
      hier_assert_disk_safe "$dev"
    done
    echo "   using real disks: src=[${src_devs[*]}] dst=[${dst_devs[*]}] vdev=${HIER_VDEV:-stripe}"
    zpool create -f -o failmode=continue -m "$HIER_WORK_DIR/mnt-src" \
      "$HIER_SRC_POOL" ${HIER_VDEV:+$HIER_VDEV} "${src_devs[@]}"
    zpool create -f -o failmode=continue -m "$HIER_WORK_DIR/mnt-dst" \
      "$HIER_DST_POOL" ${HIER_VDEV:+$HIER_VDEV} "${dst_devs[@]}"
    return 0
  fi

  hier_require_space
  truncate -s "$HIER_IMG_SIZE" "$HIER_WORK_DIR/src.img"
  truncate -s "$HIER_IMG_SIZE" "$HIER_WORK_DIR/dst.img"
  zpool create -f -o failmode=continue -m "$HIER_WORK_DIR/mnt-src" "$HIER_SRC_POOL" "$HIER_WORK_DIR/src.img"
  zpool create -f -o failmode=continue -m "$HIER_WORK_DIR/mnt-dst" "$HIER_DST_POOL" "$HIER_WORK_DIR/dst.img"
}

hier_write_data() {
  local tag="$1" fs mount
  shift
  for fs in "$@"; do
    mount="$(zfs get -H -o value mountpoint "$fs")"
    dd if=/dev/urandom of="$mount/${tag}.bin" bs=1M count="${HIER_SEED_MB:-2}" status=none
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

# hier_env_kv <allowOverwrite> <useExistingDest> [forceFullSend]
# Emits the task configuration as KEY=VALUE lines so the direct runner and the
# systemd-run wrapper drive an identical environment.
hier_env_kv() {
  local allow_overwrite="$1" use_existing="$2" force_full="${3:-false}" data_port

  if [[ "$HIER_TRANSPORT" == "netcat" || "$HIER_TRANSPORT" == "mbuffer" ]]; then
    data_port="$HIER_DATA_PORT"
  else
    data_port="$HIER_SSH_PORT"
  fi

  cat <<EOF
taskName=$HIER_TASK
ZFS_REP_DEBUG=1
ZFS_REP_DEBUG_LOG=$HIER_LOG
scheduleJsonPath=$HIER_SCHEDULE_JSON
zfsRepConfig_direction=$HIER_DIRECTION
zfsRepConfig_sourceDataset_pool=$HIER_SRC_POOL
zfsRepConfig_sourceDataset_dataset=$HIER_SRC_FS
zfsRepConfig_destDataset_pool=$HIER_DST_POOL
zfsRepConfig_destDataset_dataset=$HIER_DST_FS
zfsRepConfig_destDataset_host=$HIER_HOST
zfsRepConfig_destDataset_user=$HIER_USER
zfsRepConfig_destDataset_sshPort=$HIER_SSH_PORT
zfsRepConfig_destDataset_port=$data_port
zfsRepConfig_sendOptions_recursive_flag=$HIER_RECURSIVE
zfsRepConfig_sendOptions_includeIntermediateSnapshots=true
zfsRepConfig_sendOptions_transferMethod=$HIER_TRANSPORT
zfsRepConfig_sendOptions_sshCipher=$HIER_SSH_CIPHER
zfsRepConfig_sendOptions_resumeOnly=$HIER_RESUME_ONLY
zfsRepConfig_sendOptions_mbufferCallbackHost=$HIER_HOST
zfsRepConfig_sendOptions_allowOverwrite=$allow_overwrite
zfsRepConfig_sendOptions_useExistingDest=$use_existing
zfsRepConfig_sendOptions_forceFullSend=$force_full
zfsRepConfig_snapshotRetention_source_retentionTime=$HIER_SRC_RET_TIME
zfsRepConfig_snapshotRetention_source_retentionUnit=$HIER_SRC_RET_UNIT
zfsRepConfig_snapshotRetention_destination_retentionTime=$HIER_DST_RET_TIME
zfsRepConfig_snapshotRetention_destination_retentionUnit=$HIER_DST_RET_UNIT
EOF
}

# hier_run_task <allowOverwrite> <useExistingDest> [forceFullSend] [quiet]
# Never aborts under `set -e`; the exit code lands in HIER_RC.
# Direction and transport come from HIER_DIRECTION / HIER_TRANSPORT.
hier_run_task() {
  local allow_overwrite="$1" use_existing="$2" force_full="${3:-false}" quiet="${4:-}"
  local script
  script="$(hier_rep_script)"
  rm -f "$HIER_LOG" "$HIER_OUT"
  HIER_SNAP_BEFORE="$(hier_newest_snap "$HIER_SRC_FS")"
  hier_wait_tick

  local -a env_args=()
  mapfile -t env_args < <(hier_env_kv "$allow_overwrite" "$use_existing" "$force_full")

  set +e
  if [[ "$quiet" == "quiet" ]]; then
    env "${env_args[@]}" python3 "$script" >"$HIER_OUT" 2>&1
    HIER_RC=$?
  else
    env "${env_args[@]}" python3 "$script" >"$HIER_OUT" 2>&1
    HIER_RC=$?
    cat "$HIER_OUT"
  fi
  set -e
  return 0
}

hier_newest_snap() {
  ( zfs list -H -o name -t snapshot -s createtxg -d 1 "$1" 2>/dev/null || true ) | tail -1
}

# hier-notify-run: drive the existing hrepsrc/hrepdst pools through a transient
# Type=notify unit. The scenarios above exec the script directly, so NOTIFY_SOCKET
# is unset and every STATUS= line is discarded — this is the only path where the
# progress percentage the UI shows is actually observable.
HIER_NOTIFY_UNIT="hrep-notify-run"

cmd_hier_notify_run() {
  local direction="${1:-push}" transport="${2:-local}"
  local script env_file reason

  hier_require_root
  script="$(hier_rep_script)"

  if ! zfs list -H -o name "$HIER_SRC_FS" >/dev/null 2>&1; then
    echo "error: $HIER_SRC_FS does not exist; run a scenario-hierarchy-* command first" >&2
    exit 1
  fi

  hier_set_mode "$direction" "$transport"
  if reason="$(hier_mode_unavailable)"; then
    echo "error: $(hier_mode_label) unavailable: $reason" >&2
    exit 1
  fi

  hier_write_schedule
  env_file="$HIER_WORK_DIR/task.env"
  hier_env_kv false false false > "$env_file"
  rm -f "$HIER_LOG" "$HIER_OUT"

  systemctl reset-failed "${HIER_NOTIFY_UNIT}.service" >/dev/null 2>&1 || true
  # No --collect: a failed start job must leave the unit behind for status/journal.
  if ! systemd-run --unit="$HIER_NOTIFY_UNIT" --service-type=notify \
       -p EnvironmentFile="$env_file" \
       -p TimeoutStartSec=0 \
       -p WorkingDirectory="$(dirname "$script")" \
       "$(command -v python3)" "$script"; then
    echo
    echo "=== ${HIER_NOTIFY_UNIT}.service failed to start ==="
    systemctl status "${HIER_NOTIFY_UNIT}.service" --no-pager -l || true
    echo
    journalctl -u "${HIER_NOTIFY_UNIT}.service" -n 60 --no-pager || true
    echo
    echo "=== tail $HIER_LOG ==="
    tail -n 40 "$HIER_LOG" 2>/dev/null || echo "(no debug log written)"
    exit 1
  fi

  echo "started ${HIER_NOTIFY_UNIT}.service [$(hier_mode_label)]"
  echo "interrupt from another shell with:"
  echo "  systemctl kill --kill-who=main --signal=KILL ${HIER_NOTIFY_UNIT}.service"
  echo
  hier_notify_follow
}

# Prints StatusText whenever it changes and returns once the unit leaves the
# running state, so it terminates by itself instead of pinning a terminal.
hier_notify_follow() {
  local state status last=""

  while :; do
    state="$(systemctl show "${HIER_NOTIFY_UNIT}.service" -p ActiveState --value 2>/dev/null || echo inactive)"
    status="$(systemctl show "${HIER_NOTIFY_UNIT}.service" -p StatusText --value 2>/dev/null || true)"
    if [[ -n "$status" && "$status" != "$last" ]]; then
      printf '%s  %s\n' "$(date +%H:%M:%S)" "$status"
      last="$status"
    fi
    case "$state" in
      activating|active|deactivating) sleep 1 ;;
      *) break ;;
    esac
  done

  echo
  systemctl show "${HIER_NOTIFY_UNIT}.service" \
    -p ActiveState -p Result -p ExecMainStatus -p StatusText 2>/dev/null || true
  echo
  echo "debug log: $HIER_LOG"
  echo "journal:   journalctl -u ${HIER_NOTIFY_UNIT}.service --no-pager"
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
  # Every transport prints a reproducible "CLI command" containing the receive
  # stage, so this assertion is transport-agnostic.
  line="$( ( grep -o 'zfs recv -s[^|'"'"']*' "$HIER_OUT" 2>/dev/null || true ) | tail -1 )"
  if [[ -z "$line" ]]; then
    hier_fail "no 'zfs recv -s' line in $HIER_OUT"
    return 0
  fi
  if [[ "$want" == "yes" ]]; then
    if [[ "$line" == "zfs recv -s -F"* ]]; then
      hier_pass "recv used -F: $line"
    else
      hier_fail "recv should have used -F: $line"
    fi
  else
    if [[ "$line" == "zfs recv -s -F"* ]]; then
      hier_fail "recv used -F but should not have: $line"
    else
      hier_pass "recv did not use -F: $line"
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

HIER_TASK_PROP="com.45drives_scheduler:task_name"
HIER_TIER_PROP="com.45drives_scheduler:scheduler_interval_tier"

hier_dataset_count() {
  ( zfs list -H -o name -r "$1" 2>/dev/null || true ) | wc -l
}

# hier_expect_tags <root_fs> <snap_suffix> <property> <expected_value> <label>
# `zfs snapshot -r` creates the whole tree but `zfs set` only touches what it is
# told to, so every dataset in the tree must carry the property, not just root.
hier_expect_tags() {
  local fs="$1" suffix="$2" prop="$3" want="$4" label="$5"
  local expected seen=0 bad=0 name value
  expected="$(hier_dataset_count "$fs")"

  while read -r name value; do
    [[ "$name" == *"@${suffix}" ]] || continue
    seen=$((seen + 1))
    if [[ "$value" != "$want" ]]; then
      hier_fail "$label: $name has ${prop}='${value}', expected '${want}'"
      bad=1
    fi
  done < <( zfs get -H -o name,value -t snapshot -r "$prop" "$fs" 2>/dev/null || true )

  if [[ "$seen" -ne "$expected" ]]; then
    hier_fail "$label: ${prop} found on $seen snapshot(s), expected $expected (one per dataset)"
    return 0
  fi
  if [[ "$bad" -eq 0 ]]; then
    hier_pass "$label: all $seen dataset(s) tagged ${prop}=${want}"
  fi
}

hier_snap_suffix() {
  local snap
  snap="$(hier_newest_snap "$1")"
  echo "${snap#*@}"
}

hier_expect_no_snapshots() {
  local fs="$1" suffix="$2" label="$3" left
  left="$( ( zfs list -H -o name -t snapshot -r "$fs" 2>/dev/null || true ) | grep -c "@${suffix}\$" || true )"
  if [[ "$left" -eq 0 ]]; then
    hier_pass "$label: generation @${suffix} pruned from the whole tree"
  else
    hier_fail "$label: $left snapshot(s) of @${suffix} survived retention"
  fi
}

cmd_scenario_hierarchy_clean() {
  hier_say "hierarchy clean [$(hier_mode_label)]: healthy recursive incremental must not use -F"
  hier_setup
  hier_run_task false false false quiet; hier_expect_rc 0 "initial full send"; hier_expect_new_snapshot "initial full send"
  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
  hier_run_task false false; hier_expect_rc 0 "second run (incremental)"; hier_expect_new_snapshot "second run"
  hier_expect_force_flag no
  hier_info "destination snapshots:"; hier_dest_tree
}

cmd_scenario_hierarchy_child_behind() {
  hier_say "hierarchy child-behind [$(hier_mode_label)]: must fall back to an older base the whole tree shares"
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
  hier_say "hierarchy child-orphan [$(hier_mode_label)]: no shared base on a child must fail loudly, never full-send"
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
  hier_say "hierarchy child-no-snaps [$(hier_mode_label)]: destination child with zero snapshots must be caught before send"
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
  hier_say "hierarchy dest-ahead [$(hier_mode_label)]: destination-side snapshots require explicit Allow Overwrite"
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
  hier_say "hierarchy existing-data [$(hier_mode_label)]: an unexpected populated destination must not be wiped"
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

cmd_scenario_hierarchy_tags() {
  hier_say "hierarchy tags [$(hier_mode_label)]: every dataset in the tree must carry task and tier tags"
  hier_setup
  hier_write_schedule

  hier_run_task false false false quiet; hier_expect_rc 0 "initial full send"; hier_expect_new_snapshot "initial full send"
  local suffix
  suffix="$(hier_snap_suffix "$HIER_SRC_FS")"
  hier_info "full-send suffix: $suffix"
  hier_expect_tags "$HIER_SRC_FS" "$suffix" "$HIER_TASK_PROP" "$HIER_TASK" "source (full)"
  hier_expect_tags "$HIER_SRC_FS" "$suffix" "$HIER_TIER_PROP" "t0"          "source (full)"
  hier_expect_tags "$HIER_DST_FS" "$suffix" "$HIER_TASK_PROP" "$HIER_TASK" "destination (full)"
  hier_expect_tags "$HIER_DST_FS" "$suffix" "$HIER_TIER_PROP" "t0"          "destination (full)"

  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
  hier_run_task false false false quiet; hier_expect_rc 0 "incremental send"; hier_expect_new_snapshot "incremental send"
  suffix="$(hier_snap_suffix "$HIER_SRC_FS")"
  hier_info "incremental suffix: $suffix"
  hier_expect_tags "$HIER_SRC_FS" "$suffix" "$HIER_TASK_PROP" "$HIER_TASK" "source (incremental)"
  hier_expect_tags "$HIER_SRC_FS" "$suffix" "$HIER_TIER_PROP" "t0"          "source (incremental)"
  hier_expect_tags "$HIER_DST_FS" "$suffix" "$HIER_TASK_PROP" "$HIER_TASK" "destination (incremental)"
  hier_expect_tags "$HIER_DST_FS" "$suffix" "$HIER_TIER_PROP" "t0"          "destination (incremental)"

  HIER_SCHEDULE_JSON=""
}

cmd_scenario_hierarchy_retention() {
  hier_say "hierarchy retention [$(hier_mode_label)]: tagged children must prune alongside their root"
  hier_setup
  hier_write_schedule

  hier_run_task false false false quiet; hier_expect_rc 0 "run 1"; hier_expect_new_snapshot "run 1"
  local first_suffix
  first_suffix="$(hier_snap_suffix "$HIER_SRC_FS")"
  hier_info "generation 1 suffix: $first_suffix"

  # The smallest supported retention window is one minute, so the first
  # generation has to actually age past it before run 2 can prune it.
  hier_info "waiting 65s for generation 1 to age out of a 1-minute window"
  sleep 65

  hier_write_data second "$HIER_SRC_FS" "$HIER_SRC_FS/samba" "$HIER_SRC_FS/media"
  HIER_SRC_RET_TIME=1; HIER_SRC_RET_UNIT=minutes
  HIER_DST_RET_TIME=1; HIER_DST_RET_UNIT=minutes
  hier_run_task false false false quiet
  HIER_SRC_RET_TIME=0; HIER_SRC_RET_UNIT=""
  HIER_DST_RET_TIME=0; HIER_DST_RET_UNIT=""
  hier_expect_rc 0 "run 2 with a 1-minute retention window"
  hier_expect_new_snapshot "run 2"

  hier_expect_no_snapshots "$HIER_SRC_FS" "$first_suffix" "source"
  hier_expect_no_snapshots "$HIER_DST_FS" "$first_suffix" "destination"

  local newest_suffix
  newest_suffix="$(hier_snap_suffix "$HIER_SRC_FS")"
  hier_expect_tags "$HIER_SRC_FS" "$newest_suffix" "$HIER_TASK_PROP" "$HIER_TASK" "surviving source generation"
  hier_expect_tags "$HIER_DST_FS" "$newest_suffix" "$HIER_TASK_PROP" "$HIER_TASK" "surviving destination generation"

  HIER_SCHEDULE_JSON=""
}

HIER_MATRIX_MODES=(
  "push local"
  "push ssh"
  "push netcat"
  "push mbuffer"
  "pull ssh"
  "pull netcat"
  "pull mbuffer"
)

# ---------------------------------------------------------------------------
# Resume-continuation scenarios
#
# These cover the fix where a successful resume used to end the run outright,
# so the pending incremental never went out, retention never ran, and the UI
# reported a task that had in fact just run as "never run".
# ---------------------------------------------------------------------------

hier_expect_log() {
  local pattern="$1" label="$2"
  if grep -qF -- "$pattern" "$HIER_OUT" 2>/dev/null || grep -qF -- "$pattern" "$HIER_LOG" 2>/dev/null; then
    hier_pass "$label"
  else
    hier_fail "$label: '$pattern' missing from run output and debug log"
  fi
}

hier_expect_no_log() {
  local pattern="$1" label="$2"
  if grep -qF -- "$pattern" "$HIER_OUT" 2>/dev/null || grep -qF -- "$pattern" "$HIER_LOG" 2>/dev/null; then
    hier_fail "$label: '$pattern' should not appear but did"
  else
    hier_pass "$label"
  fi
}

hier_expect_rc_nonzero() {
  local what="$1"
  if [[ "$HIER_RC" -ne 0 ]]; then
    hier_pass "$what (exit $HIER_RC)"
  else
    hier_fail "$what: expected a non-zero exit, got 0"
  fi
}

hier_expect_no_new_snapshot() {
  local what="$1" now
  now="$(hier_newest_snap "$HIER_SRC_FS")"
  if [[ "$now" == "$HIER_SNAP_BEFORE" ]]; then
    hier_pass "$what created no new snapshot, as expected"
  else
    hier_fail "$what created ${now#*@} but should not have"
  fi
}

hier_dest_token() {
  ( zfs get -H -o value receive_resume_token "$HIER_DST_FS" 2>/dev/null || echo '-' ) | tr -d '\r'
}

# hier_expect_token <present|absent> <label>
hier_expect_token() {
  local want="$1" label="$2" token
  token="$(hier_dest_token)"
  if [[ "$want" == "present" ]]; then
    if [[ -n "$token" && "$token" != "-" ]]; then
      hier_pass "$label (token ${token:0:24}…)"
    else
      hier_fail "$label: no receive_resume_token on $HIER_DST_FS"
    fi
  else
    if [[ -z "$token" || "$token" == "-" ]]; then
      hier_pass "$label"
    else
      hier_fail "$label: token still present (${token:0:24}…)"
    fi
  fi
}

hier_expect_dest_snapshot() {
  local suffix="$1" label="$2"
  if zfs list -H -o name -t snapshot "$HIER_DST_FS@$suffix" >/dev/null 2>&1; then
    hier_pass "$label: destination holds @$suffix"
  else
    hier_fail "$label: destination is missing @$suffix"
    hier_dest_tree
  fi
}

hier_expect_lastrun() {
  local label="$1" age
  if [[ ! -f "$HIER_LASTRUN" ]]; then
    hier_fail "$label: $HIER_LASTRUN was never written"
    return 0
  fi
  age=$(( $(date +%s) - $(stat -c %Y "$HIER_LASTRUN") ))
  if [[ "$age" -le 600 ]]; then
    hier_pass "$label (stamp is ${age}s old)"
  else
    hier_fail "$label: stamp is stale (${age}s old)"
  fi
}

# Manufacture a genuine resume token by truncating an incremental stream mid-flight.
# Killing a live task instead would be timing-dependent; this is deterministic.
hier_make_resume_token() {
  local payload_mb="${1:-48}" cut_bytes="${2:-4194304}"
  local base mount

  base="$(hier_newest_snap "$HIER_SRC_FS")"
  if [[ -z "$base" ]]; then
    hier_fail "cannot manufacture a resume token: source has no snapshot to send from"
    return 0
  fi

  mount="$(zfs get -H -o value mountpoint "$HIER_SRC_FS")"
  dd if=/dev/urandom of="$mount/resume-payload.bin" bs=1M count="$payload_mb" status=none
  sync
  zfs snapshot "$HIER_SRC_FS@$HIER_RESUME_SNAP"

  hier_info "truncating an incremental ${base#*@} -> $HIER_RESUME_SNAP after ${cut_bytes} bytes"
  set +e
  zfs send -i "$base" "$HIER_SRC_FS@$HIER_RESUME_SNAP" 2>/dev/null \
    | head -c "$cut_bytes" \
    | zfs recv -s -F "$HIER_DST_FS" >/dev/null 2>&1
  set -e
}

cmd_scenario_resume_continues() {
  local previous_recursive="$HIER_RECURSIVE"
  HIER_RECURSIVE=false

  hier_say "resume-continues [$(hier_mode_label)]: a successful resume must fall through to the pending send"
  hier_setup
  rm -f "$HIER_LASTRUN"
  hier_run_task false false false quiet; hier_expect_rc 0 "initial full send"

  hier_make_resume_token
  hier_expect_token present "interrupted receive left a resume token"

  # New source data after the token, so there is genuinely more to send once the
  # resume finishes. Without the fix the run stops here and this never ships.
  hier_write_data post "$HIER_SRC_FS"

  hier_run_task false false
  hier_expect_rc 0 "resume + continue run"
  hier_expect_log 'Attempting to resume receive' "token was detected"
  hier_expect_log 'Resume completed; continuing with the rest of this replication run' "run continued instead of returning"
  hier_expect_token absent "resume token was consumed"
  hier_expect_dest_snapshot "$HIER_RESUME_SNAP" "resumed stream committed"
  hier_expect_new_snapshot "post-resume incremental"
  hier_expect_dest_snapshot "$(hier_snap_suffix "$HIER_SRC_FS")" "post-resume incremental landed"
  hier_expect_log '=== task completed successfully ===' "run reached the completion marker"
  hier_expect_lastrun "lastrun stamp written on the resume path"
  hier_expect_no_log 'zfs_replication_resume_token' "no pre-attempt Resume Token Found notification"
  hier_expect_no_log 'Resume Token Found' "no Resume Token Found subject line"

  hier_info "destination snapshots:"; hier_dest_tree
  HIER_RECURSIVE="$previous_recursive"
}

cmd_scenario_resume_only_stops() {
  local previous_recursive="$HIER_RECURSIVE"
  HIER_RECURSIVE=false

  hier_say "resume-only-stops [$(hier_mode_label)]: Resume Only must still end after the resume"
  hier_setup
  rm -f "$HIER_LASTRUN"
  hier_run_task false false false quiet; hier_expect_rc 0 "initial full send"

  hier_make_resume_token
  hier_expect_token present "interrupted receive left a resume token"
  hier_write_data post "$HIER_SRC_FS"

  HIER_RESUME_ONLY=true
  hier_run_task false false
  HIER_RESUME_ONLY=false

  hier_expect_rc 0 "resumeOnly run"
  hier_expect_log 'Resume transfer completed successfully' "resume finished"
  hier_expect_token absent "resume token was consumed"
  hier_expect_dest_snapshot "$HIER_RESUME_SNAP" "resumed stream committed"
  hier_expect_no_new_snapshot "resumeOnly"
  hier_expect_lastrun "lastrun stamp written on the resumeOnly path"

  HIER_RECURSIVE="$previous_recursive"
}

cmd_scenario_resume_all() {
  hier_reset_mode
  cmd_scenario_resume_continues
  cmd_scenario_resume_only_stops
  hier_teardown
  hier_say "resume scenarios finished with $HIER_FAILURES failure(s)"
  [[ "$HIER_FAILURES" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# SSH cipher scenarios
#
# Mirrors the option list in scheduler/src/models/SshCiphers.ts. Kept in bash so
# it also runs on an installed server, where only tests/ is deployed.
# ---------------------------------------------------------------------------

CIPHER_UI_OPTIONS=(
  "aes128-gcm@openssh.com"
  "aes256-gcm@openssh.com"
  "aes128-ctr"
  "aes256-ctr"
  "chacha20-poly1305@openssh.com"
)
CIPHER_RECOMMENDED="aes128-gcm@openssh.com"

cipher_local_list() {
  ( ssh -Q cipher 2>/dev/null || true ) | tr -d '\r'
}

# Reads the server's offer out of the pre-auth KEXINIT proposal, so it works even
# without key-based login. The client prints its own proposal first, hence the
# anchor; ssh -vv writes CRLF when stderr is a tty, hence the tr. awk must not
# exit early or the upstream stages die on SIGPIPE under `set -o pipefail`.
cipher_remote_list() {
  local user="$1" host="$2" port="${3:-22}" raw
  raw="$( ssh -vv -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
            -p "$port" "${user}@${host}" exit 2>&1 || true )"
  printf '%s\n' "$raw" | tr -d '\r' | awk '
        /peer server KEXINIT proposal/ { seen = 1; next }
        seen && !done && /ciphers stoc:/ {
          sub(/.*ciphers stoc:[[:space:]]*/, "");
          gsub(/,/, "\n");
          print;
          done = 1
        }'
}

cmd_scenario_cipher_availability() {
  local host="${1:-}" user="${2:-root}" port="${3:-22}"
  local locals remotes c

  hier_say "cipher availability: what this client supports and what the peer offers"
  locals="$(cipher_local_list)"
  if [[ -z "$locals" ]]; then
    hier_fail "ssh -Q cipher returned nothing; the UI cannot validate cipher choices here"
    return 0
  fi
  hier_info "client supports: $(echo "$locals" | tr '\n' ' ')"

  for c in "${CIPHER_UI_OPTIONS[@]}"; do
    if grep -qxF "$c" <<<"$locals"; then
      hier_pass "client supports $c"
    else
      hier_info "client does NOT support $c — the task form must flag it in red"
    fi
  done

  if grep -qxF "$CIPHER_RECOMMENDED" <<<"$locals"; then
    hier_pass "recommended default $CIPHER_RECOMMENDED is available"
  else
    hier_fail "recommended default $CIPHER_RECOMMENDED is missing from this client"
  fi

  [[ -n "$host" ]] || host="${HIER_HOST:-}"
  if [[ -z "$host" ]]; then
    hier_info "no host given; skipping the remote offer probe"
    return 0
  fi

  remotes="$(cipher_remote_list "$user" "$host" "$port")"
  if [[ -z "$remotes" ]]; then
    hier_fail "could not read the cipher offer from ${user}@${host}:${port}"
    return 0
  fi
  hier_info "${host} offers: $(echo "$remotes" | tr '\n' ' ')"
  for c in "${CIPHER_UI_OPTIONS[@]}"; do
    if grep -qxF "$c" <<<"$remotes"; then
      hier_pass "${host} offers $c"
    else
      hier_info "${host} does NOT offer $c — the task form must flag it in red"
    fi
  done
}

# An empty cipher is the UI's Automatic option: nothing must be injected at all.
cmd_scenario_cipher_send() {
  local cipher="$1"
  local previous="$HIER_SSH_CIPHER"
  local label="${cipher:-automatic (no override)}"

  hier_say "cipher send [$(hier_mode_label)]: $label must reach the ssh argv and complete a run"
  if [[ -n "$cipher" ]] && ! grep -qxF "$cipher" <<<"$(cipher_local_list)"; then
    hier_info "SKIP: this client does not support $cipher"
    return 0
  fi

  HIER_SSH_CIPHER="$cipher"
  hier_setup
  hier_run_task false false false quiet
  hier_expect_rc 0 "run with $label"
  hier_expect_new_snapshot "run with $label"
  if [[ -n "$cipher" ]]; then
    hier_expect_log "SSH cipher override: $cipher" "cipher override was picked up from the task env"
    hier_expect_log "Ciphers=$cipher" "cipher reached the ssh argv"
  else
    hier_expect_no_log "Ciphers=" "no cipher option is injected on Automatic"
  fi
  HIER_SSH_CIPHER="$previous"
}

# Every value the dropdown can produce, end to end, so a cipher cannot ship in
# the UI without a run proving the scripts accept it.
cmd_scenario_cipher_send_all() {
  local c
  cmd_scenario_cipher_send ""
  for c in "${CIPHER_UI_OPTIONS[@]}"; do
    cmd_scenario_cipher_send "$c"
  done
}

cmd_scenario_cipher_rejects_unknown() {
  local previous="$HIER_SSH_CIPHER"

  hier_say "cipher rejects-unknown [$(hier_mode_label)]: an unsupported cipher must fail before any data moves"
  HIER_SSH_CIPHER="not-a-real-cipher"
  hier_setup
  hier_run_task false false false quiet
  hier_expect_rc_nonzero "run with an unknown cipher"
  hier_expect_no_new_snapshot "run with an unknown cipher"
  hier_expect_log "SSH cipher override: not-a-real-cipher" "bad cipher was still logged for diagnosis"
  HIER_SSH_CIPHER="$previous"
}

# Indicative only: this runs over loopback SSH, so it isolates cipher cost rather
# than reproducing real link throughput. Wall clock covers the whole task (snapshot,
# ssh preflight, remote listings, retention), which on a small payload dwarfs the
# encryption itself, so the pipeline's own summary line is reported alongside it.
cmd_scenario_cipher_bench() {
  local -a ciphers=("$@")
  local -a results=()
  local previous_size="$HIER_IMG_SIZE" previous="$HIER_SSH_CIPHER"
  local payload_mb="${CIPHER_BENCH_MB:-256}"
  local c label start end mount pipe_rate rate_mib

  for c in "${ciphers[@]}"; do
    if [[ "$c" == *=* ]]; then
      hier_fail "'$c' looks like a variable assignment; run it as: CIPHER_BENCH_MB=2048 $0 scenario-cipher-bench ..."
      return 1
    fi
  done

  if [[ ${#ciphers[@]} -eq 0 ]]; then
    ciphers=("" "${CIPHER_UI_OPTIONS[@]}")
  fi

  hier_say "cipher bench [$(hier_mode_label)]: ${payload_mb} MiB full send per cipher"
  # Random data does not compress and ZFS reserves slop, so a flat margin is not enough.
  HIER_IMG_SIZE="$(( payload_mb * 3 / 2 + 512 ))M"

  for c in "${ciphers[@]}"; do
    label="${c:-automatic (OpenSSH default)}"
    if [[ -n "$c" ]] && ! grep -qxF "$c" <<<"$(cipher_local_list)"; then
      hier_info "skip $label: not supported by this client"
      continue
    fi

    HIER_SSH_CIPHER="$c"
    hier_setup
    mount="$(zfs get -H -o value mountpoint "$HIER_SRC_FS")"
    if ! dd if=/dev/urandom of="$mount/bench.bin" bs=1M count="$payload_mb" status=none; then
      hier_fail "could not write the ${payload_mb} MiB payload into $HIER_SRC_FS"
      break
    fi
    sync

    start="$(date +%s.%N)"
    hier_run_task false false false quiet
    end="$(date +%s.%N)"

    if [[ "$HIER_RC" -ne 0 ]]; then
      hier_fail "bench run failed for $label (exit $HIER_RC)"
      continue
    fi
    pipe_rate="$( grep -h 'average of' "$HIER_OUT" "$HIER_LOG" 2>/dev/null \
                    | tail -1 | sed -n 's/.*average of *\(.*\)$/\1/p' )"
    awk -v s="$start" -v e="$end" -v mb="$payload_mb" -v l="$label" -v p="${pipe_rate:-n/a}" \
      'BEGIN { d = e - s; printf "   %-34s %7.2fs task  %8.1f MB/s task  %12s stream\n", l, d, (d > 0 ? mb / d : 0), p }'
    rate_mib="$( awk -v p="$pipe_rate" 'BEGIN {
        n = p + 0
        if (p ~ /kiB/) n /= 1024
        else if (p ~ /GiB/) n *= 1024
        print (n > 0 ? n : 0)
      }' )"
    results+=("$(printf '%s\t%s' "$rate_mib" "$label")")
  done

  if [[ ${#results[@]} -gt 1 ]]; then
    hier_say "cipher bench summary (stream throughput, fastest first)"
    printf '%s\n' "${results[@]}" | sort -rn | awk -F'\t' '
      NR == 1 { best = $1 }
      { printf "   %-34s %8.1f MiB/s  %+6.1f%%\n", $2, $1, (best > 0 ? ($1 - best) / best * 100 : 0) }'
  fi

  HIER_SSH_CIPHER="$previous"
  HIER_IMG_SIZE="$previous_size"
  hier_teardown
}

cmd_scenario_cipher_all() {
  local reason
  hier_set_mode push ssh
  if reason="$(hier_mode_unavailable)"; then
    hier_say "SKIP cipher scenarios: $reason"
    hier_reset_mode
    return 0
  fi
  cmd_scenario_cipher_availability "$HIER_HOST" "$HIER_USER" "$HIER_SSH_PORT"
  cmd_scenario_cipher_send_all
  cmd_scenario_cipher_rejects_unknown
  hier_reset_mode
  hier_teardown
  hier_say "cipher scenarios finished with $HIER_FAILURES failure(s)"
  [[ "$HIER_FAILURES" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# Aggregate entry points
# ---------------------------------------------------------------------------

repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

cmd_unit_tests() {
  local base rc
  base="$(repo_root)"

  hier_say "unit tests (pytest)"
  # Source checkout keeps the scripts under system_files/; the installed appliance
  # layout puts scripts/ and tests/ side by side under the scheduler directory.
  if [[ ! -d "$base/system_files/opt/45drives/houston/scheduler/scripts/replication" \
     && ! -d "$base/scripts/replication" ]]; then
    hier_info "replication scripts not found next to tests/; skipping pytest"
    return 0
  fi
  if ! python3 -c 'import pytest' >/dev/null 2>&1; then
    hier_info "pytest is not installed; skipping (pip install pytest)"
    return 0
  fi

  set +e
  ( cd "$base" && python3 -m pytest tests -q )
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    hier_pass "pytest suite"
  else
    hier_fail "pytest suite (exit $rc)"
  fi
}

cmd_verify_fixes() {
  local reason
  hier_say "verify-fixes: unit tests, resume continuation, and SSH cipher plumbing"
  cmd_unit_tests

  hier_reset_mode
  cmd_scenario_resume_continues
  cmd_scenario_resume_only_stops

  hier_set_mode push ssh
  if reason="$(hier_mode_unavailable)"; then
    hier_say "SKIP cipher scenarios: $reason"
  else
    cmd_scenario_cipher_availability "$HIER_HOST" "$HIER_USER" "$HIER_SSH_PORT"
    cmd_scenario_cipher_send_all
    cmd_scenario_cipher_rejects_unknown
  fi

  hier_reset_mode
  hier_teardown
  hier_say "verify-fixes finished with $HIER_FAILURES failure(s)"
  [[ "$HIER_FAILURES" -eq 0 ]]
}

cmd_scenario_hierarchy_matrix() {
  local mode dir transport reason skipped=0
  for mode in "${HIER_MATRIX_MODES[@]}"; do
    read -r dir transport <<<"$mode"
    hier_set_mode "$dir" "$transport"
    if reason="$(hier_mode_unavailable)"; then
      hier_say "SKIP $(hier_mode_label): $reason"
      skipped=$((skipped + 1))
      continue
    fi
    cmd_scenario_hierarchy_clean
    cmd_scenario_hierarchy_child_behind
    cmd_scenario_hierarchy_tags
  done
  hier_reset_mode
  hier_teardown
  hier_say "hierarchy matrix finished with $HIER_FAILURES failure(s), $skipped mode(s) skipped"
  [[ "$HIER_FAILURES" -eq 0 ]]
}

cmd_scenario_hierarchy_all() {
  hier_reset_mode
  cmd_scenario_hierarchy_clean
  cmd_scenario_hierarchy_child_behind
  cmd_scenario_hierarchy_child_orphan
  cmd_scenario_hierarchy_child_no_snaps
  cmd_scenario_hierarchy_dest_ahead
  cmd_scenario_hierarchy_existing_data
  cmd_scenario_hierarchy_tags
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
    list-disks)
      cmd_list_disks
      ;;
    hier-notify-run)
      cmd_hier_notify_run "$@"
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
    verify-fixes)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      cmd_verify_fixes
      ;;
    unit-tests)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      cmd_unit_tests
      hier_say "unit tests finished with $HIER_FAILURES failure(s)"
      [[ "$HIER_FAILURES" -eq 0 ]]
      ;;
    scenario-resume-all)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      cmd_scenario_resume_all
      ;;
    scenario-resume-continues|scenario-resume-only-stops)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      hier_reset_mode
      # Pools are left standing for inspection; use scenario-hierarchy-teardown.
      "cmd_${cmd//-/_}"
      hier_say "finished with $HIER_FAILURES failure(s)"
      [[ "$HIER_FAILURES" -eq 0 ]]
      ;;
    scenario-cipher-all)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      cmd_scenario_cipher_all
      ;;
    scenario-cipher-availability)
      [[ $# -le 3 ]] || { usage; exit 1; }
      cmd_scenario_cipher_availability "$@"
      hier_say "finished with $HIER_FAILURES failure(s)"
      [[ "$HIER_FAILURES" -eq 0 ]]
      ;;
    scenario-cipher-send)
      [[ $# -eq 1 ]] || { usage; exit 1; }
      hier_require_root
      hier_set_mode push ssh
      local send_reason
      if send_reason="$(hier_mode_unavailable)"; then
        echo "cannot run $(hier_mode_label): $send_reason" >&2
        exit 1
      fi
      cmd_scenario_cipher_send "$1"
      hier_say "finished with $HIER_FAILURES failure(s)"
      [[ "$HIER_FAILURES" -eq 0 ]]
      ;;
    scenario-cipher-send-all)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      hier_set_mode push ssh
      local send_all_reason
      if send_all_reason="$(hier_mode_unavailable)"; then
        echo "cannot run $(hier_mode_label): $send_all_reason" >&2
        exit 1
      fi
      cmd_scenario_cipher_send_all
      hier_reset_mode
      hier_teardown
      hier_say "finished with $HIER_FAILURES failure(s)"
      [[ "$HIER_FAILURES" -eq 0 ]]
      ;;
    scenario-cipher-bench)
      hier_require_root
      hier_set_mode push ssh
      local bench_reason
      if bench_reason="$(hier_mode_unavailable)"; then
        echo "cannot run $(hier_mode_label): $bench_reason" >&2
        exit 1
      fi
      cmd_scenario_cipher_bench "$@"
      hier_say "finished with $HIER_FAILURES failure(s)"
      [[ "$HIER_FAILURES" -eq 0 ]]
      ;;
    scenario-hierarchy-matrix)
      [[ $# -eq 0 ]] || { usage; exit 1; }
      hier_require_root
      cmd_scenario_hierarchy_matrix
      ;;
    scenario-hierarchy-clean|scenario-hierarchy-child-behind|scenario-hierarchy-child-orphan|scenario-hierarchy-child-no-snaps|scenario-hierarchy-dest-ahead|scenario-hierarchy-existing-data|scenario-hierarchy-tags|scenario-hierarchy-retention)
      [[ $# -le 2 ]] || { usage; exit 1; }
      hier_require_root
      hier_set_mode "${1:-push}" "${2:-local}"
      local reason
      if reason="$(hier_mode_unavailable)"; then
        echo "cannot run $(hier_mode_label): $reason" >&2
        exit 1
      fi
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
