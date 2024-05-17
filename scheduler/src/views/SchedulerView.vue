<template>
    <div>
        <div class="flex flex-row justify-between sm:flex sm:items-center">
            <div class="px-4 sm:px-0 sm:flex-auto">
                <p class="mt-4 text-medium text-default">All tasks currently configured on the system are listed
                    here.</p>
            </div>
            <div class="flex flex-row justify-between">
                <div class="px-3">
                    <label class="block text-medium font-medium leading-6 text-default">Search Tasks</label>
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
            </div>
        </div>

        <div class="my-4 flow-root">
            <div class="-mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
                <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8 overflow-x-auto">
                    <div v-if="!loading && taskInstances.length < 1"
                        class="min-w-full min-h-full items-center text-center bg-well">
                        <h2>No Tasks Found</h2>
                    </div>
                    <div v-if="!loading && taskInstances.length > 0" class="relative">
	                    <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-default">
                                <thead class="bg-well">
                                    <tr class="border border-default border-collapse grid grid-cols-8 w-full">
                                        <!-- Table Headers -> Name, Enabled/Scheduled, Status, LastRuntime, Details/Empty -->
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
                                    <tr v-for="taskInstance, index in filteredAndSortedTasks" :key="index"
                                        :class="showDetails[index] ? 'border-2 border-red-700 dark:border-red-800 bg-default' : ''"
                                        class="border border-default border-collapse grid grid-cols-8 grid-flow-cols w-full text-center items-center rounded-sm p-1">
                                        <!-- Table Cells -->
                                        <td
                                            :title="taskInstance.name" class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
                                            {{ taskInstance.name }}
                                        </td>
                                        <td
                                            :title="taskStatuses.get(taskInstance.name) ?
                                                    upperCaseWord(taskStatuses.get(taskInstance.name)) : 'N/A' || 'n/a'" 
                                                    class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
                                            <span :class="taskStatusClass(taskStatuses.get(taskInstance.name))">
                                                {{ taskStatuses.get(taskInstance.name) ?
                                                    upperCaseWord(taskStatuses.get(taskInstance.name)) : 'N/A' || 'n/a' }}
                                            </span>
                                        </td>
                                        <td
                                            :title="latestTaskExecution.get(taskInstance.name) || 'N/A'" 
                                            class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
                                            <span>
                                                {{ latestTaskExecution.get(taskInstance.name) || 'N/A' }}
                                            </span>
                                        </td>
                                        <td
                                            class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-1">
                                            <input v-if="taskInstance.schedule.intervals.length > 0"
                                                :title="`Schedule is ${taskInstance.schedule.enabled ? 'Enabled' : 'Disabled'}`"
                                                type="checkbox" :checked="taskInstance.schedule.enabled"
                                                @change="handleScheduleCheckboxChange(taskInstance, index)"
                                                class="ml-2 h-4 w-4 rounded " />
                                            <input v-else disabled type="checkbox" :title="'No Schedule Found'"
                                                class="ml-2 h-4 w-4 rounded bg-gray-300 dark:bg-gray-400" />
                                        </td>
                                        <td
                                            class="truncate text-base font-medium text-default border-default m-1 col-span-1">
                                            <button v-if="!showDetails[index]" @click="taskDetailsBtn(index)"
                                                class="btn btn-secondary">View Details</button>
                                            <button v-if="showDetails[index]" @click="closeDetailsBtn(index)"
                                                class="btn text-gray-50 bg-red-700 hover:bg-red-800 dark:hover:bg-red-900 dark:bg-red-800">Close
                                                Details</button>
                                        </td>
                                        <td v-if="showDetails[index]"
                                            class="col-span-8 h-full px-2 mx-2 py-1 border-t border-default">
                                            <div>
                                                <!-- Details for ZFS Replication Task -->
                                                <div v-if="taskInstance.template.name === 'ZFS Replication Task'"
                                                    class="grid grid-cols-4 items-left text-left">
                                                    <div class="col-span-1">
                                                        <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                                                            Task Type: <b>{{ taskInstance.template.name }}</b>
                                                        </p>
                                                        <p class="my-2 truncate" :title="`Send Type: ${findValue(taskInstance.parameters, 'destDataset', 'host') !== '' ? 'Remote' : 'Local'}`">
                                                            Send Type:
                                                            <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">Remote</b>
                                                            <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') === ''">Local</b>
                                                        </p>
                                                        <p class="my-2"
                                                            v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">
                                                            <p class="truncate" :title="`Remote SSH Host: ${findValue(taskInstance.parameters,'destDataset', 'host')}`">
                                                                Remote SSH Host: <b>{{ findValue(taskInstance.parameters,'destDataset', 'host') }}</b>
                                                            </p>
                                                            <p class="truncate" :title="`Remote SSH Port: ${findValue(taskInstance.parameters,'destDataset', 'port')}`">
                                                                Remote SSH Port: : <b>{{ findValue(taskInstance.parameters,'destDataset', 'port') }}</b>
                                                            </p>        
                                                        </p>
                                                    </div>
                                                    <div class="col-span-1">
                                                        <p class="my-2 truncate" 
                                                        :title="`Compression: ${findValue(taskInstance.parameters, 'sendOptions', 'raw_flag') ? 'Raw' : findValue(taskInstance.parameters, 'sendOptions', 'compressed_flag') ? 'Compressed' : 'None'}`">
                                                            Compression: <b>{{ findValue(taskInstance.parameters,
                                                                'sendOptions', 'raw_flag') ? 'Raw' :
                                                                findValue(taskInstance.parameters, 'sendOptions',
                                                                    'compressed_flag') ? 'Compressed' : 'None' }}</b>
                                                        </p>
                                                        <p class="my-2 truncate" 
                                                        :title="`Recursive Send: ${boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'recursive_flag'))}`">
                                                            Recursive Send: <b>{{
                                                                boolToYesNo(findValue(taskInstance.parameters,
                                                                    'sendOptions', 'recursive_flag')) }}</b>
                                                        </p>
                                                    </div>
                                                    <div class="col-span-2 row-span-2">
                                                        <p class="my-2 font-bold">Current Schedules:</p>
                                                        <div v-if="taskInstance.schedule.intervals.length > 0"
                                                            v-for="interval, idx in taskInstance.schedule.intervals" :key="idx"
                                                            class="flex flex-row col-span-2 divide divide-y divide-default p-1" :title="`Run ${myScheduler.parseIntervalIntoString(interval)}.`">
                                                            <p>Run {{ myScheduler.parseIntervalIntoString(interval) }}.</p>
                                                        </div>
                                                        <div v-else>
                                                            <p>No Intervals Currently Scheduled</p>
                                                        </div>
                                                    </div>
                                                    <div class="col-span-1">
                                                        <p class="my-2 truncate" :title="`Source: ${findValue(taskInstance.parameters, 'sourceDataset', 'dataset')}`">
                                                            Source: <b>
                                                                <!-- {{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/ -->
                                                                {{ findValue(taskInstance.parameters, 'sourceDataset',
                                                                    'dataset') }}
                                                            </b>
                                                        </p>
                                                        <p class="my-2 truncate" :title="`Source Snapshots to Keep: ${findValue(taskInstance.parameters, 'snapRetention', 'source')}`">
                                                            Source Snapshots to Keep: <b>
                                                                {{ findValue(taskInstance.parameters, 'snapRetention',
                                                                    'source') }}
                                                            </b>
                                                        </p>
                                                    </div>
                                                    <div class="col-span-1">
                                                        <p class="my-2 truncate" :title="`Destination: ${findValue(taskInstance.parameters, 'destDataset', 'dataset')}`">
                                                            Destination: <b>
                                                                <!-- {{ findValue(taskInstance.parameters, 'destDataset', 'pool') }}/ -->
                                                                {{ findValue(taskInstance.parameters, 'destDataset',
                                                                    'dataset') }}
                                                            </b>
                                                        </p>
                                                        <p class="my-2 truncate" :title="`Destination Snapshots to Keep: ${findValue(taskInstance.parameters, 'snapRetention', 'destination')}`">
                                                            Destination Snapshots to Keep: <b>
                                                                {{ findValue(taskInstance.parameters, 'snapRetention',
                                                                    'destination') }}
                                                            </b>
                                                        </p>
                                                    </div>
                                                </div>

                                                <!-- Details for Automated Snapshot Task -->
                                                <div v-if="taskInstance.template.name === 'Automated Snapshot Task'"
                                                    class="grid grid-cols-4 items-left text-left">
                                                    <div class="col-span-1">
                                                        <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                                                            Task Type: <b>{{ taskInstance.template.name }}</b>
                                                        </p>
                                                        <p class="my-2 truncate" :title="`Filesystem: ${findValue(taskInstance.parameters, 'filesystem', 'dataset')}`">
                                                            Filesystem: <b>
                                                                <!-- {{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/ -->
                                                                {{ findValue(taskInstance.parameters, 'filesystem',
                                                                    'dataset') }}
                                                            </b>
                                                        </p>
                                                        <p v-if="findValue(taskInstance.parameters, 'customName_flag', 'customName_flag')"
                                                            class="my-2 truncate" :title="`Custom Snapshot Name: ${findValue(taskInstance.parameters, 'customName', 'customName')}`">
                                                            Custom Snapshot Name: <b>
                                                                <!-- {{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/ -->
                                                                {{ findValue(taskInstance.parameters, 'customName',
                                                                    'customName') }}
                                                            </b>
                                                        </p>
                                                    </div>
                                                    <div class="col-span-1">
                                                        <p class="my-2 truncate" :title="`Recursive Snapshots: ${boolToYesNo(findValue(taskInstance.parameters, 'recursive_flag', 'recursive_flag'))}`">
                                                            Recursive Snapshots: <b>{{
                                                                boolToYesNo(findValue(taskInstance.parameters,
                                                                    'recursive_flag', 'recursive_flag')) }}</b>
                                                        </p>
                                                        <p class="my-2 truncate" :title="`Snapshots to Keep: ${findValue(taskInstance.parameters, 'snapRetention', 'snapRetention')}`">
                                                            Snapshots to Keep: <b>
                                                                {{ findValue(taskInstance.parameters, 'snapRetention',
                                                                    'snapRetention') }}
                                                            </b>
                                                        </p>
                                                    </div>
                                                    <div class="col-span-2 row-span-2">
                                                        <p class="my-2 font-bold">Current Schedules:</p>
                                                        <div v-if="taskInstance.schedule.intervals.length > 0"
                                                            v-for="interval, idx in taskInstance.schedule.intervals" :key="idx"
                                                            class="flex flex-row col-span-2 divide divide-y divide-default p-1" :title="`Run ${myScheduler.parseIntervalIntoString(interval)}.`">
                                                            <p>Run {{ myScheduler.parseIntervalIntoString(interval) }}.</p>
                                                        </div>
                                                        <div v-else>
                                                            <p>No Intervals Currently Scheduled</p>
                                                        </div>
                                                    </div>

                                                </div>
                                            </div>

                                            <div class="button-group-row justify-center col-span-5 mt-2">
                                                <button @click="runTaskBtn(taskInstance)"
                                                    class="flex flex-row min-h-fit flex-nowrap btn btn-primary">
                                                    Run Now
                                                    <PlayIcon class="h-5 ml-2 mt-0.5" />
                                                </button>
                                                <button @click="manageScheduleBtn(taskInstance)"
                                                    class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                    Manage Schedule
                                                    <CalendarDaysIcon class="h-5 ml-2 mt-0.5" />
                                                </button>
                                                <button @click="editTaskBtn(taskInstance)"
                                                    class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                    Edit
                                                    <PencilIcon class="h-5 ml-2 mt-0.5" />
                                                </button>
                                                <button @click="viewLogsBtn(taskInstance)"
                                                    class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                    View Logs
                                                    <TableCellsIcon class="h-5 ml-2 mt-0.5" />
                                                </button>
                                                <button @click="removeTaskBtn(taskInstance, index)"
                                                    class="flex flex-row min-h-fit flex-nowrap btn btn-danger">
                                                    Remove
                                                    <TrashIcon class="h-5 ml-2 mt-0.5" />
                                                </button>

                                            </div>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <div v-if="loading" class="flex items-center justify-center">
                        <CustomLoadingSpinner :width="'w-32'" :height="'h-32'" :baseColor="'text-gray-200'"
                            :fillColor="'fill-gray-500'" />
                    </div>
                </div>
            </div>
        </div>
    </div>





    <div v-if="showTaskWizard" class="z-0">
        <AddTask :id-key="'add-task-modal'" />
    </div>

    <div v-if="showEditTaskWizard" class="z-0">
        <EditTask :id-key="'edit-task-modal'" :task="selectedTask!" />
    </div>

    <div v-if="showThisScheduleWizard">
        <component :is="scheduleWizardComponent" @close="updateShowThisScheduleWizardComponent" :task="selectedTask"
            :mode="'edit'" />
    </div>

    <div v-if="showEnablePrompt">
        <component :is="enableDialog" @close="updateShowEnablePrompt" :showFlag="showEnablePrompt"
            :title="'Enable Schedule'" :message="'Do you wish to enable the schedule for this task?'"
            :confirmYes="enableYes" :confirmNo="enableNo" :operating="enabling" :operation="'enabling'" />
    </div>
    <div v-if="showDisablePrompt">
        <component :is="disableDialog" @close="updateShowDisablePrompt" :showFlag="showDisablePrompt"
            :title="'Disable Schedule'" :message="'Do you wish to disable the schedule for this task?'"
            :confirmYes="disableYes" :confirmNo="disableNo" :operating="disabling" :operation="'disabling'" />
    </div>

    <div v-if="showRunNowPrompt">
        <component :is="runNowDialog" @close="updateShowRunNowPrompt" :showFlag="showRunNowPrompt" :title="'Run Task'"
            :message="'Do you wish to run this task now?'" :confirmYes="runNowYes" :confirmNo="runNowNo"
            :operating="running" :operation="'starting'" />
    </div>

    <div v-if="showRemoveTaskPrompt">
        <component :is="removeTaskDialog" @close="updateShowRemoveTaskPrompt" :showFlag="showRemoveTaskPrompt"
            :title="'Remove Task'" :message="'Are you sure you want to remove this task?'" :confirmYes="removeTaskYes"
            :confirmNo="removeTaskNo" :operating="removing" :operation="'removing'" />
    </div>

    <div v-if="showLogView">
        <component :is="logViewComponent" @close="updateShowLogViewComponent" :task="selectedTask" />
    </div>

</template>

<script setup lang="ts">
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import { computed, Ref, inject, ref, provide, reactive, onMounted, watchEffect, onUnmounted } from 'vue';
import { ArrowPathIcon, Bars3Icon, BarsArrowDownIcon, BarsArrowUpIcon, PlayIcon, PencilIcon, TrashIcon, CalendarDaysIcon, TableCellsIcon } from '@heroicons/vue/24/outline';
import { boolToYesNo, upperCaseWord } from '../composables/utility'
import CustomLoadingSpinner from "../components/common/CustomLoadingSpinner.vue";
import AddTask from "../components/wizard/AddTask.vue";
import EditTask from "../components/wizard/EditTask.vue";
import { Scheduler } from '../models/Scheduler';
import { TaskExecutionLog } from '../models/TaskLog';


const taskInstances = inject<Ref<TaskInstanceType[]>>('task-instances')!;
const loading = inject<Ref<boolean>>('loading')!;
const myScheduler = inject<Scheduler>('scheduler')!;
const myTaskLog = inject<TaskExecutionLog>('log')!;
const selectedTask = ref<TaskInstanceType>();
const selectedTaskIdx = ref<number>();
const latestTaskExecution = reactive(new Map());
const taskStatuses = reactive(new Map());

function findValue(obj, targetKey, valueKey) {
    if (!obj || typeof obj !== 'object') return null;

    // Directly check at the current level if this is the targetKey
    if (obj.key === targetKey) {
        // If looking for the same key as targetKey and it has a value, return it
        if (targetKey === valueKey && obj.value !== undefined) {
            return obj.value;
        }
        // If there's a different valueKey to find, look for it among children
        let foundChild = obj.children?.find(child => child.key === valueKey);
        if (foundChild && foundChild.value !== undefined) {
            return foundChild.value;
        }
    }

    // If no value found at this level, and there are children, search them recursively
    if (Array.isArray(obj.children)) {
        for (let child of obj.children) {
            const result = findValue(child, targetKey, valueKey);
            if (result !== null) {  // Ensure '0', 'false', or empty string are considered valid returns
                return result;
            }
        }
    }

    return null;  // If the search yields no results, return null
}

// Polling Interval
const pollingInterval = ref(10000);
const intervalId = ref();

async function updateTaskStatus(task) {
    const status = await myScheduler.getTaskStatusFor(task);
    taskStatuses.set(task.name, status);
    // console.log(`Status for ${task.name}:`, status);
}

function taskStatusClass(status) {
    if (status) {
        if (status.includes('active')) {
            return 'text-success';
        } else if (status.includes('inactive')) {
            return 'text-warning';
        } else if (status.includes('failed')) {
            return 'text-danger';
        } else if (status.includes('No schedule found') || status.includes('Not scheduled')) {
            return 'text-muted';
        }
    }
}

async function fetchLatestLog(task) {
    try {
        const latestLog = await myTaskLog.getLatestEntryFor(task);
        if (latestLog) {
            latestTaskExecution.set(task.name, latestLog.startDate);
        }
        // console.log(`Last execution of ${task.name}:`, latestLog);
    } catch (error) {
        console.error("Failed to fetch logs:", error);
    }
};

const pollTaskStatus = async () => {
    if (taskInstances.value) {
        for (const task of taskInstances.value) {
            await updateTaskStatus(task);
        }
    }
}

const pollTaskLastRun = async () => {
    if (taskInstances.value) {
        for (const task of taskInstances.value) {
            await fetchLatestLog(task);
        }
    }
}

const startPolling = () => {
    if (!intervalId.value) {
        intervalId.value = setInterval(() => {
            pollTaskStatus();
        }, pollingInterval.value);
    }
}

const stopPolling = () => {
    if (intervalId.value) {
        clearInterval(intervalId.value);
        intervalId.value = null;
    }
}

onMounted(() => {
    startPolling();
});

onUnmounted(() => {
    stopPolling();
});

// Optional: watchEffect to handle changes in taskInstances
watchEffect(() => {
    if (taskInstances.value.length > 0) {
        pollTaskStatus();
        pollTaskLastRun();
    }
});



const showDetails = ref({});
function taskDetailsBtn(idx) {
    showDetails.value = {};
    showDetails.value[idx] = !showDetails.value[idx];
}

function closeDetailsBtn(idx) {
    showDetails.value[idx] = !showDetails.value[idx];
}

const showTaskWizard = ref(false);
function addTaskBtn() {
    showTaskWizard.value = true;
}

const showEditTaskWizard = ref(false)
function editTaskBtn(task) {
    selectedTask.value = task;
    showEditTaskWizard.value = true;
}

async function refreshBtn() {
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;
}

async function loadConfirmationDialog(dialogRef) {
    const module = await import('../components/common/ConfirmationDialog.vue');
    dialogRef.value = module.default;
}


// handle checkbox for toggling task schedule enabled/disabled
function handleScheduleCheckboxChange(task: TaskInstanceType, index: number) {
    selectedTask.value = task;
    selectedTaskIdx.value = index;

    if (selectedTask.value.schedule.enabled) {
        showDisableDialog();
    } else {
        showEnableDialog();
    }
}


/* Enable Task */
const showEnablePrompt = ref(false);
const enableDialog = ref();
const enabling = ref(false);

async function showEnableDialog() {
    await loadConfirmationDialog(enableDialog);
    showEnablePrompt.value = true;
}
const enableYes: ConfirmationCallback = async () => {
    enabling.value = true;
    console.log('enabling schedule for:', selectedTask.value!.name)
    await myScheduler.enableSchedule(selectedTask!.value);
    await updateTaskStatus(selectedTask.value);
    updateShowEnablePrompt(false);
    enabling.value = false;


}
const enableNo: ConfirmationCallback = async () => {
    console.log('leaving task schedule as is');
    selectedTask.value!.schedule.enabled = selectedTask.value!.schedule.enabled;
    await updateTaskStatus(selectedTask.value);
    updateShowEnablePrompt(false);
}
const updateShowEnablePrompt = (newVal) => {
    showEnablePrompt.value = newVal;
}


/* Disable Task */
const showDisablePrompt = ref(false);
const disableDialog = ref();
const disabling = ref(false);

async function showDisableDialog() {
    await loadConfirmationDialog(disableDialog);
    showDisablePrompt.value = true;
}
const disableYes: ConfirmationCallback = async () => {
    disabling.value = true;
    console.log('disabling schedule for:', selectedTask.value!.name)
    await myScheduler.disableSchedule(selectedTask!.value);
    updateShowDisablePrompt(false);
    disabling.value = false;
}
const disableNo: ConfirmationCallback = async () => {
    console.log('leaving task schedule as is');
    updateShowDisablePrompt(false);
}
const updateShowDisablePrompt = (newVal) => {
    showDisablePrompt.value = newVal;
}


/* Run Task Ad Hoc */
const showRunNowPrompt = ref(false);
const runNowDialog = ref();
const running = ref(false);

function runTaskBtn(task) {
    selectedTask.value = task;
    showRunNowDialog();
}
async function showRunNowDialog() {
    await loadConfirmationDialog(runNowDialog);
    showRunNowPrompt.value = true;
}
const runNowYes: ConfirmationCallback = async () => {
    running.value = true;
    await myScheduler.runTaskNow(selectedTask.value!);
    pollTaskStatus();
    pollTaskLastRun();  
    updateShowRunNowPrompt(false);
    running.value = false;
}
const runNowNo: ConfirmationCallback = async () => {
    updateShowRunNowPrompt(false);
}
const updateShowRunNowPrompt = (newVal) => {
    showRunNowPrompt.value = newVal;
}


/* Remove Task */
const showRemoveTaskPrompt = ref(false);
const removeTaskDialog = ref();
const removing = ref(false);

function removeTaskBtn(task, index) {
    console.log('removeTaskBtn triggered');
    selectedTask.value = task;
    selectedTaskIdx.value = index;
    showRemoveTaskDialog();
}
async function showRemoveTaskDialog() {
    await loadConfirmationDialog(removeTaskDialog);
    showRemoveTaskPrompt.value = true;
}
const removeTaskYes: ConfirmationCallback = async () => {
    removing.value = true;
    await myScheduler.unregisterTaskInstance(selectedTask.value!);
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;
    removing.value = false;
    updateShowRemoveTaskPrompt(false);
}
const removeTaskNo: ConfirmationCallback = async () => {
    updateShowRemoveTaskPrompt(false);
}
const updateShowRemoveTaskPrompt = (newVal) => {
    showRemoveTaskPrompt.value = newVal;
}


/* Schedule Management */
const showThisScheduleWizard = ref(false);
function manageScheduleBtn(task) {
    selectedTask.value = task;
    showThisScheduleWizardComponent();
}

const scheduleWizardComponent = ref();
const loadScheduleWizardComponent = async () => {
    console.log('loadScheduleWizard triggered');
    const module = await import('../components/wizard/ManageSchedule.vue');
    scheduleWizardComponent.value = module.default;
}

async function showThisScheduleWizardComponent() {
    console.log('Attempting to load Schedule Wizard Component...');
    try {
        await loadScheduleWizardComponent();
        console.log('schedulerView: Component loaded, setting showThisScheduleWizard to true.');
        // console.log('schedulerView: setting showThisScheduleWizard to true.');
        showThisScheduleWizard.value = true;
    } catch (error) {
        console.error('Failed to load Schedule Wizard Component:', error);
    }
}

const updateShowThisScheduleWizardComponent = (newVal) => {
    console.log('updateShowThisScheduleWizard triggered');
    showThisScheduleWizard.value = newVal;
}

/* Task Log View */
const showLogView = ref(false);
async function viewLogsBtn(task) {
    selectedTask.value = task;
    await loadLogViewComponent();
    showLogView.value = true;
}
// async function viewAllLogsBtn() {
//     selectedTask.value = undefined;
//     await loadLogViewComponent();
//     showLogView.value = true;
// }
const logViewComponent = ref();
async function loadLogViewComponent() {
    const module = await import('../views/LogView.vue');
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
                } // const result = JSON.parse(output.stdout);
                // return result;
            }
            return false;
        });
    }

    if (filterItem.value && filterItem.value !== 'no_filter') {
        // filter based on status (need to figure out and program what status is first)
        // filteredTasks = filteredTasks.filter(task => formatStatus(task.active) === filterItem.value);
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
</script>