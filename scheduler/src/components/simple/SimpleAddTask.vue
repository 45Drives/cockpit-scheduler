<template>
    <div class="h-full w-full overflow-hidden">
        <CardContainer class="min-h-0 h-full overflow-y-auto">
            <div class="grid grid-cols-2 gap-4 min-h-0 h-full">
                <div class="h-full bg-accent text-default rounded-md border border-default p-2 col-span-1">
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
                        <select id="task-template-selection" v-model="selectedTemplate" name="task-template-selection"
                            class="text-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                            <option :value="undefined">Select Type of Task to Add</option>
                            <option v-for="template, idx in allowedTemplates" :key="idx" :value="template">{{
                                displayName(template) }}</option>
                        </select>
                    </div>
                    <!-- Parameters -->
                    <div v-if="selectedTemplate">
                        <ParameterInput :key="paramInputKey" ref="parameterInputComponent"
                            :selectedTemplate="selectedTemplate" :simple="true" :task="originalTask || undefined" />
                    </div>
                </div>

                <div class="col-span-1">
                    <SimpleCalendar :title="'Schedule Task'" v-model:taskSchedule="uiSchedule" />
                </div>
            </div>


            <!-- Footer: single action row -->
            <template #footer>
                <div class="button-group-row justify-between w-full">
                    <button @click="goBack" class="btn btn-secondary h-20 w-40">Back</button>
                    <div class="">
                        <button :disabled="!isDirty || adding" @click="saveAll" class="btn btn-primary h-20 w-48">
                            {{ isEditMode ? (adding ? 'Saving…' : 'Save Changes') : (adding ? 'Creating…' : 'Create Task') }}
                        </button>
                    </div>
                </div>
            </template>
        </CardContainer>
    </div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, provide, ref, watch } from 'vue';
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
import { injectWithCheck } from '../../composables/utility';
import { loadingInjectionKey, schedulerInjectionKey, taskTemplatesInjectionKey, taskInstancesInjectionKey } from '../../keys/injection-keys';

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
const newTaskName = ref('');
const newTaskNameErrorTag = ref(false);
const selectedTemplate = ref<TaskTemplateType>();
const parameterInputComponent = ref();
const parameters = ref<any>();
const notesTask = ref('');
const paramInputKey = ref(0);


// schedule bridge init
const uiSchedule = ref<UITaskSchedule>(toUISchedule(originalTask.value?.schedule));

// helper used by watcher
function resetForm() {
    newTaskName.value = '';
    selectedTemplate.value = undefined;
    parameters.value = undefined;
    notesTask.value = '';
    uiSchedule.value = toUISchedule(null);
    paramInputKey.value++; // reset ParameterInput
}

watch(isEditMode, (edit) => {
    if (!edit) resetForm();
}, { immediate: true });

// ---- deps ----
const router = useRouter();
const taskInstances = injectWithCheck(taskInstancesInjectionKey, 'taskInstances not provided!');
const taskTemplates = injectWithCheck(taskTemplatesInjectionKey, 'taskTemplates not provided!');
const loading = injectWithCheck(loadingInjectionKey, 'loading not provided!');
const myScheduler = injectWithCheck(schedulerInjectionKey, 'scheduler not provided!');

const simpleAllowed = ['Rsync Task', 'Cloud Sync Task'];
const allowedTemplates = computed(() => {
    const orderMap = Object.fromEntries(simpleAllowed.map((n, i) => [n, i]));
    return taskTemplates
        .filter((t: any) => simpleAllowed.includes(t.name))
        .sort((a: any, b: any) => orderMap[a.name] - orderMap[b.name]);
});

const nameOverrides: Record<string, string> = {
    'ZFS Replication Task': 'ZFS → ZFS Backup',
    'Automated Snapshot Task': 'Automatic Snapshots',
    'Scrub Task': 'ZFS Scrub',
    'Rsync Task': 'Server-to-Server Backup',
    'Cloud Sync Task': 'Cloud Backup',
};

const displayName = (template: TaskTemplateType) => nameOverrides[template.name] || template.name;

// ---- schedule bridge (UI <-> model) ----
function toUISchedule(model?: ModelTaskSchedule | null): UITaskSchedule {
    const now = new Date();
    if (!model || !Array.isArray(model.intervals) || model.intervals.length === 0) {
        return { repeatFrequency: 'day', startDate: now } as UITaskSchedule;
    }
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

    return new ModelTaskSchedule(true, [baseInterval]);
}

// schedule bridge watch
watch(() => originalTask.value, (t) => {
    uiSchedule.value = toUISchedule(t?.schedule);
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
    await validateTaskName();
    await parameterInputComponent.value?.validation?.();
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
const isDirty = computed(() => {
    if (!originalTask.value) return true; // creating
    const candidate = buildTask();
    if (!candidate) return false;
    const a = originalTask.value;
    return (
        a.name !== candidate.name ||
        a.template?.name !== candidate.template?.name ||
        jsonStable(a.parameters) !== jsonStable(candidate.parameters) ||
        jsonStable(a.schedule) !== jsonStable(candidate.schedule) ||
        (a.notes || '') !== (candidate.notes || '')
    );
});

// ---- navigation ----
function goBack() { router.push({ name: 'SimpleTasks' }); }

// ---- actions ----
async function saveAll() {
    if (!(await validateComponentParams())) return;
    const built = buildTask();
    if (!built) return;

    try {
        adding.value = true; loading.value = true;

        if (isEditMode.value) {
            const old = originalTask.value!;
            const nameChanged = old.name !== built.name;
            const templateChanged = old.template?.name !== built.template?.name;

            if (nameChanged || templateChanged) {
                // full replace to avoid duplicate systemd units
                await myScheduler.unregisterTaskInstance(old);
                await myScheduler.registerTaskInstance(built);
            } else {
                await (myScheduler as any).updateTaskInstance(built);
            }

            // keep these after either path
            await (myScheduler as any).updateSchedule(built);
            await (myScheduler as any).updateTaskNotes?.(built);
            await myScheduler.loadTaskInstances();
            pushNotification(new Notification('Task Updated', 'Your task changes were saved.', 'success', 6000));
        } else {
            await myScheduler.registerTaskInstance(built);
            await myScheduler.loadTaskInstances();
            pushNotification(new Notification('Task Created', 'Your task was created and scheduled.', 'success', 6000));
        }

        router.push({ name: 'SimpleTasks' });
    } catch (e: any) {
        pushNotification(new Notification('Save Failed', String(e?.message ?? e), 'error', 8000));
    } finally { adding.value = false; loading.value = false; }
}


// ---- provide for children that read these symbols ----
provide('new-task', newTask);
provide('parameters', parameters);
provide('errors', errorList);
</script>