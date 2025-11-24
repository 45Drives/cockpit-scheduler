import { ref, onUnmounted, watch } from 'vue';

type AnyTask = any;

function taskId(t: AnyTask) {
    return t?.id ?? t?.uuid ?? t?.name;
}

export function useLiveTaskStatus(
    tasksRef: { value: AnyTask[] | undefined | null },
    scheduler: any,
    log: any,
    opts?: {
        intervalMs?: number;
        formatMs?: (ms: number) => string;
        completedWindowMs?: number; // how long to show "Completed" before reverting
    }
) {
    const statusMap = ref<Record<string, string>>({});
    const lastRunMap = ref<Record<string, string>>({});
    const lastCompletedAtMap = ref<Record<string, number>>({});
    const polling = ref(false);
    let intervalId: number | undefined;

    async function refreshOne(t: AnyTask) {
        const id = taskId(t);
        const completedWindowMs = opts?.completedWindowMs ?? 15_000; // 15s default

        const fmtMs = (ms: number) => {
            if (!ms) return "Task hasn't run yet.";
            if (opts?.formatMs) return opts.formatMs(ms);
            if (typeof scheduler?.formatLocal === 'function') return scheduler.formatLocal(ms);
            return new Date(ms).toLocaleString();
        };

        const buildLastRunLabel = (statusText: string, ms: number): string => {
            if (!ms) return "";
            const lower = statusText.toLowerCase();
            const ts = fmtMs(ms);

            if (lower.includes('failed')) return `Failed at ${ts}`;
            if (lower.includes('completed')) return `Completed at ${ts}`;
            if (lower.includes('inactive') || lower.includes('disabled')) return `${ts}`;
            return `${ts}`;
        };

        try {
            // ---- Primary path: one call that gives us status + timestamps
            const meta = await scheduler.getDisplayMeta(t);

            // derive a better default status based on schedule.enabled
            let schedulerStatusText: string | undefined = meta?.statusText;
            if (!schedulerStatusText) {
                const enabled = !!t?.schedule?.enabled;
                schedulerStatusText = enabled ? 'Active (pending)' : 'Inactive (Disabled)';
            }

            const lowerScheduler = schedulerStatusText.toLowerCase();

            // If currently running → show live and bail early
            if (
                lowerScheduler.includes('active (running)') ||
                lowerScheduler.includes('starting') ||
                lowerScheduler.includes('running')
            ) {
                statusMap.value[id] = schedulerStatusText;
                lastRunMap.value[id] = 'Running now...';
                return;
            }

            let label = '';
            let lastCompletedMs = 0;

            const lastRunMs = meta?.lastRunMs || 0;
            if (lastRunMs) {
                label = buildLastRunLabel(schedulerStatusText, lastRunMs);
            }

            // Prefer log so we can inspect exitCode
            if (log?.getLatestEntryFor) {
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
                            if (typeof latest?.exitCode === 'number') {
                                const tsLabel = fmtMs(ms);
                                if (latest.exitCode === 0) {
                                    lastCompletedMs = ms;
                                    lastCompletedAtMap.value[id] = ms;
                                    label = `Completed at ${tsLabel}`;
                                } else {
                                    label = `Failed at ${tsLabel}`;
                                }
                            } else {
                                label = buildLastRunLabel(schedulerStatusText, ms) || `${fmtMs(ms)}`;
                            }
                        }
                    }
                } catch {
                    // ignore log errors
                }
            }

            if (!label && lastRunMap.value[id] === 'Running now...') {
                label = `Stopped at ${fmtMs(Date.now())}`;
            }

            // Windowed "Completed" override
            let finalStatusText = schedulerStatusText;
            const now = Date.now();
            const latestCompleted = lastCompletedMs || lastCompletedAtMap.value[id] || 0;

            if (
                latestCompleted &&
                now - latestCompleted < completedWindowMs &&
                !lowerScheduler.includes('failed') &&
                !lowerScheduler.includes('inactive')
            ) {
                finalStatusText = 'Completed';
            }

            statusMap.value[id] = finalStatusText;
            lastRunMap.value[id] = label || lastRunMap.value[id] || "Task hasn't run yet.";
            return;
        } catch (e) {
            console.debug('[useLiveTaskStatus] getDisplayMeta failed; falling back:', e);
        }

        // ---- Fallback (old behavior) ----
        try {
            const enabled = !!t?.schedule?.enabled;
            let status: any;
            try {
                status = enabled ? await scheduler.getTimerStatus(t) : await scheduler.getServiceStatus(t);
            } catch { }
            if (!status) {
                try { status = await scheduler.getServiceStatus(t); } catch { }
            }
            if (!status) {
                try { status = await scheduler.getTimerStatus(t); } catch { }
            }

            // default based on enabled state if we still have nothing
            if (status == null || status === '') {
                statusMap.value[id] = enabled ? 'Active (pending)' : 'Inactive (Disabled)';
            } else {
                statusMap.value[id] = String(status);
            }
        } catch {
            const enabled = !!t?.schedule?.enabled;
            statusMap.value[id] = enabled ? 'Active (pending)' : 'Inactive (Disabled)';
        }

        try {
            // Same idea as above: if we somehow still have nothing, use enabled to choose
            let schedulerStatusText = statusMap.value[id];
            if (!schedulerStatusText) {
                const enabled = !!t?.schedule?.enabled;
                schedulerStatusText = enabled ? 'Active (pending)' : 'Inactive (Disabled)';
            }

            const lower = schedulerStatusText.toLowerCase();

            const latest = await (log?.getLatestEntryFor?.(t));
            const raw = latest?.finishDate ?? latest?.startDate;
            let lastCompletedMs = 0;

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
                        if (typeof latest?.exitCode === 'number') {
                            const tsLabel = fmtMs(ms);
                            if (latest.exitCode === 0) {
                                lastCompletedMs = ms;
                                lastCompletedAtMap.value[id] = ms;
                                return `Completed at ${tsLabel}`;
                            }
                            return `Failed at ${tsLabel}`;
                        }

                        if (lower.includes('failed')) return `Failed at ${fmtMs(ms)}`;
                        if (lower.includes('completed')) return `Completed at ${fmtMs(ms)}`;
                        if (lower.includes('inactive') || lower.includes('disabled')) return `${fmtMs(ms)}`;
                        return `${fmtMs(ms)}`;
                    })();

                    let finalStatusText = schedulerStatusText;
                    const now = Date.now();
                    const latestCompleted = lastCompletedMs || lastCompletedAtMap.value[id] || 0;

                    if (
                        latestCompleted &&
                        now - latestCompleted < completedWindowMs &&
                        !lower.includes('failed') &&
                        !lower.includes('inactive')
                    ) {
                        finalStatusText = 'Completed';
                    }

                    statusMap.value[id] = finalStatusText;
                    lastRunMap.value[id] = label;
                    return;
                }
            }

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

    function isCompleted(t: AnyTask): boolean {
        const s = statusFor(t);
        return !!s && s.toLowerCase().includes('completed');
    }

    function isRunningNow(t: AnyTask): boolean {
        const s = statusFor(t);
        if (!s) return false;
        const lower = s.toLowerCase();
        return (
            lower.includes('active (running)') ||
            lower.includes('starting') ||
            lower.includes('running')
        );
    }

    function isFailed(t: AnyTask): boolean {
        const s = statusFor(t);
        return !!s && s.toLowerCase().includes('failed');
    }

    function isInactive(t: AnyTask): boolean {
        const s = statusFor(t);
        if (!s) return false;
        const lower = s.toLowerCase();
        return lower.includes('inactive') || lower.includes('disabled');
    }

    onUnmounted(stop);
    watch(tasksRef, () => { if (polling.value) refreshAll(); }, { deep: true });

    return {
        start,
        stop,
        refreshAll,
        toggleSchedule,
        statusFor,
        lastRunFor,
        statusMap,
        lastRunMap,
        isCompleted,
        isRunningNow,
        isFailed,
        isInactive,
    };
}

export function taskStatusClass(status?: string) {
    if (status) {
        const s = status.toLowerCase();

        if (s.includes('failed')) return 'text-danger';
        if (s.includes('inactive') || s.includes('disabled')) return 'text-warning';
        if (s.includes('active') || s.includes('starting') || s.includes('completed')) return 'text-success';
        if (s.includes('no schedule found') || s.includes('not scheduled')) return 'text-muted';
    }
    return '';
}
