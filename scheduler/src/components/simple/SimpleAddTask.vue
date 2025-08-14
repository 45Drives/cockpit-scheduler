<template>
    <CardContainer class="overflow-y-auto min-h-full w-full ">
        <div class="h-full bg-accent text-default rounded-md border border-default p-2">
            <div name="task-name">
                <div class="flex flex-row justify-between items-center">
                    <div class="flex flex-row justify-between items-center">
                        <label class="block text-sm leading-6 text-default">Task Name</label>
                        <InfoTile class="ml-1"
                            title="Name can have letters, numbers, and underscores. Spaces will convert to underscores upon save." />
                    </div>
                    <ExclamationCircleIcon v-if="newTaskNameErrorTag" class="mt-1 w-5 h-5 text-danger" />
                </div>
                <input type="text" v-model="newTaskName" :class="[
                    'my-1 block w-full input-textlike text-default',
                    newTaskNameErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]" placeholder="New Task"
                    title="Name can have letters, numbers, and underscores. Spaces will convert to underscores upon save." />
            </div>
            <div name="task-template" v-if="allowedTemplates.length > 0">
                <label for="task-template-selection" class="block text-sm leading-6 text-default">Task
                    Template</label>
                <select id="task-template-selection" v-model="selectedTemplate" name="task-template-selection"
                    class="text-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                    <option :value="undefined">Select Type of Task to Add</option>
                    <option v-for="template, idx in allowedTemplates" :key="idx" :value="template">{{ displayName(template) }}
                    </option>
                </select>
            </div>
            <div v-if="selectedTemplate">
                <ParameterInput ref="parameterInputComponent" :selectedTemplate="selectedTemplate" :simple="true" />
            </div>
        </div>
        <!-- Footer Buttons -->
        <template #footer>
            <div class="button-group-row justify-start w-full">
                <button @click="goBack" class="btn btn-secondary h-20 w-40">Back</button>

                <!-- <div class="button-group-row justify-end gap-3">
                    <button class="btn btn-secondary px-4 py-2" :disabled="!selectedBackup"
                        @click="deselectAll">Deselect All</button>
                    <button class="btn btn-secondary px-4 py-2" :disabled="!selectedBackup" @click="selectAll">Select
                        All</button>
                    <button class="btn btn-secondary px-4 py-2" :disabled="!selectedBackup"
                        @click="openSelectedBackupFolder">
                        Open Folder
                    </button>
                    <button class="btn btn-danger px-4 py-2" :disabled="multiSelectedUuids.length === 0"
                        @click="deleteSelectedBackups">
                        Delete Selected Backups
                    </button>
                    <button class="btn btn-primary px-4 py-2" :disabled="!selectedBackup || selectedFilesCount === 0"
                        @click="restoreSelected">
                        Restore Selected Files
                    </button>
                </div> -->
            </div>
        </template>
    </CardContainer>

</template>
<script setup lang="ts">
import { computed, inject, provide, ref, Ref } from 'vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import InfoTile from '../common/InfoTile.vue';
import { TaskInstance, ZFSReplicationTaskTemplate, TaskSchedule, AutomatedSnapshotTaskTemplate, RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate, CloudSyncTaskTemplate, CustomTaskTemplate } from '../../models/Tasks';
import { pushNotification, Notification, CardContainer } from '@45drives/houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, schedulerInjectionKey, taskTemplatesInjectionKey, taskInstancesInjectionKey } from '../../keys/injection-keys';
import { useRouter } from 'vue-router';

const router = useRouter();
function goBack() {
    router.push({ name: 'SimpleTasks' });
}
const taskInstances = injectWithCheck(taskInstancesInjectionKey, "taskInstances not provided!");
const taskTemplates = injectWithCheck(taskTemplatesInjectionKey, "taskTemplates not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

const emit = defineEmits(['manageSchedule']);

const newTask = ref<TaskInstanceType>();

const showTaskWizard = inject<Ref<boolean>>('show-task-wizard')!;
const adding = ref(false);

const errorList = ref<string[]>([]);
const newTaskName = ref('');
const newTaskNameErrorTag = ref(false);
const selectedTemplate = ref<TaskTemplateType>();
const parameterInputComponent = ref();
const parameters = ref();
const notesTask = ref('');

const simpleAllowed = [
    'Rsync Task',
    'Cloud Sync Task',
    'ZFS Replication Task',
    'Automated Snapshot Task',
    'Scrub Task',
];

const allowedTemplates = computed(() => {
    const orderMap = Object.fromEntries(simpleAllowed.map((name, i) => [name, i]));
    return taskTemplates
        .filter(t => simpleAllowed.includes(t.name))
        .sort((a, b) => orderMap[a.name] - orderMap[b.name]);
});

const nameOverrides: Record<string, string> = {
    'ZFS Replication Task': 'ZFS → ZFS Backup',
    'Automated Snapshot Task': 'Automatic Snapshots',
    'Scrub Task': 'ZFS Scrub',
    'Rsync Task': 'Server-to-Server Backup',
    'Cloud Sync Task': 'Cloud Backup'
};

const displayName = (template: TaskTemplateType) => {
    return nameOverrides[template.name] || template.name;
};


const cancelingAddTask = ref(false);
const showCloseConfirmation = ref(false);
const closeConfirmationComponent = ref();
async function loadCloseConfirmationComponent() {
    const module = await import('../common/ConfirmationDialog.vue');
    closeConfirmationComponent.value = module.default;
}

const closeBtn = async () => {
    if (!selectedTemplate.value) {
        // closeModal();
    } else {
        await loadCloseConfirmationComponent();
        showCloseConfirmation.value = true;
    }
};

const updateShowCloseConfirmation = (newVal) => {
    showCloseConfirmation.value = newVal;
}

const confirmCancel: ConfirmationCallback = async () => {
    // closeModal();
}

const cancelCancel: ConfirmationCallback = async () => {
    updateShowCloseConfirmation(false);
}

// Validation
function clearAllErrors() {
    errorList.value = [];
    newTaskNameErrorTag.value = false;
    parameterInputComponent.value.clearTaskParamErrorTags();
}

function doesTaskNameExist(name: string): boolean {
    return taskInstances.value.some(task => task.name === name);
}

async function validateTaskName() {
    if (newTaskName.value === '') {
        errorList.value.push("Task name cannot be empty.");
        newTaskNameErrorTag.value = true;
    } else if (!/^[a-zA-Z0-9_ ]+$/.test(newTaskName.value)) {
        // Checks if the task name contains only letters, digits, underscores, and spaces
        errorList.value.push("Task name can only contain letters, numbers, spaces, and underscores.");
        newTaskNameErrorTag.value = true;
    } else if (doesTaskNameExist(newTaskName.value)) {
        errorList.value.push("Task already exists with this name.");
        newTaskNameErrorTag.value = true;
    }
}

async function validateComponentParams() {
    clearAllErrors();
    await validateTaskName();
    await parameterInputComponent.value.validation();
    if (errorList.value.length > 0) {
        pushNotification(new Notification('Task Save Failed', `Task submission has errors: \n- ${errorList.value.join("\n- ")}`, 'error', 6000));
        return false;
    } else {
        return true;
    }
}

// Schedule Prompt
const showSchedulePrompt = ref(false);
const isStandaloneTask = ref(false);

const confirmationComponent = ref();
const loadConfirmationComponent = async () => {
    const module = await import('../common/ConfirmationDialog.vue');
    confirmationComponent.value = module.default;
}

async function showSchedulePromptDialog() {
    await loadConfirmationComponent();

    showSchedulePrompt.value = true;
    // console.log('Showing confirmation dialog...');
}

const makeScheduleLater: ConfirmationCallback = async () => {
    adding.value = true;
    isStandaloneTask.value = true;
    console.log('Make Schedule Later. isStandalone Task:', isStandaloneTask.value);
    await saveTask();
    updateShowSchedulePrompt(false);
    // closeModal();
    adding.value = true;
}

const makeScheduleNow: ConfirmationCallback = async () => {
    isStandaloneTask.value = false;
    console.log('Make Schedule Now. isStandalone:', isStandaloneTask.value);
    await saveTask();
    emit('manageSchedule', newTask.value);
    updateShowSchedulePrompt(false);
    // showScheduleWizardComponent();
    // closeModal();
}

const updateShowSchedulePrompt = (newVal) => {
    showSchedulePrompt.value = newVal;
}

async function saveTask() {
    console.log('saveTask triggered');
    const template = ref();
    if (selectedTemplate.value?.name == 'ZFS Replication Task') {
        template.value = new ZFSReplicationTaskTemplate();
    } else if (selectedTemplate.value?.name == 'Automated Snapshot Task') {
        template.value = new AutomatedSnapshotTaskTemplate();
    } else if (selectedTemplate.value?.name == 'Rsync Task') {
        template.value = new RsyncTaskTemplate();
    } else if (selectedTemplate.value?.name == "Scrub Task") {
        template.value = new ScrubTaskTemplate();
    } else if (selectedTemplate.value?.name == "SMART Test") {
        template.value = new SmartTestTemplate();
    } else if (selectedTemplate.value?.name == "Cloud Sync Task") {
        template.value = new CloudSyncTaskTemplate();
    } else if (selectedTemplate.value?.name == "Custom Task") {
        template.value = new CustomTaskTemplate();
    }

    let sanitizedName = newTaskName.value.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
    if (sanitizedName.startsWith('_')) {
        sanitizedName = 'task' + sanitizedName;
    }
    //  console.log('sanitizedName:', sanitizedName);

    console.log("template: ", template, " parameters ", parameters)
    // const notes = notesTask.value ? notesTask.value : '  '; // Assign notesTask value or two spaces if empty
    const notes = notesTask.value ? notesTask.value : '';  // Ensure notes is always a string
    if (isStandaloneTask.value) {
        const schedule = new TaskSchedule(false, []);
        const task = new TaskInstance(sanitizedName, template.value, parameters.value, schedule, notes || '');
        //  console.log('task (no schedule):', task);
        console.log("Saving task with notes:", JSON.stringify(notes));
        console.log("Task instance:", JSON.stringify(task));

        await myScheduler.registerTaskInstance(task);
        pushNotification(new Notification('Task Save Successful', `Task has been saved.`, 'success', 6000));
        loading.value = true;
        await myScheduler.loadTaskInstances();
        loading.value = false;
    } else {
        const schedule = new TaskSchedule(true, []);
        const task = new TaskInstance(sanitizedName, template.value, parameters.value, schedule, notes);
        //  console.log('task (for scheduling):', task);
        console.log("Saving task with notes:", JSON.stringify(notes));
        console.log("Task instance:", JSON.stringify(task));

        newTask.value = task;
    }
}

async function addTaskBtn() {
    if (await validateComponentParams()) {
        showSchedulePromptDialog();
    }
}


provide('new-task', newTask);
provide('parameters', parameters);
provide('errors', errorList);
provide('show-schedule-prompt', showSchedulePrompt);
provide('is-standalone-task', isStandaloneTask);
provide('show-task-wizard', showTaskWizard);

</script>
