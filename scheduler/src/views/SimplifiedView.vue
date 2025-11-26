<template>
    <div class="h-full flex flex-col bg-well text-default">
        <!-- Toolbar (same as BackUpListView) -->
        <div class="flex flex-row items-center justify-between font-bold">
            <div class="flex items-center justify-start">
                <button class="btn btn-primary text-sm mr-3" @click="openAdd" :disabled="loading">
                    <PlusIcon class="w-5 h-5 text-white" />
                </button>
                Schedule New Backup
            </div>
            <div class="flex items-center justify-end">
                Refresh Backup List
                <button class="btn btn-secondary text-sm ml-3" @click="refresh" :disabled="loading">
                    <ArrowPathIcon class="w-5 h-5 text-white" />
                </button>
            </div>
        </div>

        <!-- Content area fills remaining height; one scroll container -->
        <div class="flex-1 min-h-0 mt-2 relative">
            <!-- initial load -->
            <div v-if="showInitialSpinner" class="absolute inset-0 flex items-center justify-center">
                <CustomLoadingSpinner :width="'w-24'" :height="'h-24'" :baseColor="'text-gray-200'"
                    :fillColor="'fill-gray-500'" />
            </div>

            <!-- empty state -->
            <div v-else-if="displayRows.length === 0" class="h-full flex items-center justify-center">
                <div class="text-center">
                    <h2 class="text-default">No Remote Backup Tasks Found</h2>
                    <p class="text-muted mt-1">Click “Add New Task” to create one.</p>
                </div>
            </div>

            <!-- table -->
            <div v-else class="h-full overflow-hidden">
                <!-- busy overlay while keeping table visible -->
                <div v-if="showOverlaySpinner"
                    class="absolute inset-0 z-[100] flex items-center justify-center bg-well/60 backdrop-blur-sm">
                    <CustomLoadingSpinner :width="'w-16'" :height="'h-16'" :baseColor="'text-gray-200'"
                        :fillColor="'fill-gray-500'" />
                </div>

                <!-- match BackUpListView: border, rounded, sticky header, single scroll -->
                <div class="h-full overflow-auto border border-default rounded-md">
                    <table class="min-w-full text-sm">
                        <thead class="text-left sticky top-0 bg-accent z-10">
                            <tr class="border-b border-default">
                                <th class="px-3 py-2">Task Name</th>
                                <th class="px-3 py-2">Type</th>
                                <th class="px-3 py-2">Details</th>
                                <th class="px-3 py-2">Status</th>
                                <th class="px-3 py-2">Schedule</th>
                                <th class="px-3 py-2">Last Run</th>
                                <th class="px-3 py-2">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in displayRows" :key="row.id"
                                class="border-b border-default bg-default hover:bg-well text-left">
                                <td class="px-3 py-2 align-top">
                                    <div class="font-medium">{{ row.name }}</div>
                                </td>
                                <td class="px-3 py-2 align-top">
                                    <span
                                        class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-default/10"
                                        :title="row.type">
                                        {{ row.type }} (Scope: {{ row.scope }})
                                    </span>
                                </td>
                                <td class="px-3 py-2 align-top">
                                    <div class="text-sm leading-5">
                                        <div><span class="text-muted">Source:</span> {{ row.details.source }}</div>
                                        <div><span class="text-muted">Destination:</span> {{ row.details.destination }}
                                        </div>
                                        <div v-if="row.details.extra"><span class="text-muted">Info:</span> {{
                                            row.details.extra }}</div>
                                    </div>
                                </td>
                                <td class="px-3 py-2 align-top">
                                    <span class="text-sm" :class="taskStatusClass(row.status)">{{ row.status || '—'
                                        }}</span>
                                </td>
                                <td class="px-3 py-2 align-top">
                                    <span class="text-sm">{{ row.schedule }}</span>
                                </td>
                                <td class="px-3 py-2 align-top">
                                    <span class="text-sm">{{ row.lastRun }}</span>
                                </td>
                                <td class="px-3 py-2 align-top">
                                    <div class="flex gap-2">
                                        <button class="btn btn-xs btn-primary" @click="runNow(row.raw)"
                                            :disabled="loading">Run Now</button>
                                        <button class="btn btn-xs btn-secondary" @click="edit(row.raw)"
                                            :disabled="loading">Edit</button>
                                        <button class="btn btn-xs btn-danger" @click="remove(row.raw)"
                                            :disabled="loading">Delete</button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div> <!-- /bordered scroll box -->
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, onActivated, onUnmounted, onMounted, watch, provide } from 'vue';
import { ArrowPathIcon, PlusIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../components/common/CustomLoadingSpinner.vue';
import { injectWithCheck } from '../composables/utility';
import { loadingInjectionKey, schedulerInjectionKey, taskInstancesInjectionKey, logInjectionKey } from '../keys/injection-keys';
import { Notification, pushNotification, confirm } from '@45drives/houston-common-ui';
import { useRouter } from 'vue-router';
import { useTaskDraftStore } from '../stores/taskDraft';
import { useLiveTaskStatus, taskStatusClass } from '../composables/useLiveTaskStatus';

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
    // router.push({ name: 'SimpleEditTask' });
    router.push({ name: 'SimpleEditTask', query: { session: t.id || t.name } });

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
        pushNotification(new Notification('Delete Failed', String(e?.message ?? e), 'error', 6000));
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
    // router.push({ name: 'SimpleAddTask' });
    const session = Date.now().toString(); // or nanoid/uuid
    router.push({ name: 'SimpleAddTask', query: { session } });
}
</script>
