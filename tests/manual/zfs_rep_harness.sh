#!/usr/bin/env bash
#
# Manual integration harness for the ZFS replication planner.
#
# Builds two throwaway file-backed pools, replicates a parent+child hierarchy
# between them, then deliberately desyncs the destination to prove that the
# planner picks a safe incremental base and only uses `zfs recv -F` when ZFS
# actually requires it.
#
# Requires root and the zfs userland. Touches ONLY the pools named below.
#
#   sudo tests/manual/zfs_rep_harness.sh all
#   sudo tests/manual/zfs_rep_harness.sh child-behind
#   sudo tests/manual/zfs_rep_harness.sh teardown
#
set -uo pipefail

SRC_POOL="hrepsrc"
DST_POOL="hrepdst"
SRC_FS="${SRC_POOL}/data"
DST_FS="${DST_POOL}/backup"
WORK_DIR="/var/tmp/hrep"
IMG_SIZE="512M"
TASK_NAME="hrepharness"
LOG="/tmp/zfs_rep_debug_${TASK_NAME}.log"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REP_SCRIPT="${REPO_ROOT}/system_files/opt/45drives/houston/scheduler/scripts/replication-script.py"

FAILURES=0

say()  { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
pass() { printf '   \033[1;32mPASS\033[0m %s\n' "$*"; }
fail() { printf '   \033[1;31mFAIL\033[0m %s\n' "$*"; FAILURES=$((FAILURES + 1)); }

require_root() {
    if [[ ${EUID} -ne 0 ]]; then
        echo "This harness must run as root (it creates and destroys zpools)." >&2
        exit 1
    fi
    command -v zfs >/dev/null || { echo "zfs not found in PATH" >&2; exit 1; }
    [[ -f ${REP_SCRIPT} ]] || { echo "Cannot find ${REP_SCRIPT}" >&2; exit 1; }
}

teardown() {
    zpool destroy -f "${SRC_POOL}" 2>/dev/null
    zpool destroy -f "${DST_POOL}" 2>/dev/null
    rm -rf "${WORK_DIR}"
    rm -f "${LOG}"
}

setup() {
    teardown
    mkdir -p "${WORK_DIR}"
    truncate -s "${IMG_SIZE}" "${WORK_DIR}/src.img"
    truncate -s "${IMG_SIZE}" "${WORK_DIR}/dst.img"
    zpool create -f -m "${WORK_DIR}/mnt-src" "${SRC_POOL}" "${WORK_DIR}/src.img" || exit 1
    zpool create -f -m "${WORK_DIR}/mnt-dst" "${DST_POOL}" "${WORK_DIR}/dst.img" || exit 1
    zfs create "${SRC_FS}"
    zfs create "${SRC_FS}/samba"
    zfs create "${SRC_FS}/media"
    write_source_data seed
}

write_source_data() {
    local tag="$1"
    dd if=/dev/urandom of="$(zfs get -H -o value mountpoint "${SRC_FS}")/${tag}.bin" bs=1M count=2 status=none
    dd if=/dev/urandom of="$(zfs get -H -o value mountpoint "${SRC_FS}/samba")/${tag}.bin" bs=1M count=2 status=none
    dd if=/dev/urandom of="$(zfs get -H -o value mountpoint "${SRC_FS}/media")/${tag}.bin" bs=1M count=2 status=none
    sync
}

# run_task <allowOverwrite> <useExistingDest> [forceFullSend]
run_task() {
    local allow_overwrite="$1" use_existing="$2" force_full="${3:-false}"
    rm -f "${LOG}"
    env \
        taskName="${TASK_NAME}" \
        ZFS_REP_DEBUG=1 \
        ZFS_REP_DEBUG_LOG="${LOG}" \
        zfsRepConfig_direction=push \
        zfsRepConfig_sourceDataset_pool="${SRC_POOL}" \
        zfsRepConfig_sourceDataset_dataset="${SRC_FS}" \
        zfsRepConfig_destDataset_pool="${DST_POOL}" \
        zfsRepConfig_destDataset_dataset="${DST_FS}" \
        zfsRepConfig_destDataset_host="" \
        zfsRepConfig_destDataset_user=root \
        zfsRepConfig_sendOptions_recursive_flag=true \
        zfsRepConfig_sendOptions_includeIntermediateSnapshots=true \
        zfsRepConfig_sendOptions_transferMethod=local \
        zfsRepConfig_sendOptions_allowOverwrite="${allow_overwrite}" \
        zfsRepConfig_sendOptions_useExistingDest="${use_existing}" \
        zfsRepConfig_sendOptions_forceFullSend="${force_full}" \
        python3 "${REP_SCRIPT}"
    return $?
}

last_recv_cmd() {
    grep 'PIPE recv cmd=' "${LOG}" 2>/dev/null | tail -1
}

expect_exit() {
    local actual="$1" expected="$2" what="$3"
    if [[ ${actual} -eq ${expected} ]]; then
        pass "${what} (exit ${actual})"
    else
        fail "${what}: expected exit ${expected}, got ${actual}"
    fi
}

expect_force_flag() {
    local want="$1" line
    line="$(last_recv_cmd)"
    if [[ -z ${line} ]]; then
        fail "no 'PIPE recv cmd=' line in ${LOG}"
        return
    fi
    if [[ ${want} == "yes" ]]; then
        if [[ ${line} == *" -F"* ]]; then pass "recv used -F: ${line##*cmd=}"
        else fail "recv should have used -F: ${line##*cmd=}"; fi
    else
        if [[ ${line} == *" -F"* ]]; then fail "recv used -F but should not have: ${line##*cmd=}"
        else pass "recv did not use -F: ${line##*cmd=}"; fi
    fi
}

expect_incremental_from() {
    local want="$1" line
    line="$(grep 'send_cmd:' "${LOG}" 2>/dev/null | tail -1)"
    if [[ ${line} == *"${want}"* ]]; then
        pass "incremental base is ${want}"
    else
        fail "expected base ${want} in: ${line}"
    fi
}

newest_snap() {   # newest_snap <dataset>
    zfs list -H -o name -t snapshot -s creation -d 1 "$1" 2>/dev/null | tail -1
}

dest_tree() {
    zfs list -H -o name -t snapshot -r "${DST_FS}" 2>/dev/null | sed 's/^/     /'
}

# ---------------------------------------------------------------- scenarios --

scenario_clean() {
    say "clean: healthy recursive incremental must NOT use -F"
    setup
    run_task false false; expect_exit $? 0 "initial full send"
    write_source_data second
    run_task false false; local rc=$?
    expect_exit ${rc} 0 "second run (incremental)"
    expect_force_flag no
    info "destination snapshots:"; dest_tree
}

scenario_child_behind() {
    say "child-behind: child missing the newest base must fall back to an older shared base"
    setup
    run_task false false >/dev/null; expect_exit $? 0 "run 1"
    write_source_data second
    run_task false false >/dev/null; expect_exit $? 0 "run 2"

    local victim
    victim="$(newest_snap "${DST_FS}/samba")"
    info "simulating a partial receive by destroying ${victim}"
    zfs destroy "${victim}"

    local shared="${SRC_FS}@$(newest_snap "${DST_FS}/samba" | cut -d@ -f2)"
    write_source_data third

    info "run 3 without Allow Overwrite (must refuse, change nothing):"
    run_task false false; expect_exit $? 2 "refuses rollback without Allow Overwrite"

    info "run 3 with Allow Overwrite (must resync from the older shared base):"
    run_task true false; expect_exit $? 0 "resyncs incrementally"
    expect_incremental_from "${shared}"
    expect_force_flag yes
    info "destination snapshots:"; dest_tree
}

scenario_child_orphan() {
    say "child-orphan: no shared base anywhere on a child must fail loudly, never full-send"
    setup
    run_task false false >/dev/null; expect_exit $? 0 "run 1"

    info "destroying every destination snapshot on the child and planting a foreign one"
    zfs destroy -r "${DST_FS}/samba@%" 2>/dev/null
    zfs snapshot "${DST_FS}/samba@foreign"
    local before; before="$(zfs list -H -o name -t snapshot -r "${DST_FS}" | wc -l)"

    write_source_data second
    run_task true false; expect_exit $? 2 "refuses even with Allow Overwrite enabled"

    local after; after="$(zfs list -H -o name -t snapshot -r "${DST_FS}" | wc -l)"
    if [[ ${before} -eq ${after} ]]; then
        pass "destination untouched (${after} snapshots)"
    else
        fail "destination snapshot count changed ${before} -> ${after}"
    fi
}

scenario_child_no_snaps() {
    say "child-no-snaps: destination child that exists with zero snapshots must be caught before send"
    setup
    run_task false false >/dev/null; expect_exit $? 0 "run 1"

    info "destroying every snapshot on ${DST_FS}/samba while leaving the dataset in place"
    zfs destroy "${DST_FS}/samba@%" 2>/dev/null
    local before; before="$(zfs list -H -o name -t snapshot -r "${DST_FS}" | wc -l)"

    write_source_data second
    run_task true false; expect_exit $? 2 "refuses instead of sending an unreceivable stream"

    local after; after="$(zfs list -H -o name -t snapshot -r "${DST_FS}" | wc -l)"
    if [[ ${before} -eq ${after} ]]; then
        pass "destination untouched (${after} snapshots)"
    else
        fail "destination snapshot count changed ${before} -> ${after}"
    fi
}

scenario_dest_ahead() {
    say "dest-ahead: destination-side snapshots require explicit Allow Overwrite"
    setup
    run_task false false >/dev/null; expect_exit $? 0 "run 1"
    zfs snapshot "${DST_FS}/samba@local-extra"
    write_source_data second

    run_task false false; expect_exit $? 2 "refuses to roll back without Allow Overwrite"
    if zfs list -t snapshot "${DST_FS}/samba@local-extra" >/dev/null 2>&1; then
        pass "destination-only snapshot survived the refusal"
    else
        fail "destination-only snapshot was destroyed without Allow Overwrite"
    fi

    run_task true false; expect_exit $? 0 "proceeds with Allow Overwrite"
    expect_force_flag yes
}

scenario_existing_data() {
    say "existing-data: an unexpected populated destination must not be wiped"
    teardown
    mkdir -p "${WORK_DIR}"
    truncate -s "${IMG_SIZE}" "${WORK_DIR}/src.img"
    truncate -s "${IMG_SIZE}" "${WORK_DIR}/dst.img"
    zpool create -f -m "${WORK_DIR}/mnt-src" "${SRC_POOL}" "${WORK_DIR}/src.img"
    zpool create -f -m "${WORK_DIR}/mnt-dst" "${DST_POOL}" "${WORK_DIR}/dst.img"
    zfs create "${SRC_FS}"; zfs create "${SRC_FS}/samba"
    write_source_data seed

    zfs create "${DST_FS}"
    local dst_mount; dst_mount="$(zfs get -H -o value mountpoint "${DST_FS}")"
    echo "irreplaceable customer data" > "${dst_mount}/precious.txt"
    sync

    info "Allow Overwrite ON, Use Existing Destination OFF -> must refuse to force"
    run_task true false; local rc=$?
    if [[ ${rc} -ne 0 ]]; then
        pass "run failed safely instead of forcing (exit ${rc})"
    else
        fail "run succeeded; check whether it overwrote the destination"
    fi
    expect_force_flag no
    if [[ -f ${dst_mount}/precious.txt ]]; then
        pass "unsnapshotted destination data survived"
    else
        fail "unsnapshotted destination data was destroyed"
    fi

    info "Use Existing Destination ON + Allow Overwrite ON -> destructive BY DESIGN"
    run_task true true; expect_exit $? 0 "explicit overwrite accepted"
    expect_force_flag yes
}

# -------------------------------------------------------------------- main --

require_root
case "${1:-all}" in
    setup)          setup ;;
    teardown)       teardown ;;
    clean)          scenario_clean ;;
    child-behind)   scenario_child_behind ;;
    child-orphan)   scenario_child_orphan ;;
    child-no-snaps) scenario_child_no_snaps ;;
    dest-ahead)     scenario_dest_ahead ;;
    existing-data)  scenario_existing_data ;;
    all)
        scenario_clean
        scenario_child_behind
        scenario_child_orphan
        scenario_child_no_snaps
        scenario_dest_ahead
        scenario_existing_data
        teardown
        ;;
    *)
        echo "usage: $0 {all|clean|child-behind|child-orphan|child-no-snaps|dest-ahead|existing-data|setup|teardown}" >&2
        exit 1
        ;;
esac

say "harness finished with ${FAILURES} failure(s)"
exit $(( FAILURES > 0 ? 1 : 0 ))
