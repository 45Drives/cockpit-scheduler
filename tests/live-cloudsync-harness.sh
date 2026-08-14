#!/usr/bin/env bash
#
# Reproduce and verify the CloudSync progress-reporting bugs without needing a
# cloud remote, Cockpit, or customer data.
#
# It runs cloudsync-script.py exactly as systemd does — same environment
# variables, same NOTIFY_SOCKET protocol — and captures both the journal output
# and the sd_notify STATUS= timeline, then diffs the current working tree
# against a git baseline.
#
#   ./tests/live-cloudsync-harness.sh              # all scenarios
#   ./tests/live-cloudsync-harness.sh zero         # single scenario
#   BASELINE_REF=v1.6.13 ./tests/live-cloudsync-harness.sh
#
# Scenarios:
#   zero  - rclone reports "0 B / 0 B, -," forever (a sync stuck in its check
#           phase). Customer symptom: progress pinned at 0%, journal spam.
#   full  - rclone reports "450 MiB / 450 MiB, 100%" forever (transfer done,
#           process still finalizing). Customer symptom: pinned at 100%.
#   real  - real rclone against a generated, already-in-sync tree.
#
set -euo pipefail

SCENARIOS=("${@:-zero full real}")
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$REPO_ROOT/system_files/opt/45drives/houston/scheduler/scripts"
BASELINE_REF="${BASELINE_REF:-HEAD}"
WORK="${CLOUDSYNC_HARNESS_DIR:-${TMPDIR:-/tmp}/cloudsync-harness}"
STUB_SECONDS="${STUB_SECONDS:-12}"
STUB_INTERVAL="${STUB_INTERVAL:-1}"
REAL_FILE_COUNT="${REAL_FILE_COUNT:-20000}"

command -v rclone >/dev/null || { echo "rclone not installed"; exit 1; }
python3 -c "import requests" 2>/dev/null || { echo "python3 'requests' module required"; exit 1; }

rm -rf "$WORK"
mkdir -p "$WORK"/{stub,baseline,out}

# --- variant under test vs. baseline -----------------------------------------
cp "$SCRIPTS_DIR/notify.py" "$WORK/baseline/"
git -C "$REPO_ROOT" show \
    "$BASELINE_REF:system_files/opt/45drives/houston/scheduler/scripts/cloudsync-script.py" \
    > "$WORK/baseline/cloudsync-script.py"

# --- rclone.conf using the local backend, so no cloud credentials are needed --
cat > "$WORK/rclone.conf" <<'EOF'
[harnesslocal]
type = local
EOF

# --- sd_notify listener -------------------------------------------------------
cat > "$WORK/listener.py" <<'EOF'
import os, socket, sys, time
path, out = sys.argv[1], sys.argv[2]
if os.path.exists(path):
    os.unlink(path)
s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
s.bind(path)
start = time.monotonic()
with open(out, "w", buffering=1) as fh:
    while True:
        data = s.recv(4096).decode("utf-8", "replace").strip()
        for msg in data.splitlines():
            if msg.startswith("STATUS="):
                fh.write("%6.1fs  %s\n" % (time.monotonic() - start, msg[7:]))
EOF

# --- fake rclone that loops one stats line, mimicking a wedged transfer -------
make_stub() {
    cat > "$WORK/stub/rclone" <<EOF
#!/usr/bin/env bash
echo "2026/01/01 00:00:00 INFO  : Starting harness stub"
end=\$((SECONDS + $STUB_SECONDS))
while [ \$SECONDS -lt \$end ]; do
    echo "2026/01/01 00:00:00 INFO  : $1"
    sleep $STUB_INTERVAL
done
exit 0
EOF
    chmod +x "$WORK/stub/rclone"
}

build_real_tree() {
    [ -d "$WORK/src" ] && return
    mkdir -p "$WORK/src/resources_and_social" "$WORK/dst"
    python3 - "$WORK/src/resources_and_social" "$REAL_FILE_COUNT" <<'EOF'
import os, sys
d, n = sys.argv[1], int(sys.argv[2])
for i in range(n):
    with open(os.path.join(d, "file_%d.bin" % i), "wb") as f:
        f.write(os.urandom(64))
EOF
    rclone sync "$WORK/src" "$WORK/dst" -q   # prime it so the re-sync has no work
}

# run_case <scenario> <variant> <script-dir>
run_case() {
    local scenario="$1" variant="$2" script_dir="$3"
    local tag="$scenario-$variant"
    local sock="$WORK/notify-$tag.sock"
    local journal="$WORK/out/$tag.journal"
    local status="$WORK/out/$tag.status"
    local stats_interval="10s"
    local extra_path=""

    case "$scenario" in
        zero) make_stub "          0 B / 0 B, -, 0 B/s, ETA -"          ; extra_path="$WORK/stub:" ;;
        full) make_stub "  450.000 MiB / 450.000 MiB, 100%, 0 B/s, ETA -"; extra_path="$WORK/stub:" ;;
        real) build_real_tree; stats_interval="200ms" ;;
    esac

    python3 "$WORK/listener.py" "$sock" "$status" &
    local listener_pid=$!
    local waited=0
    while [ ! -S "$sock" ]; do
        if ! kill -0 "$listener_pid" 2>/dev/null; then
            echo "  ERROR: sd_notify listener died — are AF_UNIX sockets permitted here?" >&2
            return 1
        fi
        waited=$((waited + 1))
        [ "$waited" -gt 100 ] && { echo "  ERROR: notify socket never appeared" >&2; return 1; }
        sleep 0.05
    done

    set +e
    env -i \
        PATH="$extra_path/usr/local/bin:/usr/bin:/bin" \
        HOME="$WORK" \
        PYTHONPATH="$script_dir" \
        NOTIFY_SOCKET="$sock" \
        CLOUDSYNC_DEBUG_LOG="$WORK/out/$tag.debug" \
        CLOUDSYNC_STALL_TIMEOUT_SECONDS=0 \
        cloudSyncConfig_rclone_config_path="$WORK/rclone.conf" \
        cloudSyncConfig_rclone_remote="harnesslocal" \
        cloudSyncConfig_local_path="$WORK/src" \
        cloudSyncConfig_target_path="harnesslocal:$WORK/dst" \
        cloudSyncConfig_direction="push" \
        cloudSyncConfig_type="sync" \
        cloudSyncConfig_rcloneOptions_check_first_flag="True" \
        cloudSyncConfig_rcloneOptions_stats_interval="$stats_interval" \
        python3 "$script_dir/cloudsync-script.py" > "$journal" 2>&1
    set -e

    sleep 0.3
    kill "$listener_pid" 2>/dev/null || true
    wait "$listener_pid" 2>/dev/null || true

    local stats_lines
    stats_lines=$(grep -cE ', (-|[0-9.]+%),' "$journal" || true)
    printf '  %-9s journal stats lines: %-4s   status updates: %s\n' \
        "$variant" "$stats_lines" "$(wc -l < "$status")"
}

for scenario in ${SCENARIOS[*]}; do
    echo
    echo "=== scenario: $scenario ==========================================="
    run_case "$scenario" "baseline" "$WORK/baseline"
    run_case "$scenario" "fixed"    "$SCRIPTS_DIR"

    echo
    echo "  --- status timeline (baseline @ $BASELINE_REF) ---"
    sed 's/^/    /' "$WORK/out/$scenario-baseline.status" | head -12
    [ -s "$WORK/out/$scenario-baseline.status" ] || echo "    (no STATUS updates at all)"
    echo "  --- status timeline (working tree) ---"
    sed 's/^/    /' "$WORK/out/$scenario-fixed.status" | head -12
done

echo
echo "Artifacts in $WORK/out/  (*.journal = what journald would show)"
