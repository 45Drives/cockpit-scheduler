<template>
    <div>
        <div class="flex flex-row justify-between sm:flex sm:items-center">
            <div class="px-4 sm:px-0 sm:flex-auto">
                <p class="mt-4 text-medium text-default">All tasks currently configured on the system are listed here.</p>
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
                                       <TaskInstanceTableRow v-for="taskInstance, index in filteredAndSortedTasks" :key="index" :task="taskInstance" :isExpanded="expandedTaskName === taskInstance.name"
                                       @runTask="(task) => runTaskBtn(task)" @editTask="(task) => editTaskBtn(task)" @manageSchedule="(task) => manageScheduleBtn(task)" 
                                       @removeTask="(task) => removeTaskBtn(task)" @viewLogs="(task) => viewLogsBtn(task)" @toggleDetails="toggleDetails"/>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div v-if="showTaskWizard">
        <component :is="addTaskComponent" :id-key="'add-task-modal'"/>
    </div>

    <div v-if="showEditTaskWizard">
        <component :is="editTaskComponent" :id-key="'edit-task-modal'" :task="selectedTask!"/>
    </div>

    <div v-if="showThisScheduleWizard">
        <component :is="scheduleWizardComponent" @close="updateShowThisScheduleWizardComponent" :task="selectedTask"
            :mode="'edit'" />
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
import 'houston-common-css/src/index.css';
import "houston-common-ui/style.css";
import { computed, ref, provide } from 'vue';
import { ArrowPathIcon, Bars3Icon, BarsArrowDownIcon, BarsArrowUpIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from "../components/common/CustomLoadingSpinner.vue";
import TaskInstanceTableRow from '../components/table/TaskInstanceTableRow.vue';
import { loadingInjectionKey, schedulerInjectionKey, taskInstancesInjectionKey } from '../keys/injection-keys';
import { injectWithCheck } from '../composables/utility'
const taskInstances = injectWithCheck(taskInstancesInjectionKey, "taskInstances not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

const selectedTask = ref<TaskInstanceType>();

/* Refresh Display */
async function refreshBtn() {
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;
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


/* Run Task Now */
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
    const module = await import('../components/modals/ManageSchedule.vue');
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