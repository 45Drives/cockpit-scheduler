<template>
    <div class="flex flex-col h-full p-2 bg-default text-default">
        <div>
            <!-- Header / toolbar -->
            <div class="flex items-center justify-between">
                <p class="mt-4 text-medium text-default">Here are the remote backup tasks currently configured.</p>
                <div class="flex items-center gap-2">
                    <button class="btn btn-secondary mt-6" @click="refresh">
                        <ArrowPathIcon class="w-5 h-5" />
                    </button>
                    <button class="btn btn-primary mt-6" @click="openAdd">Add New Task</button>
                </div>
            </div>

            <!-- Empty / loading states -->
            <div class="my-4">
                <div v-if="loading" class="flex items-center justify-center">
                    <CustomLoadingSpinner :width="'w-24'" :height="'h-24'" :baseColor="'text-gray-200'"
                        :fillColor="'fill-gray-500'" />
                </div>
                <!-- <div v-else-if="remoteTasks.length === 0" class="bg-well p-6 rounded-md text-center">
                <h2 class="text-default">No Remote Backup Tasks Found</h2>
                <p class="text-muted mt-1">Click “Add New Task” to create one.</p>
            </div> -->

                <!-- Table -->
                <div v-else class="overflow-x-auto mt-3">
                    <!-- <table class="task-table">
                        <thead>
                            <tr>
                                <th>Task Name</th>
                                <th>Type</th>
                                <th>Destination</th>
                                <th>Status</th>
                                <th>Last Run</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="task in tasks" :key="task.id">
                                <td>{{ task.name }}</td>
                                <td>
                                    <span v-if="task.type === 'S2S'">🔗 Server</span>
                                    <span v-else>☁️ Cloud</span>
                                </td>
                                <td>{{ task.destination }}</td>
                                <td>{{ task.status }}</td>
                                <td>{{ task.lastRun }}</td>
                                <td>
                                    <button @click="toggleRow(task.id)">
                                        {{ expandedRow === task.id ? 'Hide' : 'Details' }}
                                    </button>
                                </td>
                            </tr>

                            <tr v-if="expandedRow === task.id" class="details-row">
                                <td colspan="6">
                                    <strong>Source Path:</strong> {{ task.source }}<br>
                                    <strong>Destination Path:</strong> {{ task.destPath }}<br>
                                    <strong>Schedule:</strong> {{ task.schedule }}<br>
                                    <strong>Retention:</strong> {{ task.retention }}<br>
                                    <strong>Last Error:</strong> {{ task.lastError || 'None' }}
                                </td>
                            </tr>
                        </tbody>
                    </table> -->
                </div>
            </div>

            <!-- Modals (reuse your existing ones) -->
            <!-- <component v-if="showAdd" :is="addComponent" @close="showAdd = false" />
            <component v-if="showSchedule" :is="scheduleComponent" @close="showSchedule = false" :task="selected" />
            <component v-if="showLogs" :is="logsComponent" @close="showLogs = false" :task="selected" />
            <component v-if="showEdit" :is="editComponent" @close="showEdit = false" :task="selected" />
            <component v-if="showConfirm" :is="confirmComponent" @close="showConfirm = false" :title="'Remove Task'"
                :message="`Delete ${selected?.name}?`" :confirmYes="confirmRemove"
                :confirmNo="() => showConfirm = false" /> -->


        </div>
        <div v-show="showAdd" class="mt-4">
            <component :is="addComponent" />
        </div>
    </div>

</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { ArrowPathIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../components/common/CustomLoadingSpinner.vue';
import { injectWithCheck } from '../composables/utility';
import { loadingInjectionKey, schedulerInjectionKey, taskInstancesInjectionKey } from '../keys/injection-keys';
import { Notification, pushNotification } from '@45drives/houston-common-ui';
import { useRouter } from 'vue-router';

const router = useRouter();
const loading = injectWithCheck(loadingInjectionKey, 'loading not provided!');
const myScheduler = injectWithCheck(schedulerInjectionKey, 'scheduler not provided!');
const taskInstances = injectWithCheck(taskInstancesInjectionKey, 'taskInstances not provided!');

const search = ref('');
const expandedRow = ref(null)

function toggleRow(id) {
    expandedRow.value = expandedRow.value === id ? null : id
}

// Only remote backups (Rsync Task + Cloud Sync Task)
const remoteTasks = computed(() =>
    taskInstances.value.filter(t =>
        t.template?.name === 'Rsync Task' || t.template?.name === 'Cloud Sync Task'
    )
);

// Simple name filter
const filtered = computed(() => {
    if (!search.value.trim()) return remoteTasks.value;
    const q = search.value.toLowerCase();
    return remoteTasks.value.filter(t => t.name.toLowerCase().includes(q));
});


async function refresh() {
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;
}

// Quick getters (safe fallbacks)
function isRsync(t: any) { return t.template?.name === 'Rsync Task'; }
function paramsOf(t: any) { return t.parameters?.children ?? []; }

function getSource(t: any) {
    const p = paramsOf(t).find((x: any) => x.key === 'local_path');
    return p?.value ?? '—';
}
function getTarget(t: any) {
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

// Row actions (lean)
const selected = ref<any>(null);

async function runNow(t: any) {
    selected.value = t;
    pushNotification(new Notification('Task Started', `Task ${t.name} has started running.`, 'info', 6000));
    try {
        await myScheduler.runTaskNow(t);
        pushNotification(new Notification('Task Successful', `Task ${t.name} completed.`, 'success', 6000));
    } catch {
        pushNotification(new Notification('Task Failed', `Task ${t.name} failed.`, 'error', 6000));
    }
}

const showSchedule = ref(false);
const scheduleComponent = ref<any>(null);
async function manageSchedule(t: any) {
    selected.value = t;
    const mod = await import('../components/modals/ManageSchedule.vue');
    scheduleComponent.value = mod.default;
    showSchedule.value = true;
}

const showLogs = ref(false);
const logsComponent = ref<any>(null);
async function logs(t: any) {
    selected.value = t;
    const mod = await import('../components/modals/LogView.vue');
    logsComponent.value = mod.default;
    showLogs.value = true;
}

const showEdit = ref(false);
const editComponent = ref<any>(null);
async function edit(t: any) {
    selected.value = t;
    const mod = await import('../components/modals/EditTask.vue');
    editComponent.value = mod.default;
    showEdit.value = true;
}

const showConfirm = ref(false);
const confirmComponent = ref<any>(null);
async function remove(t: any) {
    selected.value = t;
    const mod = await import('../components/common/ConfirmationDialog.vue');
    confirmComponent.value = mod.default;
    showConfirm.value = true;
}
async function confirmRemove() {
    await myScheduler.unregisterTaskInstance(selected.value);
    showConfirm.value = false;
    await refresh();
    pushNotification(new Notification('Task Removed', 'Backup task deleted.', 'success', 6000));
}

// “Add New Task” — use the simplified creator if you’ve added it; fallback to your existing AddTask
const showAdd = ref(false);
const addComponent = ref<any>(null);
async function openAdd() {
    // try {
    //     const mod = await import('../components/simple/SimpleAddTask.vue'); // << if you saved it here
    //     addComponent.value = mod.default;
    // } catch {
    //     const mod = await import('../components/modals/AddTask.vue');               // fallback
    //     addComponent.value = mod.default;
    // }
    // showAdd.value = true;
    router.push({ name: 'SimpleAddTask' });
}
</script>
