// useLiveTaskStatus.ts
import { ref, onUnmounted, watch } from 'vue';

type AnyTask = any;

function taskId(t: AnyTask) {
    return t?.id ?? t?.uuid ?? t?.name;
}

export function useLiveTaskStatus(
    tasksRef: { value: AnyTask[] | undefined | null },
    scheduler: any,
    log: any,
    opts?: { intervalMs?: number; formatMs?: (ms: number) => string }
) {
    const statusMap = ref<Record<string, string>>({});
    const lastRunMap = ref<Record<string, string>>({});
    const polling = ref(false);
    let intervalId: number | undefined;

    async function refreshOne(t: AnyTask) {
        const id = taskId(t);

        // prefer a formatter the caller passed in → else scheduler.formatLocal → else toLocaleString
        const fmtMs = (ms: number) => {
            if (!ms) return "Task hasn't run yet.";
            if (opts?.formatMs) return opts.formatMs(ms);
            if (typeof scheduler?.formatLocal === 'function') return scheduler.formatLocal(ms);
            return new Date(ms).toLocaleString();
        };

        // helper to turn (statusText, ms) into a nice "Last Run" string
        const buildLastRunLabel = (statusText: string, ms: number): string => {
            if (!ms) return "";
            const lower = statusText.toLowerCase();
            const ts = fmtMs(ms);

            if (lower.includes('failed')) return `Failed at ${ts}`;
            if (lower.includes('completed')) return `Completed at ${ts}`;
            if (lower.includes('inactive') || lower.includes('disabled')) return `Last Run at ${ts}`;
            return `Last Run at ${ts}`;
        };

        try {
            // ---- Primary path: one call that gives us status + timestamps
            const meta = await scheduler.getDisplayMeta(t);
            const statusText = meta?.statusText ?? 'Inactive (Disabled)';
            statusMap.value[id] = statusText;
            const lower = statusText.toLowerCase();

            // If currently running → show live
            if (
                lower.includes('active (running)') ||
                lower.includes('starting') ||
                lower.includes('running')
            ) {
                lastRunMap.value[id] = 'Running now...';
                return;
            }

            // Not running anymore → try to get a timestamp from systemd first
            let label = buildLastRunLabel(statusText, meta?.lastRunMs || 0);

            // If systemd didn't give us a timestamp, try the task log
            if (!label && log?.getLatestEntryFor) {
                try {
                    const latest = await log.getLatestEntryFor(t);
                    const raw = latest?.finishDate ?? latest?.startDate;
                    if (raw) {
                        let ms = 0;
                        if (typeof raw === 'number') {
                            ms = raw.toString().length === 10 ? raw * 1000 : raw;
                        } else {
                            const parsed = Date.parse(String(raw));
                            if (Number.isFinite(parsed)) ms = parsed;
                        }
                        if (ms) {
                            label = buildLastRunLabel(statusText, ms) || `Last Run at ${fmtMs(ms)}`;
                        }
                    }
                } catch {
                    // ignore log errors
                }
            }

            // If we still have nothing, but we *were* showing "Running now...", treat this as stopped just now
            if (!label && lastRunMap.value[id] === 'Running now...') {
                label = `Stopped at ${fmtMs(Date.now())}`;
            }

            // Final fallback
            lastRunMap.value[id] = label || lastRunMap.value[id] || "Task hasn't run yet.";
            return;
        } catch (e) {
            // continue to fallback below
            console.debug('[useLiveTaskStatus] getDisplayMeta failed; falling back:', e);
        }

        // ---- Fallback (old behavior) ----
        try {
            const enabled = !!t?.schedule?.enabled;
            let status: any;
            try { status = enabled ? await scheduler.getTimerStatus(t) : await scheduler.getServiceStatus(t); } catch { }
            if (!status) { try { status = await scheduler.getServiceStatus(t); } catch { } }
            if (!status) { try { status = await scheduler.getTimerStatus(t); } catch { } }
            statusMap.value[id] = String(status ?? 'Inactive (Disabled)');
        } catch {
            statusMap.value[id] = 'Inactive (Disabled)';
        }

        try {
            const statusText = statusMap.value[id] || 'Inactive (Disabled)';
            const lower = statusText.toLowerCase();

            const latest = await (log?.getLatestEntryFor?.(t));
            const raw = latest?.finishDate ?? latest?.startDate;
            if (raw) {
                let ms = 0;
                if (typeof raw === 'number') {
                    ms = raw.toString().length === 10 ? raw * 1000 : raw;
                } else {
                    const parsed = Date.parse(String(raw));
                    if (Number.isFinite(parsed)) ms = parsed;
                }

                if (ms) {
                    const label = (() => {
                        if (lower.includes('failed')) return `Failed at ${fmtMs(ms)}`;
                        if (lower.includes('completed')) return `Completed at ${fmtMs(ms)}`;
                        if (lower.includes('inactive') || lower.includes('disabled')) return `Last Run at ${fmtMs(ms)}`;
                        return `Last Run at ${fmtMs(ms)}`;
                    })();
                    lastRunMap.value[id] = label;
                    return;
                }
            }

            // If we got here, no timestamp from log
            if (lastRunMap.value[id] === 'Running now...') {
                lastRunMap.value[id] = `Stopped at ${fmtMs(Date.now())}`;
            } else {
                lastRunMap.value[id] = lastRunMap.value[id] ?? "Task hasn't run yet.";
            }
        } catch {
            if (lastRunMap.value[id] === 'Running now...') {
                lastRunMap.value[id] = `Stopped at ${fmtMs(Date.now())}`;
            } else {
                lastRunMap.value[id] = lastRunMap.value[id] ?? "Task hasn't run yet.";
            }
        }
    }

    async function refreshAll() {
        const tasks = tasksRef.value ?? [];
        await Promise.all(tasks.map(refreshOne));
    }

    function start() {
        if (polling.value) return;
        polling.value = true;
        refreshAll();
        intervalId = window.setInterval(refreshAll, opts?.intervalMs ?? 1500);
    }

    function stop() {
        polling.value = false;
        if (intervalId) {
            clearInterval(intervalId);
            intervalId = undefined;
        }
    }

    async function toggleSchedule(t: AnyTask) {
        const enabled = !!t?.schedule?.enabled;
        if (enabled) {
            await scheduler.disableSchedule(t);
            t.schedule.enabled = false;
        } else {
            await scheduler.enableSchedule(t);
            t.schedule.enabled = true;
        }
        await refreshOne(t);
    }

    function statusFor(t: AnyTask) { return statusMap.value[taskId(t)]; }
    function lastRunFor(t: AnyTask) { return lastRunMap.value[taskId(t)]; }

    onUnmounted(stop);
    watch(tasksRef, () => { if (polling.value) refreshAll(); }, { deep: true });

    return { start, stop, refreshAll, toggleSchedule, statusFor, lastRunFor, statusMap, lastRunMap };
}

export function taskStatusClass(status?: string) {
    if (status) {
        const s = status.toLowerCase();
        if (s.includes('active') || s.includes('starting') || s.includes('completed')) return 'text-success';
        if (s.includes('inactive') || s.includes('disabled')) return 'text-warning';
        if (s.includes('failed')) return 'text-danger';
        if (s.includes('no schedule found') || s.includes('not scheduled')) return 'text-muted';
    }
    return '';
}
