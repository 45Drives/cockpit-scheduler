// useLiveTaskStatus.ts
import { ref, onUnmounted, watch } from 'vue';

type AnyTask = any;

function taskId(t: AnyTask) {
    return t?.id ?? t?.uuid ?? t?.name;
}

function formatDateLike(v: any) {
    if (!v) return '—';
    const d = new Date(v);
    if (Number.isFinite(v) && typeof v === 'number' && v.toString().length === 10) {
        const d2 = new Date(v * 1000);
        return isNaN(d2.getTime()) ? String(v) : d2.toLocaleString();
    }
    return isNaN(d.getTime()) ? String(v) : d.toLocaleString();
}

// helper that ignores empty strings
function pickNonEmpty<T>(...vals: T[]) {
    for (const v of vals) {
        if (v !== undefined && v !== null && String(v).trim() !== '') return v;
    }
    return undefined;
}

export function useLiveTaskStatus(
    tasksRef: { value: AnyTask[] | undefined | null },
    scheduler: any,
    log: any,
    opts?: { intervalMs?: number }
) {
    const statusMap = ref<Record<string, string>>({});
    const lastRunMap = ref<Record<string, string>>({});
    const polling = ref(false);
    let intervalId: number | undefined;

    async function refreshOne(t: AnyTask) {
        const id = taskId(t);

        // --- STATUS (robust) ---
        try {
            const enabled = !!t?.schedule?.enabled;
            let status: any;

            // try the expected unit first
            try {
                status = enabled ? await scheduler.getTimerStatus(t)
                    : await scheduler.getServiceStatus(t);
            } catch {
                // fallbacks: try both in case the first one failed
                try { status = await scheduler.getServiceStatus(t); } catch { }
                if (!status) {
                    try { status = await scheduler.getTimerStatus(t); } catch { }
                }
            }

            statusMap.value[id] = String(status ?? 'Inactive (Disabled)');
        } catch {
            statusMap.value[id] = 'Inactive (Disabled)';
        }

        // --- LAST RUN (don’t show — when never run) ---
        try {
            const latest = await log.getLatestEntryFor(t);
            const ts = [latest?.startDate, latest?.finishDate].find(s => s && String(s).trim() !== '');
            lastRunMap.value[id] = ts ? formatDateLike(ts) : "Task hasn't run yet.";
            
            if (latest) {
                const ts = pickNonEmpty(latest.startDate, latest.finishDate);
                lastRunMap.value[id] = ts ? formatDateLike(ts) : "Task hasn't run yet.";
            } else {
                lastRunMap.value[id] = "Task hasn't run yet.";
            }
        } catch {
            lastRunMap.value[id] = "Task hasn't run yet.";
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
