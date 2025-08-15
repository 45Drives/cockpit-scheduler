<template>
    <div class="flex flex-col h-full p-2 bg-default text-default">
        <!-- Header / toolbar -->
        <div class="flex items-center justify-between gap-2">
            <div class="flex flex-col">
                <p class="mt-4 text-medium text-default">
                    Here are the remote backup tasks currently configured.
                </p>
            </div>
            <div class="flex items-center gap-2">
                <button class="btn btn-secondary mt-6" @click="refresh" :disabled="loading">
                    <ArrowPathIcon class="w-5 h-5" />
                </button>
                <button class="btn btn-primary mt-6" @click="openAdd">Add New Task</button>
            </div>
        </div>

        <!-- Empty / loading states -->
        <div class="my-4">
            <div v-if="!everLoaded && (fetching || loading)" class="flex items-center justify-center">
                <CustomLoadingSpinner :width="'w-24'" :height="'h-24'" :baseColor="'text-gray-200'"
                    :fillColor="'fill-gray-500'" />
            </div>

            <div v-else-if="displayRows.length === 0" class="bg-well p-6 rounded-md text-center">
                <h2 class="text-default">No Remote Backup Tasks Found</h2>
                <p class="text-muted mt-1">Click “Add New Task” to create one.</p>
            </div>

            <!-- Table -->
            <div v-else class="overflow-x-auto mt-3">
                <table class="task-table min-w-full bg-well rounded-md border border-default p-1">
                    <thead>
                        <tr>
                            <th class="text-left p-2">Task Name</th>
                            <th class="text-left p-2">Type</th>
                            <th class="text-left p-2">Details</th>
                            <th class="text-left p-2">Status</th>
                            <th class="text-left p-2">Schedule</th>
                            <th class="text-left p-2">Last Run</th>
                            <th class="text-left p-2">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="row in displayRows" :key="row.id" class="border-t border-default/10">
                            <td class="p-2 align-top">
                                <div class="font-medium">{{ row.name }}</div>
                            </td>
                            <td class="p-2 align-top">
                                <span
                                    class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-default/10"
                                    :title="row.type">
                                    {{ row.type }}
                                </span>
                            </td>
                            <td class="p-2 align-top">
                                <div class="text-sm leading-5">
                                    <div><span class="text-muted">Source:</span> {{ row.details.source }}</div>
                                    <div><span class="text-muted">Destination:</span> {{ row.details.destination }}
                                    </div>
                                    <div v-if="row.details.extra"><span class="text-muted">Info:</span> {{
                                        row.details.extra }}</div>
                                </div>
                            </td>
                            <td class="p-2 align-top">
                                <span class="text-sm" :class="taskStatusClass(row.status)">{{ row.status || '—'
                                    }}</span>
                            </td>
                            <td class="p-2 align-top">
                                <span class="text-sm">{{ row.schedule }}</span>
                            </td>
                            <td class="p-2 align-top">
                                <span class="text-sm">{{ row.lastRun }}</span>
                            </td>
                            <td class="p-2 align-top">
                                <div class="flex gap-2">
                                    <button class="btn btn-xs btn-primary" @click="runNow(row.raw)" :disabled="loading">
                                        Run Now
                                    </button>
                                    <button class="btn btn-xs btn-secondary" @click="edit(row.raw)" :disabled="loading">
                                        Edit
                                    </button>
                                    <button class="btn btn-xs btn-danger" @click="remove(row.raw)" :disabled="loading">
                                        Delete
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, onActivated, onUnmounted, onMounted, watch } from 'vue';
import { ArrowPathIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../components/common/CustomLoadingSpinner.vue';
import { injectWithCheck } from '../composables/utility';
import { loadingInjectionKey, schedulerInjectionKey, taskInstancesInjectionKey, logInjectionKey } from '../keys/injection-keys';
import { Notification, pushNotification, confirm } from '@45drives/houston-common-ui';
import { useRouter } from 'vue-router';
import { useTaskDraftStore } from '../stores/taskDraft';
import { useLiveTaskStatus, taskStatusClass } from '../composables/useLiveTaskStatus'; // NEW

const router = useRouter();
const loading = injectWithCheck(loadingInjectionKey, 'loading not provided!');
const myScheduler = injectWithCheck(schedulerInjectionKey, 'scheduler not provided!');
const taskInstances = injectWithCheck(taskInstancesInjectionKey, 'taskInstances not provided!');
const draftStore = useTaskDraftStore();

const search = ref('');
const selected = ref<any>(null);
const myTaskLog = injectWithCheck(logInjectionKey, 'log not provided!');

const fetching = ref(false);
const everLoaded = ref(false);
const cachedRows = ref<any[]>([]);

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
    return ivals.map((i: any) => myScheduler.parseIntervalIntoShortString(i)).join(' + ');
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

function detailsFor(t: any) {
    const source = getSource(t);
    if (isRsync(t)) {
        const user = getUser(t);
        const host = getHost(t);
        const port = getPort(t);
        const path = getTargetPath(t);
        return {
            source,
            destination: `${user}@${host}:${port}${path ? `:${path}` : ''}`,
            extra: undefined,
        };
    } else if (isCloud(t)) {
        const remote = getRemoteName(t);
        const path = getTargetPath(t);
        return {
            source,
            destination: `${remote}:${path}`,
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
            schedule: getSchedule(t),
            lastRun: live.lastRunFor(t) ?? getLastRun(t),
            raw: t,
        }));
});

watch(rows, (r) => {
    if (r.length) {
        cachedRows.value = r;
        everLoaded.value = true;
    }
}, { immediate: true });

const displayRows = computed(() => {
    if (!everLoaded.value) return rows.value;                 // before first load
    if ((fetching.value || loading.value) && rows.value.length === 0)
        return cachedRows.value;                                // show cache during refresh
    return rows.value;                                        // normal
});


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

async function runNow(t: any) {
    selected.value = t;
    pushNotification(new Notification('Task Started', `Task ${t?.name ?? ''} has started running.`, 'info', 6000));
    try {
        await myScheduler.runTaskNow(t);
        pushNotification(new Notification('Task Successful', `Task ${t?.name ?? ''} completed.`, 'success', 6000));
    } catch {
        pushNotification(new Notification('Task Failed', `Task ${t?.name ?? ''} failed.`, 'error', 6000));
    }
}

async function edit(t: any) {
    draftStore.setDraft(t, 'edit');
    router.push({ name: 'SimpleEditTask' });
}

async function remove(t: any) {
    const ok = window.confirm(`Delete "${t?.name ?? 'this task'}"? This cannot be undone.`);
    if (!ok) return;
    loading.value = true;
    fetching.value = true;            // keep table visible while we reload
    try {
        await myScheduler.unregisterTaskInstance(t);
        pushNotification(new Notification('Task Removed', 'Backup task deleted.', 'success', 6000));
        await myScheduler.loadTaskInstances();
    } catch (e: any) {
        pushNotification(new Notification('Delete Failed', String(e?.message ?? e), 'error', 8000));
    } finally {
        loading.value = false;
        fetching.value = false;
    }
}
/**
 * Add New Task
 */
async function openAdd() {
    draftStore.clear(); 
    router.push({ name: 'SimpleAddTask' });
}
</script>
