<template>
    <div class="h-full flex flex-col bg-well text-default p-3 gap-3">
        <!-- Toolbar: selection actions + new/refresh (matches BackUpListView) -->
        <div class="flex flex-wrap items-center gap-2 min-h-8">
            <!-- Action buttons (visible when a task is selected) -->
            <div class="flex flex-wrap items-center gap-2"
                :class="selectedTask ? '' : 'invisible pointer-events-none'">
                <span class="text-sm text-muted mr-1">1 selected</span>

                <button class="btn btn-primary text-sm h-8 px-3 shrink-0 whitespace-nowrap inline-flex items-center justify-center gap-2 leading-none"
                    :disabled="!selectedTask || selectedRowRunning"
                    @click="selectedTask && confirmRunNow(selectedTask)">
                    <PlayIcon class="w-4 h-4" />
                    Run Now
                </button>

                <button v-if="selectedRowRunning"
                    class="btn btn-danger text-sm h-8 px-3 shrink-0 whitespace-nowrap inline-flex items-center justify-center gap-2 leading-none"
                    @click="selectedTask && confirmStopNow(selectedTask)">
                    <StopIcon class="w-4 h-4" />
                    Stop
                </button>

                <button class="btn btn-secondary text-sm h-8 px-3 shrink-0 whitespace-nowrap inline-flex items-center justify-center gap-2 leading-none"
                    :disabled="!selectedTask" @click="selectedTask && viewLogs(selectedTask)">
                    <DocumentTextIcon class="w-4 h-4" />
                    Logs
                </button>

                <button class="btn btn-secondary text-sm h-8 px-3 shrink-0 whitespace-nowrap inline-flex items-center justify-center gap-2 leading-none"
                    :disabled="!selectedTask" @click="selectedTask && edit(selectedTask)">
                    <PencilSquareIcon class="w-4 h-4" />
                    Edit
                </button>

                <button class="btn btn-danger text-sm h-8 px-3 shrink-0 whitespace-nowrap inline-flex items-center justify-center gap-2 leading-none"
                    :disabled="!selectedTask" @click="selectedTask && confirmRemove(selectedTask)">
                    <TrashIcon class="w-4 h-4" />
                    Delete
                </button>
            </div>

            <div class="flex-1" />

            <button class="btn btn-primary text-sm h-8 px-3 shrink-0 whitespace-nowrap inline-flex items-center justify-center gap-2 leading-none" @click="openAdd" :disabled="loading">
                <PlusIcon class="w-4 h-4" />
                New Backup
            </button>

            <button class="btn btn-secondary text-sm h-8 px-3 shrink-0 whitespace-nowrap inline-flex items-center justify-center gap-2 leading-none" @click="refresh" :disabled="loading">
                <ArrowPathIcon class="w-4 h-4" />
                Refresh
            </button>
        </div>

        <!-- Content area fills remaining height -->
        <div class="flex-1 min-h-0 relative">
            <!-- initial load -->
            <div v-if="showInitialSpinner" class="absolute inset-0 flex items-center justify-center">
                <CustomLoadingSpinner :width="'w-24'" :height="'h-24'" :baseColor="'text-gray-200'"
                    :fillColor="'fill-gray-500'" />
            </div>

            <!-- empty state -->
            <div v-else-if="displayRows.length === 0" class="h-full flex flex-col items-center justify-center text-center py-12 gap-3">
                <CircleStackIcon class="w-12 h-12 text-muted opacity-30" />
                <span class="text-muted text-lg">No remote backup tasks found</span>
                <p class="text-sm text-muted">Click <b>New Backup</b> above to create one.</p>
            </div>

            <!-- table -->
            <div v-else class="h-full overflow-hidden">
                <!-- busy overlay while keeping table visible -->
                <div v-if="showOverlaySpinner"
                    class="absolute inset-0 z-[100] flex items-center justify-center bg-well/60 backdrop-blur-sm">
                    <CustomLoadingSpinner :width="'w-16'" :height="'h-16'" :baseColor="'text-gray-200'"
                        :fillColor="'fill-gray-500'" />
                </div>

                <div class="h-full overflow-auto">
                    <table class="min-w-full text-sm text-left table-fixed border border-default rounded-md" style="table-layout: fixed;">
                        <thead class="sticky top-0 bg-secondary z-10">
                            <tr class="border-b border-default">
                                <th class="px-3 py-2" style="width: 42px;">
                                    <span class="sr-only">Select</span>
                                </th>
                                <th class="px-3 py-2" style="width: 180px;">Name</th>
                                <th class="px-3 py-2" style="width: 120px;">Type</th>
                                <th class="px-3 py-2" style="width: 360px;">Details</th>
                                <th class="px-3 py-2" style="width: 150px;">Schedule</th>
                                <th class="px-3 py-2" style="width: 140px;">Status</th>
                                <th class="px-3 py-2" style="width: 190px;">Last Run</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template v-for="row in displayRows" :key="row.id">
                                <tr class="border-b border-default text-left cursor-pointer select-none transition-colors row-hover"
                                    :class="isSelected(row.raw) ? 'row-selected' : 'bg-default'"
                                    @click="toggleSelection(row.raw)">
                                    <td class="px-3 py-2">
                                        <input
                                            type="radio"
                                            name="remote-backup-selection"
                                            class="input-radio pointer-events-none"
                                            :checked="isSelected(row.raw)"
                                            :aria-label="`Select ${row.name}`"
                                        />
                                    </td>
                                    <td class="px-3 py-2 truncate" :title="row.name">{{ row.name }}</td>
                                    <td class="px-3 py-2 truncate">
                                        <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-default/10"
                                            :title="row.type">
                                            {{ row.type }}
                                        </span>
                                    </td>
                                    <td class="px-3 py-2">
                                        <div class="space-y-1 min-w-0">
                                            <div class="truncate" :title="row.details.source">
                                                <span class="text-muted mr-2">Source</span>{{ row.details.source }}
                                            </div>
                                            <div class="truncate" :title="row.details.destination">
                                                <span class="text-muted mr-2">Destination</span>{{ row.details.destination }}
                                            </div>
                                        </div>
                                    </td>
                                    <td class="px-3 py-2 truncate" :title="row.schedule">{{ row.schedule }}</td>
                                    <td class="px-3 py-2">
                                        <span class="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full"
                                            :class="taskStatusBadgeClass(row.status)">
                                            <span class="w-1.5 h-1.5 rounded-full" :class="statusDotClass(row.status)" />
                                            {{ row.status || '—' }}
                                        </span>
                                    </td>
                                    <td class="px-3 py-2 truncate" :title="row.lastRun">{{ row.lastRun }}</td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div v-if="runningRows.length > 0"
            class="bg-accent rounded-lg border border-default shrink-0 flex flex-col">
            <div class="px-3 pt-3 pb-1.5 text-xs font-semibold text-muted uppercase tracking-wide">
                {{ runningRows.length }} backup{{ runningRows.length > 1 ? 's' : '' }} in progress
            </div>
            <div class="overflow-y-auto max-h-[220px] px-3 pb-3 space-y-2">
                <div v-for="row in runningRows" :key="`progress-${row.id}`"
                    class="flex items-center gap-3 py-1.5">
                    <span class="text-sm font-medium text-default truncate min-w-[120px] max-w-[240px]"
                        :title="row.name">{{ row.name }}</span>
                    <div class="flex-1 h-2.5 bg-default rounded-full overflow-hidden">
                        <div v-if="row.progress != null"
                            class="h-full bg-primary rounded-full transition-all duration-300"
                            :style="{ width: Math.min(row.progress, 100) + '%' }" />
                        <div v-else
                            class="h-full bg-primary rounded-full animate-pulse w-full" />
                    </div>
                    <span class="text-sm text-muted whitespace-nowrap min-w-[80px] text-right">
                        {{ row.progress != null ? Math.round(row.progress) + '%' : 'Running…' }}
                    </span>
                </div>
            </div>
        </div>
    </div>

    <!-- Log View Modal -->
    <div v-if="showLogView">
        <component :is="logViewComponent" @close="closeLogView" :id-key="'simple-log-view'" :task="selectedLogTask!" />
    </div>

    <!-- Confirmation Dialogs -->
    <div v-if="showRunNowPrompt">
        <component :is="confirmDialogComponent" @close="(v: boolean) => showRunNowPrompt = v" :showFlag="showRunNowPrompt"
            title="Run Task" message="Do you wish to run this task now?" :confirmYes="runNowYes"
            :confirmNo="() => showRunNowPrompt = false" :operating="operating" operation="starting" />
    </div>
    <div v-if="showStopNowPrompt">
        <component :is="confirmDialogComponent" @close="(v: boolean) => showStopNowPrompt = v" :showFlag="showStopNowPrompt"
            title="Stop Task" message="Do you wish to stop this task now?" :confirmYes="stopNowYes"
            :confirmNo="() => showStopNowPrompt = false" :operating="operating" operation="stopping" />
    </div>
    <div v-if="showRemovePrompt">
        <component :is="confirmDialogComponent" @close="(v: boolean) => showRemovePrompt = v" :showFlag="showRemovePrompt"
            title="Remove Task" message="Are you sure you want to remove this task? This cannot be undone."
            :confirmYes="removeYes" :confirmNo="() => showRemovePrompt = false" :operating="operating"
            operation="removing" />
    </div>
</template>

<script setup lang="ts">
import { computed, ref, onActivated, onUnmounted, onMounted, watch, provide } from 'vue';
import { ArrowPathIcon, PlusIcon, PlayIcon, StopIcon, DocumentTextIcon, PencilSquareIcon, TrashIcon, CircleStackIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../components/common/CustomLoadingSpinner.vue';
import { injectWithCheck } from '../composables/utility';
import { loadingInjectionKey, schedulerInjectionKey, taskInstancesInjectionKey, logInjectionKey } from '../keys/injection-keys';
import { Notification, pushNotification, confirm } from '@45drives/houston-common-ui';
import { useRouter } from 'vue-router';
import { useTaskDraftStore } from '../stores/taskDraft';
import { useLiveTaskStatus, taskStatusClass, taskStatusBadgeClass } from '../composables/useLiveTaskStatus';

const router = useRouter();
const loading = injectWithCheck(loadingInjectionKey, 'loading not provided!');
const myScheduler = injectWithCheck(schedulerInjectionKey, 'scheduler not provided!');
const taskInstances = injectWithCheck(taskInstancesInjectionKey, 'taskInstances not provided!');
const draftStore = useTaskDraftStore();

const search = ref('');
const selected = ref<any>(null);
const myTaskLog = injectWithCheck(logInjectionKey, 'log not provided!');

/* ── Single-select (matches local BackUpListView pattern) ── */
const selectedTask = ref<any>(null);

function toggleSelection(t: any) {
    const id = t?.id ?? t?.uuid ?? t?.name;
    const curId = selectedTask.value?.id ?? selectedTask.value?.uuid ?? selectedTask.value?.name;
    selectedTask.value = id === curId ? null : t;
}

function isSelected(t: any) {
    if (!selectedTask.value) return false;
    const id = t?.id ?? t?.uuid ?? t?.name;
    const curId = selectedTask.value?.id ?? selectedTask.value?.uuid ?? selectedTask.value?.name;
    return id === curId;
}

const selectedRowRunning = computed(() => {
    if (!selectedTask.value) return false;
    return live.isRunningNow(selectedTask.value);
});

function statusDotClass(status: string) {
    const s = (status ?? '').toLowerCase();
    if (s.includes('running') || s.includes('in progress')) return 'bg-blue-500';
    if (s.includes('fail') || s.includes('error')) return 'bg-red-500';
    if (s.includes('success') || s.includes('complete') || s.includes('active')) return 'bg-green-500';
    return 'bg-gray-400';
}

/* ── View Logs modal ──────────────────────────────────── */
const showLogView = ref(false);
const selectedLogTask = ref<any>(null);
const logViewComponent = ref();
provide('show-log-view', showLogView);

async function viewLogs(t: any) {
    selectedLogTask.value = t;
    if (!logViewComponent.value) {
        const mod = await import('../components/modals/LogView.vue');
        logViewComponent.value = mod.default;
    }
    showLogView.value = true;
}
function closeLogView() {
    showLogView.value = false;
}

const fetching = ref(false);
const everLoaded = ref(false);
const cachedRows = ref<any[]>([]);

const isBusy = computed(() => fetching.value || loading.value);
const showInitialSpinner = computed(() => !everLoaded.value && isBusy.value);
const showOverlaySpinner = computed(() => everLoaded.value && isBusy.value);

const boot = async () => {
    if (fetching.value) return;       // guard against double calls
    fetching.value = true;
    try {
        await myScheduler.loadTaskInstances();
        await live.refreshAll();
        live.start();
    } finally {
        fetching.value = false;
    }
};

onMounted(boot);
onActivated(boot);
onUnmounted(() => live.stop());

// Only remote backups (Rsync Task + Cloud Sync Task)
const remoteTasks = computed(() =>
    (taskInstances.value ?? []).filter(
        (t: any) => t?.template?.name === 'Rsync Task' || t?.template?.name === 'Cloud Sync Task'
    )
);
const live = useLiveTaskStatus(remoteTasks, myScheduler, myTaskLog, { intervalMs: 1500 });

// Simple name filter
const filtered = computed(() => {
    const list = remoteTasks.value;
    const q = search.value.trim().toLowerCase();
    if (!q) return list;
    return list.filter((t: any) => (t?.name ?? '').toLowerCase().includes(q));
});

/**
 * Helpers to read parameters safely
 */
function paramsOf(t: any) {
    return t?.parameters?.children ?? [];
}
function isRsync(t: any) {
    return t?.template?.name === 'Rsync Task';
}
function isCloud(t: any) {
    return t?.template?.name === 'Cloud Sync Task';
}

function getSource(t: any) {
    const p = paramsOf(t).find((x: any) => x.key === 'local_path');
    return p?.value ?? '—';
}
function getTargetPath(t: any) {
    if (isRsync(t)) {
        const ti = paramsOf(t).find((x: any) => x.key === 'target_info');
        return ti?.children?.find((c: any) => c.key === 'path')?.value ?? '—';
    } else {
        const tp = paramsOf(t).find((x: any) => x.key === 'target_path');
        return tp?.value ?? '—';
    }
}
function getHost(t: any) {
    const ti = paramsOf(t).find((x: any) => x.key === 'target_info');
    return ti?.children?.find((c: any) => c.key === 'host')?.value ?? '—';
}
function getUser(t: any) {
    const ti = paramsOf(t).find((x: any) => x.key === 'target_info');
    return ti?.children?.find((c: any) => c.key === 'user')?.value ?? 'root';
}
function getPort(t: any) {
    const ti = paramsOf(t).find((x: any) => x.key === 'target_info');
    return ti?.children?.find((c: any) => c.key === 'port')?.value ?? 22;
}
function getRemoteName(t: any) {
    const r = paramsOf(t).find((x: any) => x.key === 'rclone_remote');
    return r?.value ?? '—';
}

function getSchedule(t: any) {
    const ivals = t?.schedule?.intervals ?? [];
    if (!ivals.length) return '—';
    return ivals.map((i: any) => myScheduler.describeInterval(i)).join(' + ');
}


/**
 * UI field builders
 */
function typeLabel(t: any) {
    if (isRsync(t)) return 'Server-to-Server';
    if (isCloud(t)) return 'Cloud Backup';
    // Future types (left here for easy extension):
    // if (t?.template?.name === 'ZFS Replication Task') return 'ZFS → ZFS Backup';
    // if (t?.template?.name === 'Auto Snapshot Task') return 'Automatic Snapshot';
    // if (t?.template?.name === 'ZFS Scrub Task') return 'ZFS Scrub';
    return '—';
}

function isBlank(v: any) {
    return v === undefined || v === null || String(v).trim() === '' || v === '—';
}

function formatRsyncDestination(t: any) {
    const host = getHost(t);
    const path = getTargetPath(t);
    if (isBlank(host)) return isBlank(path) ? '—' : String(path);

    const user = getUser(t);
    const portNum = Number(getPort(t));
    const userPart = isBlank(user) ? '' : `${user}@`;
    const includePort = Number.isFinite(portNum) && portNum > 0 && portNum !== 22; // ← only show non-22 ports
    const portPart = includePort ? `:${portNum}` : '';
    const pathPart = isBlank(path) ? '' : `:${path}`;

    return `${userPart}${host}${portPart}${pathPart}`;
}

function formatCloudDestination(t: any) {
    const remote = String(getRemoteName(t) ?? '').trim();
    const rawPath = String(getTargetPath(t) ?? '').trim();

    if (isBlank(remote)) return isBlank(rawPath) ? '—' : rawPath;

    // If path already starts with "<remote>:", strip that prefix
    let path = rawPath.startsWith(`${remote}:`) ? rawPath.slice(remote.length + 1) : rawPath;

    return `${remote}${isBlank(path) ? '' : `:${path}`}`;
}
function detailsFor(t: any) {
    const source = getSource(t);
    if (isRsync(t)) {
        return {
            source,
            destination: formatRsyncDestination(t),
            extra: undefined,
        };
    } else if (isCloud(t)) {
        return {
            source,
            destination: formatCloudDestination(t),
            extra: undefined,
        };
    }
    return { source, destination: '—', extra: undefined };
}

function coalesce<T>(...vals: T[]) {
    return vals.find(v => v !== undefined && v !== null && v !== '') as T | undefined;
}

function formatDateLike(v: any) {
    if (!v) return '—';
    const d = new Date(v);
    if (Number.isFinite(v) && typeof v === 'number' && v.toString().length === 10) {
        // seconds -> ms
        const d2 = new Date(v * 1000);
        return isNaN(d2.getTime()) ? String(v) : d2.toLocaleString();
    }
    return isNaN(d.getTime()) ? String(v) : d.toLocaleString();
}

function getLastRun(t: any) {
    const v = coalesce(
        t?.lastRun,
        t?.last_run,
        t?.metadata?.lastRun,
        t?.metadata?.last_run,
        t?.stats?.lastRun,
        t?.history?.lastRunAt,
    );
    return formatDateLike(v);
}

/**
 * Rows for the table
 */
const rows = computed(() => {
    const seen = new Set<string>();
    return filtered.value
        .filter((t: any) => {
            const key = `${t?.name}::${t?.template?.name}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        })
        .map((t: any) => ({
            id: t?.id ?? t?.uuid ?? `${t?.name}::${t?.template?.name}`,
            name: t?.name ?? '—',
            type: typeLabel(t),
            details: detailsFor(t),
            status: live.statusFor(t) ?? '—',
            progress: live.progressFor(t),
            isRunning: live.isRunningNow(t),
            schedule: getSchedule(t),
            lastRun: live.lastRunFor(t) ?? getLastRun(t),
            raw: t,
            scope: t.scope
        }));
});

watch(rows, (r) => {
    if (r.length) {
        cachedRows.value = r;
        everLoaded.value = true;
    }
}, { immediate: true });

const displayRows = computed(() => {
    if (!everLoaded.value) return rows.value;      // first load path
    if (isBusy.value) return cachedRows.value;     // keep UI steady during work
    return rows.value;
});

const runningRows = computed(() => displayRows.value.filter((row: any) => row.isRunning));

/**
 * Actions
 */
async function refresh() {
    fetching.value = true;            // do not clear UI
    try {
        await myScheduler.loadTaskInstances();
    } finally {
        fetching.value = false;
    }
}

/* ── Confirmation dialogs ─────────────────────────────── */
const confirmDialogComponent = ref();
const showRunNowPrompt = ref(false);
const showStopNowPrompt = ref(false);
const showRemovePrompt = ref(false);
const operating = ref(false);

async function loadConfirmDialog() {
    if (!confirmDialogComponent.value) {
        const mod = await import('../components/common/ConfirmationDialog.vue');
        confirmDialogComponent.value = mod.default;
    }
}

async function confirmRunNow(t: any) {
    selected.value = t;
    await loadConfirmDialog();
    showRunNowPrompt.value = true;
}

const runNowYes = async () => {
    const t = selected.value;
    if (!t) { showRunNowPrompt.value = false; return; }

    operating.value = true;
    showRunNowPrompt.value = false;

    pushNotification(new Notification('Task Started', `Task ${t?.name ?? ''} has started running.`, 'info', 6000));

    // Immediately mark as running so the UI updates before the server responds
    const id = t?.id ?? t?.uuid ?? t?.name;
    if (id) {
        live.statusMap.value[id] = 'Active (running)';
        live.lastRunMap.value[id] = 'Running now...';
        live.progressMap.value[id] = null;
    }

    try {
        await myScheduler.runTaskNow(t);

        // Inspect exit code for accurate notification
        let exitCode: number | null = null;
        try {
            const latest = await myTaskLog.getLatestEntryFor(t);
            if (latest && typeof latest.exitCode === 'number') exitCode = latest.exitCode;
        } catch { /* fall back to generic */ }

        if (exitCode === 0) {
            pushNotification(new Notification('Task Successful', `Task ${t.name} completed.`, 'success', 6000));
        } else if (exitCode !== null) {
            pushNotification(new Notification('Task Failed', `Task ${t.name} failed (exit code ${exitCode}).`, 'error', 6000));
        } else {
            pushNotification(new Notification('Task Finished', `Task ${t.name} finished.`, 'success', 6000));
        }
    } catch {
        pushNotification(new Notification('Task Failed', `Task ${t?.name ?? ''} failed.`, 'error', 6000));
    } finally {
        operating.value = false;
        live.refreshAll();
    }
};

async function confirmStopNow(t: any) {
    selected.value = t;
    await loadConfirmDialog();
    showStopNowPrompt.value = true;
}

const stopNowYes = async () => {
    const t = selected.value;
    if (!t) { showStopNowPrompt.value = false; return; }

    operating.value = true;
    showStopNowPrompt.value = false;

    pushNotification(new Notification('Task Stopping', `Task ${t?.name ?? ''} is stopping.`, 'info', 6000));

    try {
        await myScheduler.stopTaskNow(t);
        pushNotification(new Notification('Task Stopped', `Task ${t?.name ?? ''} has been stopped.`, 'success', 6000));
    } catch {
        pushNotification(new Notification('Stop Failed', `Failed to stop task ${t?.name ?? ''}.`, 'error', 6000));
    } finally {
        operating.value = false;
        live.refreshAll();
    }
};

async function confirmRemove(t: any) {
    selected.value = t;
    await loadConfirmDialog();
    showRemovePrompt.value = true;
}

const removeYes = async () => {
    const t = selected.value;
    if (!t) { showRemovePrompt.value = false; return; }

    operating.value = true;
    showRemovePrompt.value = false;

    fetching.value = true;
    try {
        await myScheduler.unregisterTaskInstance(t);
        pushNotification(new Notification('Task Removed', 'Backup task deleted.', 'success', 6000));
        await myScheduler.loadTaskInstances();
    } catch (e: any) {
        pushNotification(new Notification('Delete Failed', String(e?.message ?? e), 'error', 6000));
    } finally {
        operating.value = false;
        fetching.value = false;
    }
};

async function edit(t: any) {
    draftStore.setDraft(t, 'edit');
    // router.push({ name: 'SimpleEditTask' });
    router.push({ name: 'SimpleEditTask', query: { session: t.id || t.name } });

}


/**
 * Add New Task
 */
async function openAdd() {
    draftStore.clear();
    // router.push({ name: 'SimpleAddTask' });
    const session = Date.now().toString(); // or nanoid/uuid
    router.push({ name: 'SimpleAddTask', query: { session } });
}
</script>


<style scoped>
tbody tr.row-selected {
    background-color: var(--row-selected-bg) !important;
    outline: 2px solid var(--btn-primary-border);
    outline-offset: -2px;
    border-radius: 0.375rem;
}

tbody tr.row-selected > td {
    background-color: inherit;
}

tbody tr.row-hover:hover {
    background-color: var(--row-hover-bg);
    border-radius: 0.375rem;
}
</style>
