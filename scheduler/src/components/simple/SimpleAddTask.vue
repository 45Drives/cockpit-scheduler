<template>
    <div class="h-full w-full flex flex-col bg-well">
        <!-- Single scroll area (same height/feel as local list) --> <!-- Top toolbar (mirrors List toolbar) -->
        <div class="flex flex-row items-center justify-between font-bold shrink-0 text-default">
            <div class="flex items-center">
                <button class="btn btn-danger text-sm mr-3" @click="goBack">Cancel</button>
                {{ isEditMode ? 'Edit Backup Task' : 'Create Backup Task' }}
            </div>
            <button class="btn btn-success text-sm" :disabled="!isDirty || adding" @click="saveAll">
                {{ isEditMode ? (adding ? 'Saving…' : 'Save Changes') : (adding ? 'Creating…' : 'Create Task') }}
            </button>
        </div>

        <div class="flex-1 min-h-0 mt-2 border border-default rounded-md bg-well overflow-auto">
            <div class="grid grid-cols-12 gap-2 p-2 items-stretch">
                <!-- LEFT: parameters card -->
                <div class="col-span-12 xl:col-span-6 min-h-0">
                    <div class="h-full flex-1 bg-accent text-default rounded-md border border-default p-2">
                        <!-- Task Name -->
                        <div name="task-name" class="mb-2">
                            <div class="flex flex-row justify-between items-center">
                                <div class="flex flex-row items-center">
                                    <label class="block text-sm leading-6 text-default">Task Name</label>
                                    <InfoTile class="ml-1"
                                        title="Name can have letters, numbers, and underscores. Spaces convert to underscores upon save." />
                                </div>
                                <ExclamationCircleIcon v-if="newTaskNameErrorTag" class="mt-1 w-5 h-5 text-danger" />
                            </div>
                            <input type="text" v-model="newTaskName"
                                :class="['my-1 block w-full input-textlike text-default', newTaskNameErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                placeholder="New Task"
                                title="Name can have letters, numbers, and underscores. Spaces convert to underscores upon save." />
                        </div>

                        <!-- Template -->
                        <div name="task-template" v-if="allowedTemplates.length > 0" class="mb-2">
                            <label for="task-template-selection" class="block text-sm leading-6 text-default">Task
                                Template</label>
                            <select id="task-template-selection" v-model="selectedTemplate"
                                name="task-template-selection"
                                class="text-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                                <option :value="undefined">Select Type of Task to Add</option>
                                <option v-for="template, idx in allowedTemplates" :key="idx" :value="template">
                                    {{ displayName(template) }}
                                </option>
                            </select>
                        </div>

                        <!-- ZFS Replication info blurb -->
                        <div v-if="selectedTemplate?.name === 'ZFS Replication Task'" class="mb-2 rounded-md bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 p-3">
                            <p class="text-sm text-blue-700 dark:text-blue-300">
                                <strong>ZFS Backup</strong> uses ZFS replication to send only the changes (incremental snapshots)
                                since the last backup — much faster than copying everything each time. It also preserves
                                exact file permissions, timestamps, and metadata. Recommended when both servers use ZFS storage.
                            </p>
                        </div>

                        <!-- Parameters -->
                        <div v-if="selectedTemplate" class="min-h-0">
                            <ParameterInput :key="paramInputKey" ref="parameterInputComponent"
                                :selectedTemplate="selectedTemplate" :simple="true"
                                :task="originalTask || draftTask || undefined"
                                @open-wireshield="handleOpenWireShield" />
                        </div>
                    </div>
                </div>

                <!-- RIGHT: schedule + how long backups are kept -->
                <div class="col-span-12 xl:col-span-6 min-h-0 flex flex-col gap-2">
                    <SimpleCalendar :title="'Schedule Task'" v-model:taskSchedule="uiSchedule"
                        class="w-full flex-1 min-h-0" />

                    <div v-if="showRetention"
                        class="shrink-0 rounded-md border border-default bg-accent text-default p-2">
                        <h3 class="text-base font-medium leading-6">How far back do you want to be able to restore?</h3>
                        <p class="text-xs text-muted mt-1">
                            Each run leaves behind a restore point. Older ones are cleaned up automatically so your
                            drives don't slowly fill up.
                        </p>

                        <div class="mt-3" :class="isSnapshotOnly ? '' : 'grid grid-cols-1 sm:grid-cols-2 gap-2'">
                            <div>
                                <label for="keep-local" class="block text-sm">
                                    {{ isSnapshotOnly ? 'Keep restore points for' : 'On this server' }}
                                </label>
                                <select id="keep-local" v-model="keepLocal" class="input-textlike w-full text-sm mt-1">
                                    <option v-for="opt in keepLocalOptions" :key="opt.key" :value="opt.key">
                                        {{ opt.label }}
                                    </option>
                                </select>
                                <p class="text-[11px] text-muted mt-1">
                                    {{ isSnapshotOnly
                                        ? 'Snapshots stay on this server, so this is how far back you can undo a change.'
                                        : 'For undoing a mistake quickly.' }}
                                </p>
                            </div>

                            <div v-if="!isSnapshotOnly">
                                <label for="keep-backup" class="block text-sm">On the backup server</label>
                                <select id="keep-backup" v-model="keepBackup" class="input-textlike w-full text-sm mt-1">
                                    <option v-for="opt in keepBackupOptions" :key="opt.key" :value="opt.key">
                                        {{ opt.label }}
                                    </option>
                                </select>
                                <p class="text-[11px] text-muted mt-1">Your long-term safety net.</p>
                            </div>
                        </div>

                        <p v-if="backupKeptShorterThanLocal" class="text-[11px] text-amber-600 dark:text-amber-400 mt-2">
                            The backup server is set to forget sooner than this server does, so it will hold less
                            history than the original. That is usually the wrong way around.
                        </p>
                        <p v-else-if="keepsEverything" class="text-[11px] text-amber-600 dark:text-amber-400 mt-2">
                            Nothing will ever be cleaned up. Restore points will keep building until one of the drives
                            runs out of space.
                        </p>
                        <p v-else-if="isSnapshotOnly" class="text-[11px] text-muted mt-2">
                            Snapshots protect against deleting or overwriting a file, but not against losing the
                            server itself. Add a backup task for that.
                        </p>
                        <p v-else class="text-[11px] text-muted mt-2">
                            Only restore points created by this task are cleaned up, and the newest one is always kept.
                            Your actual files are never deleted.
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Bottom action bar (pinned, matches your local bottom controls) -->
        <!-- <div class="shrink-0 mt-2 flex items-center justify-between">
            <button @click="goBack" class="btn btn-secondary h-16 w-40">Back</button>
            <button :disabled="!isDirty || adding" @click="saveAll" class="btn btn-primary h-16 w-48">
                {{ isEditMode ? (adding ? 'Saving…' : 'Save Changes') : (adding ? 'Creating…' : 'Create Task') }}
            </button>
        </div> -->
    </div>
</template>
<script setup lang="ts">
import { computed, inject, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, provide, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import ParameterInput from '../parameters/ParameterInput.vue';
import SimpleCalendar from './SimpleCalendar.vue';
import InfoTile from '../common/InfoTile.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import { pushNotification, Notification, CardContainer } from '@45drives/houston-common-ui';
import {
    TaskInstance,
    ZFSReplicationTaskTemplate,
    TaskSchedule as ModelTaskSchedule,
    AutomatedSnapshotTaskTemplate,
    RsyncTaskTemplate,
    ScrubTaskTemplate,
    SmartTestTemplate,
    CloudSyncTaskTemplate,
    CustomTaskTemplate,
} from '../../models/Tasks';
import type { TaskInstance as TaskInstanceType, TaskTemplate as TaskTemplateType } from '../../models/Tasks';
import type { TaskSchedule as UITaskSchedule } from '@45drives/houston-common-lib';
import { useTaskDraftStore } from '../../stores/taskDraft';
import { injectWithCheck, getPoolData } from '../../composables/utility';
import { logTaskEvent, logToClient } from '../../composables/useTaskLogBridge';
import { clearSavedDraft, markDraftSession, readSavedDraft, saveDraft, takeVpnHost } from '../../composables/taskDraftStorage';
import { schedulerModulePath } from '../../composables/moduleReturn';
import { loadingInjectionKey, schedulerInjectionKey, taskTemplatesInjectionKey, taskInstancesInjectionKey } from '../../keys/injection-keys';

defineOptions({ name: 'SimpleTaskForm' });
// ---- props ----
const props = defineProps<{ mode?: 'create' | 'edit', existingTask?: TaskInstanceType }>();
const draft = useTaskDraftStore();

// Return the actual task (not the store object)
const originalTask = computed<TaskInstanceType | null>(() => props.existingTask ?? draft.draft ?? null);

// Treat either prop mode or store mode as the source of truth
const isEditMode = computed(() => (props.mode ?? draft.mode) === 'edit');

// ---- state/refs ----
const newTask = ref<TaskInstance | null>(null);
const adding = ref(false);
const errorList = ref<string[]>([]);
const originalName = ref(props.existingTask?.name);
const newTaskName = ref('');
const newTaskNameErrorTag = ref(false);
const selectedTemplate = ref<TaskTemplateType>();
const parameterInputComponent = ref();
const parameters = ref<any>();
const notesTask = ref('');
const paramInputKey = ref(0);

// Stand-in "existing task" built from a restored draft so the parameter components
// rehydrate their own internal form state (pools, datasets, hosts, flags, …).
const draftTask = ref<TaskInstanceType | null>(null);

// vpnHost ref — will be set from draft in onMounted, before child components mount
const vpnHostRef = ref<string | null>(null);
provide('vpnHost', vpnHostRef);

// Listen for localStorage changes from WireShield (same origin, hidden iframe)
// This fires when another iframe (WireShield) modifies localStorage
function handleStorageEvent(event: StorageEvent) {
    if (event.key === 'scheduler-task-draft' && event.newValue) {
        try {
            const snap = JSON.parse(event.newValue);
            if (snap.vpnHost) {
                vpnHostRef.value = snap.vpnHost;
            }
        } catch { /* ignore */ }
    }
    if (event.key === 'scheduler-vpn-host' && event.newValue) {
        vpnHostRef.value = event.newValue;
    }
}
window.addEventListener('storage', handleStorageEvent);
onUnmounted(() => window.removeEventListener('storage', handleStorageEvent));

// schedule bridge init
const uiSchedule = ref<UITaskSchedule>(toUISchedule(originalTask.value?.schedule));

// ---- retention (how long snapshots are kept) ----
type RetentionPreset = { key: string; label: string; time: number; unit: string };

const RETENTION_PRESETS: RetentionPreset[] = [
    { key: 'forever', label: 'Keep everything', time: 0, unit: '' },
    { key: '7-days', label: '1 week', time: 7, unit: 'days' },
    { key: '14-days', label: '2 weeks', time: 14, unit: 'days' },
    { key: '1-months', label: '1 month', time: 1, unit: 'months' },
    { key: '3-months', label: '3 months', time: 3, unit: 'months' },
    { key: '6-months', label: '6 months', time: 6, unit: 'months' },
    { key: '1-years', label: '1 year', time: 1, unit: 'years' },
    { key: '2-years', label: '2 years', time: 2, unit: 'years' },
];

// Matches the unit table in the pruning script.
const RETENTION_UNIT_SECONDS: Record<string, number> = {
    minutes: 60, hours: 3600, days: 86400, weeks: 604800, months: 2592000, years: 31536000,
};

const DEFAULT_KEEP_LOCAL = '14-days';
const DEFAULT_KEEP_BACKUP = '1-years';

const keepLocal = ref(DEFAULT_KEEP_LOCAL);
const keepBackup = ref(DEFAULT_KEEP_BACKUP);

const SNAPSHOT_TEMPLATE = 'Automated Snapshot Task';
const REPLICATION_TEMPLATE = 'ZFS Replication Task';

// Snapshot tasks keep copies in one place; replication keeps them in two.
const isSnapshotOnly = computed(() => selectedTemplate.value?.name === SNAPSHOT_TEMPLATE);
const showRetention = computed(
    () => isSnapshotOnly.value || selectedTemplate.value?.name === REPLICATION_TEMPLATE
);

function retentionKey(r?: { retentionTime?: number; retentionUnit?: string } | null): string {
    if (!r || !r.retentionTime || r.retentionTime <= 0 || !r.retentionUnit) return 'forever';
    return `${r.retentionTime}-${r.retentionUnit}`;
}

function retentionFromKey(key: string) {
    if (key === 'forever') return null;
    const [time, unit] = key.split('-');
    const n = Number(time);
    if (!Number.isFinite(n) || n <= 0 || !RETENTION_UNIT_SECONDS[unit]) return null;
    return { retentionTime: n, retentionUnit: unit };
}

function retentionSeconds(key: string): number {
    const r = retentionFromKey(key);
    return r ? r.retentionTime * RETENTION_UNIT_SECONDS[r.retentionUnit] : Infinity;
}

// The advanced editor allows any number/unit pair, so offer whatever a task already
// has rather than snapping it to the nearest preset behind the user's back.
function retentionOptions(current: string): RetentionPreset[] {
    if (RETENTION_PRESETS.some(p => p.key === current)) return RETENTION_PRESETS;
    const parsed = retentionFromKey(current);
    if (!parsed) return RETENTION_PRESETS;
    const extra: RetentionPreset = {
        key: current,
        label: `${parsed.retentionTime} ${parsed.retentionUnit}`,
        time: parsed.retentionTime,
        unit: parsed.retentionUnit,
    };
    return [...RETENTION_PRESETS, extra].sort(
        (a, b) => a.time * (RETENTION_UNIT_SECONDS[a.unit] ?? 0) - b.time * (RETENTION_UNIT_SECONDS[b.unit] ?? 0)
    );
}

const keepLocalOptions = computed(() => retentionOptions(keepLocal.value));
const keepBackupOptions = computed(() => retentionOptions(keepBackup.value));

const backupKeptShorterThanLocal = computed(
    () => !isSnapshotOnly.value && retentionSeconds(keepBackup.value) < retentionSeconds(keepLocal.value)
);

const keepsEverything = computed(
    () => keepLocal.value === 'forever' && (isSnapshotOnly.value || keepBackup.value === 'forever')
);

// A brand-new task gets a bounded default; an existing one keeps exactly what it had,
// so opening a task in the simple view never starts deleting snapshots on its own.
function loadRetentionFrom(model?: ModelTaskSchedule | null, templateName?: string) {
    if (!model) {
        keepLocal.value = DEFAULT_KEEP_LOCAL;
        keepBackup.value = DEFAULT_KEEP_BACKUP;
        return;
    }
    const retention: any = (model as any)?.intervals?.[0]?.retention ?? null;
    if (templateName === SNAPSHOT_TEMPLATE) {
        keepLocal.value = retentionKey(retention?.destination ?? retention?.source);
        keepBackup.value = DEFAULT_KEEP_BACKUP;
        return;
    }
    keepLocal.value = retentionKey(retention?.source);
    keepBackup.value = retentionKey(retention?.destination);
}

// helper used by watcher
function resetForm() {
    newTaskName.value = '';
    selectedTemplate.value = undefined;
    parameters.value = undefined;
    notesTask.value = '';
    uiSchedule.value = toUISchedule(null);
    loadRetentionFrom(null);
    paramInputKey.value++; // reset ParameterInput
}

watch(isEditMode, (edit) => {
    if (!edit) resetForm();
}, { immediate: true });

onMounted(async () => {
    await nextTick();

    // Check for standalone vpnHost fallback (WireShield couldn't find draft)
    const standaloneVpn = takeVpnHost();
    if (standaloneVpn) {
        vpnHostRef.value = standaloneVpn;
    }

    // Restore an in-progress draft (WireShield round trip, or a resumed session).
    // The draft stays in storage so it remains resumable until the task is
    // created or explicitly discarded.
    const snap = isEditMode.value ? null : readSavedDraft();
    if (snap) {
        newTaskName.value = snap.name ?? '';
        if (snap.vpnHost) {
            vpnHostRef.value = snap.vpnHost;
        }
        const found = taskTemplates.find((t: any) => t.name === snap.templateName);
        if (found) selectedTemplate.value = found;
        const localSchema = makeLocalSchemaByName(snap.templateName);
        parameters.value = localSchema ? hydrateSchemaWithRaw(localSchema, snap.parameters) : snap.parameters;
        notesTask.value = snap.notes ?? '';
        if (snap.schedule) {
            // Restore Date objects from serialized strings
            const sched = snap.schedule;
            if (sched.startDate) sched.startDate = new Date(sched.startDate);
            uiSchedule.value = sched;
        }
        if (snap.keepLocal) keepLocal.value = snap.keepLocal;
        if (snap.keepBackup) keepBackup.value = snap.keepBackup;
        const tpl = templateFromSelection();
        if (tpl && parameters.value) {
            draftTask.value = new TaskInstance(
                sanitizeName(newTaskName.value) || 'draft',
                tpl,
                parameters.value,
                toModelSchedule(uiSchedule.value),
                notesTask.value,
            ) as unknown as TaskInstanceType;
        }
        paramInputKey.value++;
        startAutosave();
        return; // skip default initialization
    }
    if (isEditMode.value && originalTask.value) {
        // Editing: load the task's existing schedule + other fields
        uiSchedule.value = toUISchedule(originalTask.value.schedule);
        loadRetentionFrom(originalTask.value.schedule, originalTask.value.template?.name);
        prefillFromTask(originalTask.value);
    } else {
        // Creating: clear to defaults (blank schedule + empty form)
        resetForm();                   // clears name/template/params/notes
        uiSchedule.value = toUISchedule(null); // default blank UI schedule
    }
    startAutosave();
});


// ---- deps ----
const router = useRouter();
const taskInstances = injectWithCheck(taskInstancesInjectionKey, 'taskInstances not provided!');
const taskTemplates = injectWithCheck(taskTemplatesInjectionKey, 'taskTemplates not provided!');
const loading = injectWithCheck(loadingInjectionKey, 'loading not provided!');
const myScheduler = injectWithCheck(schedulerInjectionKey, 'scheduler not provided!');

const simpleAllowed = ['Automated Snapshot Task', 'Rsync Task', 'Cloud Sync Task', 'ZFS Replication Task'];
const localZfsAvailable = ref(false);

onMounted(async () => {
    try {
        const pools = await getPoolData();
        localZfsAvailable.value = Array.isArray(pools) && pools.length > 0;
    } catch {
        localZfsAvailable.value = false;
    }
});

const ZFS_ONLY_TEMPLATES = ['ZFS Replication Task', 'Automated Snapshot Task'];

const allowedTemplates = computed(() => {
    const orderMap = Object.fromEntries(simpleAllowed.map((n, i) => [n, i]));
    return taskTemplates
        .filter((t: any) => simpleAllowed.includes(t.name))
        .filter((t: any) => !ZFS_ONLY_TEMPLATES.includes(t.name) || localZfsAvailable.value)
        .sort((a: any, b: any) => orderMap[a.name] - orderMap[b.name]);
});

const nameOverrides: Record<string, string> = {
    'ZFS Replication Task': 'ZFS Backup (Server-to-Server)',
    'Automated Snapshot Task': 'Snapshots (This Server Only)',
    'Scrub Task': 'Disk Health Check (ZFS Scrub)',
    'Rsync Task': 'File Copy / Sync (Rsync)',
    'Cloud Sync Task': 'Cloud Backup',
};

const displayName = (template: TaskTemplateType) => nameOverrides[template.name] || template.name;

// ---- schedule bridge (UI <-> model) ----
function toUISchedule(model?: ModelTaskSchedule | null): UITaskSchedule {
    const now = new Date();
    // ----- DEFAULT when no model schedule: HOURLY, start in 1 hour -----
    if (!model || !Array.isArray(model.intervals) || model.intervals.length === 0) {
        // assume `now` already exists; if not: const now = new Date();
        const start = new Date(now);
        start.setMinutes(0, 0, 0);
        if (start <= now) start.setHours(start.getHours() + 1);

        return { repeatFrequency: 'hour', startDate: start } as UITaskSchedule;
    }
    // ---------------------------------------------------------


    const intv: any = model.intervals[0] ?? {};
    const v = (x: any) => (x?.value ?? x);
    const isStar = (x: any) => String(v(x) ?? '*') === '*';
    const asNum = (x: any, fb: number) => {
        const s = String(v(x) ?? '');
        const n = Number(s);
        return Number.isFinite(n) ? n : fb;
    };

    const hasDOW = Array.isArray(intv.dayOfWeek) && intv.dayOfWeek.length > 0;
    const hourStar = isStar(intv.hour);
    const dayStar = isStar(intv.day);
    const monthStar = isStar(intv.month);
    const yearStar = isStar(intv.year);

    let repeatFrequency: 'hour' | 'day' | 'week' | 'month' = 'day';
    if (hourStar && dayStar && monthStar && yearStar) repeatFrequency = 'hour';
    else if (hasDOW) repeatFrequency = 'week';
    else if (!dayStar && monthStar) repeatFrequency = 'month';

    const hour = asNum(intv.hour, now.getHours());
    const minute = asNum(intv.minute, now.getMinutes());

    if (repeatFrequency === 'week') {
        const DOW_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        const raw = intv.dayOfWeek[0];
        const targetDow = typeof raw === 'number'
            ? raw
            : (() => {
                const idx = DOW_NAMES.indexOf(String(raw).slice(0, 3));
                return idx >= 0 ? idx : now.getDay();
            })();

        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0);
        const delta = (targetDow - start.getDay() + 7) % 7;
        if (delta !== 0 || start <= now) start.setDate(start.getDate() + (delta || 7));
        return { repeatFrequency, startDate: start } as UITaskSchedule;
    }

    if (repeatFrequency === 'hour') {
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), minute, 0, 0);
        if (start <= now) start.setHours(start.getHours() + 1);
        return { repeatFrequency, startDate: start } as UITaskSchedule;
    }

    const year = asNum(intv.year, now.getFullYear());
    const month = asNum(intv.month, now.getMonth() + 1);
    const day = asNum(intv.day, now.getDate());
    return { repeatFrequency, startDate: new Date(year, Math.min(11, Math.max(0, month - 1)), day, hour, minute) } as UITaskSchedule;
}

const DOW_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function toModelSchedule(ui: UITaskSchedule): ModelTaskSchedule {
    const d = ui.startDate;

    const baseInterval: any = {
        minute: { value: String(d.getMinutes()) },
        hour: { value: ui.repeatFrequency === 'hour' ? '*' : String(d.getHours()) },
        // Default to recurring years unless we ever support one-time:
        year: { value: '*' },
    };

    if (ui.repeatFrequency === 'hour') {
        baseInterval.day = { value: '*' };
        baseInterval.month = { value: '*' };
        // year already '*'
    } else if (ui.repeatFrequency === 'day') {
        baseInterval.day = { value: '*' };
        baseInterval.month = { value: '*' };
    } else if (ui.repeatFrequency === 'week') {
        baseInterval.day = { value: '*' };
        baseInterval.month = { value: '*' };
        baseInterval.dayOfWeek = [DOW_NAMES[d.getDay()]]; // "Sun"..."Sat"
    } else if (ui.repeatFrequency === 'month') {
        baseInterval.day = { value: String(d.getDate()) };
        baseInterval.month = { value: '*' };
    }

    if (showRetention.value) {
        const retention: any = {};
        if (isSnapshotOnly.value) {
            // One location, and both the scheduler and the snapshot script read it from `destination`.
            const keep = retentionFromKey(keepLocal.value);
            if (keep) retention.destination = keep;
        } else {
            const source = retentionFromKey(keepLocal.value);
            const destination = retentionFromKey(keepBackup.value);
            if (source) retention.source = source;
            if (destination) retention.destination = destination;
        }
        if (Object.keys(retention).length > 0) baseInterval.retention = retention;
    }

    return new ModelTaskSchedule(true, [baseInterval]);
}

// schedule bridge watch
watch(() => originalTask.value, (t) => {
    uiSchedule.value = toUISchedule(t?.schedule);
    loadRetentionFrom(t?.schedule, t?.template?.name);
}, { immediate: true });


// ---- prefill helpers ----
function makeLocalSchemaByName(name: string) {
    if (name === 'Rsync Task') return new RsyncTaskTemplate().parameterSchema;
    if (name === 'Cloud Sync Task') return new CloudSyncTaskTemplate().parameterSchema;
    if (name === 'ZFS Replication Task') return new ZFSReplicationTaskTemplate().parameterSchema;
    if (name === 'Automated Snapshot Task') return new AutomatedSnapshotTaskTemplate().parameterSchema;
    if (name === 'Scrub Task') return new ScrubTaskTemplate().parameterSchema;
    if (name === 'SMART Test') return new SmartTestTemplate().parameterSchema;
    if (name === 'Custom Task') return new CustomTaskTemplate().parameterSchema;
    return null;
}

function hydrateSchemaWithRaw(schema: any, raw: any) {
    if (!schema || !raw) return schema;
    if ('value' in raw && raw.value !== undefined) schema.value = raw.value;
    if (Array.isArray(raw.children) && Array.isArray(schema.children)) {
        for (const rawChild of raw.children) {
            const target = schema.children.find((c: any) => c.key === rawChild.key);
            if (target) hydrateSchemaWithRaw(target, rawChild);
        }
    }
    return schema;
}

function prefillFromTask(task: any) {
    if (!task) return;
    newTaskName.value = task.name;
    const found = taskTemplates.find((t: any) => t.name === task.template?.name);
    if (found) selectedTemplate.value = found;
    const localSchema = makeLocalSchemaByName(task.template?.name);
    parameters.value = localSchema ? hydrateSchemaWithRaw(localSchema, task.parameters) : task.parameters;
    notesTask.value = task.notes ?? '';
    paramInputKey.value++;
}

const canPrefill = computed(() => !!originalTask.value && allowedTemplates.value.length > 0);

watch(canPrefill, async (ok) => {
    if (!ok) return;
    await nextTick();
    prefillFromTask(originalTask.value);   // uses name, template, parameters
}, { immediate: true });

// ---- validation ----
function clearAllErrors() {
    errorList.value = [];
    newTaskNameErrorTag.value = false;
    parameterInputComponent.value?.clearTaskParamErrorTags?.();
}

// name uniqueness check
function doesTaskNameExist(name: string): boolean {
    const currentName = originalTask.value?.name;
    return taskInstances.value.some((task: any) =>
        task.name === name && (!isEditMode.value || task.name !== currentName)
    );
}

async function validateTaskName() {
    if (newTaskName.value === '') {
        errorList.value.push('Task name cannot be empty.');
        newTaskNameErrorTag.value = true;
    } else if (!/^[a-zA-Z0-9_ ]+$/.test(newTaskName.value)) {
        errorList.value.push('Task name can only contain letters, numbers, spaces, and underscores.');
        newTaskNameErrorTag.value = true;
    } else if (doesTaskNameExist(newTaskName.value)) {
        errorList.value.push('Task already exists with this name.');
        newTaskNameErrorTag.value = true;
    }
}

async function validateComponentParams() {
    clearAllErrors();
    // Parameter components reset the shared error list when they validate, so they must
    // run first — otherwise they wipe the task name errors and the save proceeds anyway.
    await parameterInputComponent.value?.validation?.();
    await validateTaskName();
    if (errorList.value.length > 0) {
        pushNotification(new Notification('Task Save Failed', `Task submission has errors:\n- ${errorList.value.join('\n- ')}`, 'error', 6000));
        return false;
    }
    return true;
}

// ---- save builders ----
function templateFromSelection() {
    const n = selectedTemplate.value?.name;
    if (n === 'ZFS Replication Task') return new ZFSReplicationTaskTemplate();
    if (n === 'Automated Snapshot Task') return new AutomatedSnapshotTaskTemplate();
    if (n === 'Rsync Task') return new RsyncTaskTemplate();
    if (n === 'Scrub Task') return new ScrubTaskTemplate();
    if (n === 'SMART Test') return new SmartTestTemplate();
    if (n === 'Cloud Sync Task') return new CloudSyncTaskTemplate();
    if (n === 'Custom Task') return new CustomTaskTemplate();
    return undefined as any;
}

function sanitizeName(n: string) {
    let s = n.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
    if (s.startsWith('_')) s = 'task' + s;
    return s;
}

function buildTask(): TaskInstance | null {
    const tpl = templateFromSelection();
    if (!tpl) return null;
    const notes = notesTask.value || '';
    const schedule = toModelSchedule(uiSchedule.value);
    const inst = new TaskInstance(sanitizeName(newTaskName.value), tpl, parameters.value, schedule, notes);
    return inst;
}

// ---- dirty tracking ----
function jsonStable(v: any) { try { return JSON.stringify(v); } catch { return String(v); } }

// Parameter components keep their form state internally and only publish to `parameters`
// on a successful validate, so ask the active one directly instead of diffing stale params.
function paramComponentDirty(): boolean {
    try { return (parameterInputComponent.value as any)?.hasChanges?.() === true; }
    catch { return false; }
}

const isDirty = computed(() => {
    if (!originalTask.value) return true; // creating
    const candidate = buildTask();
    if (!candidate) return false;
    const a = originalTask.value;
    return (
        a.name !== candidate.name ||
        a.template?.name !== candidate.template?.name ||
        paramComponentDirty() ||
        jsonStable(a.parameters) !== jsonStable(candidate.parameters) ||
        jsonStable(a.schedule) !== jsonStable(candidate.schedule) ||
        (a.notes || '') !== (candidate.notes || '')
    );
});

// ---- draft autosave ----
const AUTOSAVE_INTERVAL_MS = 2000;
let autosaveTimer: number | undefined;

function snapshotForm() {
    return {
        name: newTaskName.value,
        templateName: selectedTemplate.value?.name ?? '',
        parameters: parameters.value ? JSON.parse(JSON.stringify(parameters.value)) : null,
        notes: notesTask.value,
        schedule: uiSchedule.value ? JSON.parse(JSON.stringify(uiSchedule.value)) : null,
        keepLocal: keepLocal.value,
        keepBackup: keepBackup.value,
    };
}

function autosaveDraft() {
    if (isEditMode.value) return;
    // Nothing worth resuming yet — don't leave a draft that triggers the resume prompt.
    if (!selectedTemplate.value && !newTaskName.value.trim()) return;
    // Parameter components own their form state; ask the active one to publish it first.
    if (parameterInputComponent.value && parameterInputComponent.value.syncParams?.() === false) return;
    saveDraft(snapshotForm());
}

function startAutosave() {
    if (isEditMode.value || autosaveTimer !== undefined) return;
    autosaveTimer = window.setInterval(autosaveDraft, AUTOSAVE_INTERVAL_MS);
    window.addEventListener('pagehide', autosaveDraft);
}

function stopAutosave() {
    if (autosaveTimer !== undefined) {
        window.clearInterval(autosaveTimer);
        autosaveTimer = undefined;
    }
    window.removeEventListener('pagehide', autosaveDraft);
}

onActivated(startAutosave);
onDeactivated(stopAutosave);
onUnmounted(stopAutosave);

// ---- navigation ----
function goBack() {
    // Discarding the task also discards its draft
    stopAutosave();
    clearSavedDraft();
    router.push({ name: 'SimpleTasks' });
}

function handleOpenWireShield() {
    // Snapshot form state to localStorage before jumping to WireShield
    parameterInputComponent.value?.syncParams?.();
    saveDraft(snapshotForm());
    markDraftSession();

    logToClient('scheduler:vpn_tunnel_open', {
        task: newTaskName.value,
        template: selectedTemplate.value?.name ?? '',
        origin: 'simple-view',
    }, 'info', 'Opening WireShield to connect an off-site server for this task');

    const back = `${schedulerModulePath()}#/simple`;
    const query = `from=scheduler&return=${encodeURIComponent(back)}`;
    const cockpit = (window as any).cockpit;
    if (cockpit?.jump) {
        cockpit.jump(`/wireshield#/simple?${query}`);
    } else {
        window.open(`/cockpit/@localhost/wireshield/index.html#/simple?${query}`, '_blank');
    }
}

// ---- actions ----
async function saveAll() {
    if (!(await validateComponentParams())) return;
    const built = buildTask();
    if (!built) return;

    const mode = isEditMode.value ? 'update' : 'create';
    const startedAt = Date.now();

    try {
        adding.value = true; loading.value = true;

        if (isEditMode.value) {
            const old = originalTask.value!;
            const nameChanged = old.name !== built.name;
            const templateChanged = old.template?.name !== built.template?.name;

            if (nameChanged || templateChanged) {
                await myScheduler.updateTaskInstance(built, {
                    oldName: originalName.value ?? old.name,
                    oldTemplateName: old.template?.name,
                });
            } else {
                await (myScheduler as any).updateTaskInstance(built);
            }

            // keep these after either path
            await (myScheduler as any).updateSchedule(built);
            await (myScheduler as any).updateTaskNotes?.(built);
            await myScheduler.loadTaskInstances();
            logTaskEvent('scheduler:task_update', built, {
                previousName: originalName.value,
                renamed: nameChanged,
                templateChanged,
                durationMs: Date.now() - startedAt,
                origin: 'simple-view',
            });
            pushNotification(new Notification('Task Updated', 'Your task changes were saved.', 'success', 6000));
        } else {
            await myScheduler.registerTaskInstance(built);
            await myScheduler.loadTaskInstances();
            logTaskEvent('scheduler:task_create', built, {
                durationMs: Date.now() - startedAt,
                origin: 'simple-view',
            });
            pushNotification(new Notification('Task Created', 'Your task was created and scheduled.', 'success', 6000));
        }

        // Clear any leftover draft/vpnHost so router guard doesn't redirect back
        stopAutosave();
        clearSavedDraft();
        router.push({ name: 'SimpleTasks' });
    } catch (e: any) {
        logTaskEvent(`scheduler:task_${mode}.error`, built, {
            durationMs: Date.now() - startedAt,
            origin: 'simple-view',
            error: String(e?.message ?? e),
        }, 'error');
        pushNotification(new Notification('Save Failed', String(e?.message ?? e), 'error', 6000));
    } finally { adding.value = false; loading.value = false; }
}


provide('new-task', newTask);
provide('parameters', parameters);
provide('errors', errorList);
</script>