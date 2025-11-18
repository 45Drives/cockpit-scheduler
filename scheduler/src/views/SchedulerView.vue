<template>
    <div>
        <div class="flex flex-row justify-between sm:flex sm:items-center">
            <div class="text-left">
                <p class="mt-4 text-medium text-default">
                    All tasks currently configured on the system are listed here.
                </p>
            </div>
            <div class="flex flex-row justify-between">
                <div class="px-3">
                    <label class="block text-medium font-medium leading-6 text-default">Filter By Name</label>
                    <input type="text" @keydown.enter="" v-model="searchItem"
                        class="text-default bg-default block w-fit input-textlike sm:text-sm" placeholder="Search..." />
                </div>
                <div class="mt-5 py-0.5 px-3">
                    <button @click="refreshBtn()" class="btn btn-secondary">
                        <ArrowPathIcon class="w-5 h-5 m-0.5" />
                    </button>
                </div>
                <div class="mt-5 py-0.5 px-3">
                    <button @click="addTaskBtn()" class="btn btn-primary">Add New Task</button>
                </div>
                <!-- <div class="mt-5 py-0.5 px-3">
                    <button @click="showNewScheduleComponent()" class="btn btn-primary">CALENDAR</button>
                </div> -->
            </div>
        </div>

        <div class="my-4 flow-root">
            <div class="-mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
                <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8 overflow-x-auto">
                    <div v-if="loading" class="flex items-center justify-center">
                        <CustomLoadingSpinner :width="'w-32'" :height="'h-32'" :baseColor="'text-gray-200'"
                            :fillColor="'fill-gray-500'" />
                    </div>
                    <div v-else-if="taskInstances.length === 0"
                        class="min-w-full min-h-full items-center text-center bg-well">
                        <h2>No Tasks Found</h2>
                    </div>
                    <div v-else class="relative">
                        <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-default">
                                <thead class="bg-well">
                                    <tr class="border border-default border-collapse grid grid-cols-8 w-full">
                                        <th scope="col"
                                            class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default border-collapse col-span-2">
                                            <button @click="sortBy('name')"
                                                class="flex w-full justify-between whitespace-nowrap">
                                                Name
                                                <BarsArrowDownIcon class="ml-1 aspect-square w-5 h-5 text-muted"
                                                    v-if="sort.field === 'name' && sortMode == 'desc'" />
                                                <BarsArrowUpIcon class="ml-1 aspect-square w-5 h-5 text-muted"
                                                    v-else-if="sort.field === 'name' && sortMode == 'asc'" />
                                                <Bars3Icon class="ml-1 aspect-square w-5 h-5 text-muted" v-else />
                                            </button>
                                        </th>
                                        <th scope="col"
                                            class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default border-collapse col-span-2">
                                            Status
                                        </th>
                                        <th scope="col"
                                            class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default border-collapse col-span-2">
                                            Last Run
                                        </th>
                                        <th scope="col"
                                            class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default border-collapse col-span-1">
                                            Scheduled
                                        </th>
                                        <th scope="col"
                                            class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default border-collapse col-span-1">
                                            Details
                                        </th>
                                    </tr>
                                </thead>
                                <tbody class="bg-accent">
                                    <div v-for="(taskInstance, index) in filteredAndSortedTasks"
                                        :key="taskInstance.name">
                                        <TaskInstanceTableRow :task="taskInstance"
                                            :isExpanded="expandedTaskName === taskInstance.name"
                                            @runTask="(task) => runTaskBtn(taskInstance, index)"
                                            @stopTask="(task) => stopTaskBtn(taskInstance, index)"
                                            @editTask="(task) => editTaskBtn(task)"
                                            @manageSchedule="(task) => manageScheduleBtn(task)"
                                            @removeTask="(task) => removeTaskBtn(task)"
                                            @viewLogs="(task) => viewLogsBtn(task)" @toggleDetails="toggleDetails"
                                            @viewNotes="(task) => viewNotesBtn(task)" ref="taskTableRow"
                                            :attr="taskInstance" />
                                    </div>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div v-if="showTaskWizard">
        <component :is="addTaskComponent" :id-key="'add-task-modal'" @manageSchedule="addScheduleHandler" />
    </div>

    <div v-if="showEditTaskWizard">
        <component :is="editTaskComponent" :id-key="'edit-task-modal'" :task="selectedTask!" />
    </div>

    <div v-if="showThisScheduleWizard">
        <component :is="scheduleWizardComponent" @close="updateShowThisScheduleWizardComponent" :task="selectedTask"
            :mode="scheduleMode" />
    </div>

    <!-- <Modal :show="showNewScheduleWizard" v-on:click-outside="showNewScheduleComponent">
        <CalendarConfig title="New Schedule" :show="showNewScheduleWizard" @close="showNewScheduleComponent"/>
    </Modal> -->

    <div v-if="showRunNowPrompt">
        <component :is="runNowDialog" @close="updateShowRunNowPrompt" :showFlag="showRunNowPrompt" :title="'Run Task'"
            :message="'Do you wish to run this task now?'" :confirmYes="runNowYes" :confirmNo="runNowNo"
            :operating="running" :operation="'starting'" />
    </div>

    <div v-if="showStopNowPrompt">
        <component :is="stopNowDialog" @close="updateShowStopNowPrompt" :showFlag="showStopNowPrompt" :title="'Stop Task'"
            :message="'Do you wish to stop this task now?'" :confirmYes="stopNowYes" :confirmNo="stopNowNo"
            :operating="stopping" :operation="'stopping'" />
    </div>


    <div v-if="showRemoveTaskPrompt">
        <component :is="removeTaskDialog" @close="updateShowRemoveTaskPrompt" :showFlag="showRemoveTaskPrompt"
            :title="'Remove Task'" :message="'Are you sure you want to remove this task?'" :confirmYes="removeTaskYes"
            :confirmNo="removeTaskNo" :operating="removing" :operation="'removing'" />
    </div>

    <div v-if="showNotesPrompt">
        <component :is="viewNotesComponent" :id-key="'view-notes-task-modal'" :task="selectedTask" />
    </div>

    <div v-if="showLogView">
        <component :is="logViewComponent" @close="updateShowLogViewComponent" :task="selectedTask" />
    </div>

</template>

<script setup lang="ts">
import "@45drives/houston-common-css/src/index.css";
import { computed, ref, provide, nextTick } from 'vue';
import { ArrowPathIcon, Bars3Icon, BarsArrowDownIcon, BarsArrowUpIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from "../components/common/CustomLoadingSpinner.vue";
import TaskInstanceTableRow from '../components/table/TaskInstanceTableRow.vue';
import { pushNotification, Notification, CalendarConfig, Modal } from '@45drives/houston-common-ui';
import { loadingInjectionKey, schedulerInjectionKey, taskInstancesInjectionKey, truncateTextInjectionKey } from '../keys/injection-keys';
import { injectWithCheck } from '../composables/utility'
import { TaskInstance } from '../models/Tasks';

const taskInstances = injectWithCheck(taskInstancesInjectionKey, "taskInstances not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
const selectedTask = ref<TaskInstanceType>();
const selectedRowIndex = ref<number | null>(null);
const taskTableRow = ref<Array<typeof TaskInstanceTableRow>>([]);

async function updateStatusAndTime(task: TaskInstanceType, rowIndex: number) {
    const target = taskTableRow.value[rowIndex];
    await target.updateTaskStatus(task);
    await target.fetchLatestLog(task);
}

/* Refresh Display */
async function refreshBtn() {
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;

    await nextTick();

    taskInstances.value.forEach((task, index) => {
        const row = taskTableRow.value[index];
        if (row) {
            row.updateTaskStatus(task);
            row.fetchLatestLog(task);
        }
    });
}

const expandedTaskName = ref(null);
function toggleDetails(taskName) {
    expandedTaskName.value = expandedTaskName.value === taskName ? null : taskName;
}

/* Add New Task */
const showTaskWizard = ref(false);
async function addTaskBtn() {
    await loadAddTaskComponent();
    showTaskWizard.value = true;
}
const addTaskComponent = ref();
async function loadAddTaskComponent() {
    const module = await import('../components/modals/AddTask.vue');
    addTaskComponent.value = module.default;
}


/* Edit Task */
const showEditTaskWizard = ref(false)
async function editTaskBtn(task) {
    selectedTask.value = task;
    await loadEditTaskComponent();
    showEditTaskWizard.value = true;
}
const editTaskComponent = ref();
async function loadEditTaskComponent() {
    const module = await import('../components/modals/EditTask.vue');
    editTaskComponent.value = module.default;
}



/* Generic loading function for Confirmation Dialogs */
async function loadConfirmationDialog(dialogRef) {
    const module = await import('../components/common/ConfirmationDialog.vue');
    dialogRef.value = module.default;
}
/* Task Notes View*/
const showNotesPrompt = ref(false);

async function viewNotesBtn(task){
    selectedTask.value = task;
    console.log("viewNotesBtn triggered with task:", task);
    await loadViewNotesComponent();
    showNotesPrompt.value = true
}

const viewNotesComponent = ref()

async function loadViewNotesComponent(){
    console.log('load ViewNotes Component triggered in scheduler view');

    const module = await import('../components/modals/Notes.vue')
    viewNotesComponent.value = module.default;
}


/* Run Task Now */
const showRunNowPrompt = ref(false);
const runNowDialog = ref();
const running = ref(false);

function runTaskBtn(task, rowIndex: number) {
    selectedTask.value = task;
    selectedRowIndex.value = rowIndex;
    showRunNowDialog();
}
async function showRunNowDialog() {
    await loadConfirmationDialog(runNowDialog);
    showRunNowPrompt.value = true;
}


const updateShowRunNowPrompt = (newVal) => {
    showRunNowPrompt.value = newVal;
}

const runNowNo: ConfirmationCallback = async () => {
    updateShowRunNowPrompt(false);
}


const runNowYes: ConfirmationCallback = async () => {
    if (selectedTask.value == null || selectedRowIndex.value == null) {
        // No selected row; just bail out quietly
        updateShowRunNowPrompt(false);
        return;
    }

    running.value = true;
    const task = selectedTask.value;
    const rowIndex = selectedRowIndex.value;

    pushNotification(
        new Notification('Task Started', `Task ${task.name} has started running.`, 'info', 8000)
    );

    const row = taskTableRow.value[rowIndex];

    // Tell the row to treat the next 60 seconds as a "manual run" window
    row?.markManualRun(60_000);

    // Kick an immediate status/log refresh so the UI flips quickly
    await updateStatusAndTime(task, rowIndex);

    updateShowRunNowPrompt(false);

    try {
        await myScheduler.runTaskNow(task);
        pushNotification(
            new Notification('Task Successful', `Task ${task.name} has successfully completed.`, 'success', 8000)
        );
    } catch (error) {
        pushNotification(
            new Notification('Task Failed', `Task ${task.name} failed to complete.`, 'error', 8000)
        );
    } finally {
        running.value = false;
    }
};


/* Stop Task Now */
const showStopNowPrompt = ref(false);
const stopNowDialog = ref();
const stopping = ref(false);

function stopTaskBtn(task, rowIndex: number) {
    selectedTask.value = task;
    selectedRowIndex.value = rowIndex;
    showStopNowDialog();
}
async function showStopNowDialog() {
    await loadConfirmationDialog(stopNowDialog);
    showStopNowPrompt.value = true;
}


const updateShowStopNowPrompt = (newVal) => {
    showStopNowPrompt.value = newVal;
}

const stopNowNo: ConfirmationCallback = async () => {
    updateShowStopNowPrompt(false);
}


const stopNowYes: ConfirmationCallback = async () => {
    if (selectedTask.value == null || selectedRowIndex.value == null) {
        // No selected row; just bail out quietly
        updateShowStopNowPrompt(false);
        return;
    }

    stopping.value = true;
    const task = selectedTask.value;
    const rowIndex = selectedRowIndex.value;

    pushNotification(
        new Notification('Task Stopping', `Task ${task.name} is stopping.`, 'info', 8000)
    );

    // Kick an immediate status/log refresh so the UI flips quickly
    await updateStatusAndTime(task, rowIndex);

    updateShowStopNowPrompt(false);

    try {
        await myScheduler.stopTaskNow(task);
        pushNotification(
            new Notification('Task Stopped', `Task ${task.name} has successfully been stopped.`, 'success', 8000)
        );
    } catch (error) {
        pushNotification(
            new Notification('Task Stop Failed', `Task ${task.name} failed to stop.`, 'error', 8000)
        );
    } finally {
        stopping.value = false;
    }
};


/* Remove Task */
const showRemoveTaskPrompt = ref(false);
const removeTaskDialog = ref();
const removing = ref(false);

function removeTaskBtn(task) {
    console.log('removeTaskBtn triggered');
    selectedTask.value = task;

    showRemoveTaskDialog();
}
async function showRemoveTaskDialog() {
    await loadConfirmationDialog(removeTaskDialog);
    showRemoveTaskPrompt.value = true;
}
const removeTaskYes: ConfirmationCallback = async () => {
    removing.value = true;
    await myScheduler.unregisterTaskInstance(selectedTask.value!);
    removing.value = false;
    updateShowRemoveTaskPrompt(false);
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;
}
const removeTaskNo: ConfirmationCallback = async () => {
    updateShowRemoveTaskPrompt(false);
}
const updateShowRemoveTaskPrompt = (newVal) => {
    showRemoveTaskPrompt.value = newVal;
}


/* Schedule Management */
const scheduleMode = ref('');
const showThisScheduleWizard = ref(false);
function manageScheduleBtn(task) {
    selectedTask.value = task;
    scheduleMode.value = 'edit';
    showThisScheduleWizardComponent();
}
const scheduleWizardComponent = ref();
const loadScheduleWizardComponent = async () => {
    console.log('loadScheduleWizard triggered');
    const module = await import('../components/modals/ManageSchedule.vue');
    scheduleWizardComponent.value = module.default;
}

async function showThisScheduleWizardComponent() {
  //  console.log('Attempting to load Schedule Wizard Component...');
    try {
        await loadScheduleWizardComponent();
      //  console.log('schedulerView: Component loaded, setting showThisScheduleWizard to true.');
        // console.log('schedulerView: setting showThisScheduleWizard to true.');
        showThisScheduleWizard.value = true;
    } catch (error) {
        console.error('Failed to load Schedule Wizard Component:', error);
    }
}
const updateShowThisScheduleWizardComponent = (newVal) => {
  //  console.log('updateShowThisScheduleWizard triggered');
    showThisScheduleWizard.value = newVal;
}

const addScheduleHandler = async (task) => {
    selectedTask.value = task;
    scheduleMode.value = 'new';
    await loadScheduleWizardComponent();
    showThisScheduleWizard.value = true;
}

const showNewScheduleWizard = ref(false);
function showNewScheduleComponent() {
    showNewScheduleWizard.value = !showNewScheduleWizard.value;
}


/* Task Log View */
const showLogView = ref(false);
async function viewLogsBtn(task) {
    selectedTask.value = task;
    await loadLogViewComponent();
    showLogView.value = true;
}


const logViewComponent = ref();
async function loadLogViewComponent() {
    const module = await import('../components/modals/LogView.vue');
    logViewComponent.value = module.default;
}


const updateShowLogViewComponent = (newVal) => {
    showLogView.value = newVal;
}


/* Searching + Sorting List */
const searchItem = ref('');
const filterItem = ref('no_filter');
const sortMode = ref<string | null>(null);
const sort = ref<{ field: keyof TaskInstanceType | null; order: number }>({
    field: null,
    order: 1,
});

const filteredAndSortedTasks = computed(() => {
    let filteredTasks = taskInstances.value;

    if (searchItem.value) {
        const searchQuery = searchItem.value.toLowerCase();
        filteredTasks = filteredTasks.filter(task => {
            for (const key in task) {
                const value = task[key];
                if (value && value.toString().toLowerCase().includes(searchQuery)) {
                    return true;
                }
            }
            return false;
        });
    }

    return sortTasks(filteredTasks);
});


const sortTasks = (tasksToSort: TaskInstanceType[]) => {
    if (!sort.value.field) return tasksToSort;

    const field = sort.value.field as keyof TaskInstanceType;

    return [...tasksToSort].sort((a, b) => {
        const factor = sort.value.order === 1 ? 1 : -1;
        const valueA = a[field] as string | number | null;
        const valueB = b[field] as string | number | null;

        if (valueA === null || valueB === null) {
            return valueA === null ? 1 : -1;
        }

        if (typeof valueA === 'string' && typeof valueB === 'string') {
            return factor * valueA.localeCompare(valueB);
        }

        return factor * ((valueA as number) - (valueB as number));
    });
};


const sortBy = (field: keyof TaskInstanceType) => {
    if (sort.value.field === field) {
        sort.value.order = -sort.value.order;
    } else {
        sort.value.field = field;
        sort.value.order = 1;
    }
    sortIconFlip();
};


function sortIconFlip() {
    if (sort.value.order == 1) {
        sortMode.value = 'asc';
    } else if (sort.value.order == -1) {
        sortMode.value = 'desc';
    } else {
        sortMode.value = null;
    }
}

provide('show-task-wizard', showTaskWizard);
provide('show-schedule-wizard', showThisScheduleWizard);
provide('show-edit-task-wizard', showEditTaskWizard);
provide('show-log-view', showLogView);
provide('show-notes-view', showNotesPrompt);

</script>
