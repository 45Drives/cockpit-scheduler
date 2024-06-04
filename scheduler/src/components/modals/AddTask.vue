<template>
    <Modal @close="closeModal" :isOpen="showTaskWizard" :margin-top="'mt-10'" :width="'w-3/5'" :min-width="'min-w-3/5'" :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="false">
        <template v-slot:title>
            Add New Task
        </template>
        <template v-slot:content>
            <div>
                <div name="task-name">
                    <div class="flex flex-row justify-between items-center">
                        <div class="flex flex-row justify-between items-center">
                            <label class="block text-sm leading-6 text-default">Task Name</label>
                            <InfoTile class="ml-1" title="Name can have letters, numbers, and underscores. Spaces will convert to underscores upon save." />
                        </div>
                        <ExclamationCircleIcon v-if="newTaskNameErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                    </div>
                    <input v-if="newTaskNameErrorTag" type="text" v-model="newTaskName" class="my-1 block w-full input-textlike bg-default text-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="New Task" title="Name can have letters, numbers, and underscores. Spaces will convert to underscores upon save."/> 
                    <input v-else type="text" v-model="newTaskName" class="my-1 block w-full input-textlike bg-default text-default" placeholder="New Task" title="Name can have letters, numbers, and underscores. Spaces will convert to underscores upon save."/> 
                </div>
                <div name="task-template" v-if="taskTemplates.length > 0">
					<label for="task-template-selection" class="block text-sm leading-6 text-default">Task Template</label>
					<select id="task-template-selection" v-model="selectedTemplate" name="task-template-selection" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option :value="undefined">Select Type of Task to Add</option>
                        <option v-for="template, idx in taskTemplates" :key="idx" :value="template">{{ template.name }}</option>
					</select>
				</div>
                <div v-if="selectedTemplate">
                    <ParameterInput ref="parameterInputComponent" :selectedTemplate="selectedTemplate"/>
                </div>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
				<div class="button-group-row w-full justify-between">
                    <div class="button-group-row">
                        <button @click.stop="closeModal" id="close-add-task-btn" name="close-add-task-btn" class="mt-1 btn btn-danger h-fit w-full">Close</button>
                    </div>
                    <div class="button-group-row">
                        <button disabled v-if="adding" id="adding-task-btn" type="button" class="btn btn-primary h-fit w-full">
                            <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                            </svg>
                            Adding...
                        </button>
                        <button v-else-if="!adding && selectedTemplate" id="add-task-btn" class="btn btn-primary h-fit w-full" @click="addTaskBtn">Add Task</button>
                        <button v-else disabled id="add-task-btn-error" class="btn btn-primary h-fit w-full" @click="addTaskBtn">Add Task</button>
                    </div>
				</div>
			</div>
        </template>
    </Modal>

    <div v-if="showSchedulePrompt">
        <component :is="confirmationComponent" @close="updateShowSchedulePrompt" :showFlag="showSchedulePrompt" :title="'Schedule Task'" :message="'Do you wish to schedule this task now?'" :confirmYes="makeScheduleNow" :confirmNo="makeScheduleLater" :operation="'adding'" :operating="adding"/>
    </div>

    <div v-if="showScheduleWizard">
        <component :is="scheduleWizardComponent" @close="updateShowScheduleWizardComponent" :mode="'new'" :task="newTask"/>
    </div>
    
</template>
<script setup lang="ts">
import { inject, provide, ref, Ref, watch } from 'vue';
import Modal from '../common/Modal.vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import InfoTile from '../common/InfoTile.vue';
import { TaskInstance, ZFSReplicationTaskTemplate, TaskSchedule, AutomatedSnapshotTaskTemplate, RsyncTaskTemplate } from '../../models/Tasks';
import { pushNotification, Notification } from 'houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, schedulerInjectionKey, taskTemplatesInjectionKey, taskInstancesInjectionKey } from '../../keys/injection-keys';

const taskInstances = injectWithCheck(taskInstancesInjectionKey, "taskInstances not provided!");
const taskTemplates = injectWithCheck(taskTemplatesInjectionKey, "taskTemplates not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

const emit = defineEmits(['close']);

const newTask = ref<TaskInstanceType>();

const showTaskWizard = inject<Ref<boolean>>('show-task-wizard')!;
const adding = ref(false);

const errorList = ref<string[]>([]);
const newTaskName = ref('');
const newTaskNameErrorTag = ref(false);
const selectedTemplate = ref<TaskTemplateType>();
const parameterInputComponent = ref();
const parameters = ref();

const closeModal = () => {
    showTaskWizard.value = false;
    emit('close');
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
    parameterInputComponent.value.validation();
    if (errorList.value.length > 0) {
       pushNotification(new Notification('Task Save Failed', `Task submission has errors: \n- ${errorList.value.join("\n- ")}`, 'error', 8000));
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
    console.log('Showing confirmation dialog...');
}

const makeScheduleLater : ConfirmationCallback = async () => {
    adding.value = true;
    isStandaloneTask.value = true;
    console.log('Make Schedule Later. isStandalone Task:', isStandaloneTask.value);
    await saveTask();
    updateShowSchedulePrompt(false);
    closeModal();
    adding.value = true;
}

const makeScheduleNow : ConfirmationCallback = async () => {
    isStandaloneTask.value = false;
    console.log('Make Schedule Now. isStandalone:', isStandaloneTask.value);
    await saveTask();
    updateShowSchedulePrompt(false);
    showScheduleWizardComponent();
}

const updateShowSchedulePrompt = (newVal) => {
    showSchedulePrompt.value = newVal;
}


// Show Schedule Wizard
const showScheduleWizard = ref(false);

const scheduleWizardComponent = ref();
const loadScheduleWizardComponent = async () => {
    console.log('loadScheduleWizard triggered');
    const module = await import('./ManageSchedule.vue');
    scheduleWizardComponent.value = module.default;
}

async function showScheduleWizardComponent() {
    console.log('Attempting to load Schedule Wizard Component...');
    try {
        await loadScheduleWizardComponent();
        console.log('addTask: setting showScheduleWizard to true.');
        showScheduleWizard.value = true;
    } catch (error) {
        console.error('Failed to load Schedule Wizard Component:', error);
    }
}

const updateShowScheduleWizardComponent = (newVal) => {
    console.log('updateShowScheduleWizard triggered');
    showScheduleWizard.value = newVal;
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
    }

    let sanitizedName = newTaskName.value.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
    if (sanitizedName.startsWith('_')) {
        sanitizedName = 'task' + sanitizedName;
    }
    console.log('sanitizedName:', sanitizedName);


    if (isStandaloneTask.value) {
        const schedule = new TaskSchedule(false, []);
        const task = new TaskInstance(sanitizedName, template.value, parameters.value, schedule);
        console.log('task (no schedule):', task);

        await myScheduler.registerTaskInstance(task);
        pushNotification(new Notification('Task Save Successful', `Task has been saved.`, 'success', 8000));
        loading.value = true;
        await myScheduler.loadTaskInstances();
        loading.value = false;
    } else {
        const schedule = new TaskSchedule(true, []);
        const task = new TaskInstance(sanitizedName, template.value, parameters.value, schedule);
        console.log('task (for scheduling):', task);

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
provide('show-schedule-wizard', showScheduleWizard);
</script>

