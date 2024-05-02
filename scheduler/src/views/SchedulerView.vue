<template>
	<div>
		<div class="w-full h-dvh min-h-dvh overflow-visible bg-default text-default">
			<div class="p-2">
				<div class="min-w-full max-w-full max-h-full py-2 align-middle sm:px-4 lg:px-6 sm:rounded-lg bg-accent rounded-md border border-default">
                    <div class="">
                        <div class="flex flex-row justify-between sm:flex sm:items-center">
                            <div class="px-4 sm:px-0 sm:flex-auto">
                                <p class="mt-2 text-medium text-default">List of all task instances. Click on View Details button to view details.</p>
                            </div>
                            <div class="flex flex-row justify-between">
                                <div class="px-3">
                                    <label class="block text-medium font-medium leading-6 text-default">Search Tasks</label>
                                    <input type="text" @keydown.enter="" v-model="searchItem" class="text-default bg-default block w-fit input-textlike sm:text-sm" placeholder="Search..." />
                                </div>
                                <!-- <div class="px-3">
                                    <label class="block text-medium font-medium leading-6 text-default">Filter</label>
                                    <select v-model="filterItem" class="text-default bg-defaultblock w-fit input-textlike sm:text-sm">
                                        <option value="no_filter">No Filter</option>
                                        <option value="filter_item">filter_item</option>
                                    </select>
                                </div> -->
                                <div class="mt-5 py-0.5 px-3">
                                    <button @click="refreshBtn()" class="btn btn-secondary"><ArrowPathIcon class="w-5 h-5 m-0.5"/></button>
                                </div>
                                <div class="mt-5 py-0.5 px-3">
                                    <button @click="addTaskBtn()" class="btn btn-primary">Add New Task</button>
                                </div>
                            </div>
                        </div>
                        <div class="my-4 flow-root">
                            <div class="-mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
                                <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
                                    <div v-if="!loading && taskInstances.length < 1" class="min-w-full min-h-full items-center text-center bg-well">
                                        <h2>No Tasks Found</h2>
                                    </div>
                                    <table v-if="!loading && taskInstances.length > 0" class="table-auto min-w-full divide-y divide-default overflow-x-auto">
                                        <thead class="bg-well">
                                            <tr class="border border-default grid grid-cols-8">
                                                <!-- Table Headers -> Name, Enabled/Scheduled, Status, LastRuntime, Details/Empty -->
                                                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default col-span-2">
                                                    <button @click="sortBy('name')" class="flex w-full justify-between whitespace-nowrap">
                                                        Name
                                                        <BarsArrowDownIcon class="ml-1 aspect-square w-5 h-5 text-muted" v-if="sort.field === 'name' && sortMode == 'desc'"/>
                                                        <BarsArrowUpIcon class="ml-1 aspect-square w-5 h-5 text-muted" v-else-if="sort.field === 'name' && sortMode == 'asc'"/>
                                                        <Bars3Icon class="ml-1 aspect-square w-5 h-5 text-muted" v-else/>
                                                    </button>
                                                </th>
                                                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default col-span-2">
                                                    Status
                                                </th>
                                                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default col-span-2">
                                                    Last Run
                                                </th>
                                                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default col-span-1">
                                                    Scheduled
                                                </th>
                                                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-default border border-default col-span-1">
                                                    Details
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody class="bg-default">
                                            <tr v-for="taskInstance, index in filteredAndSortedTasks" :key="index" :class="showDetails[index] ? 'outline outline-2 outline-red-700 dark:outline-red-800' : ''" class="border border-default grid grid-cols-8 grid-flow-cols w-full text-center items-center rounded-sm p-1">
                                                <!-- Table Cells -->
                                                <td class="whitespace-nowrap text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
                                                    {{ taskInstance.name }}
                                                </td>
                                                <td class="whitespace-nowrap text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
                                                    &lt;status here&gt;
                                                </td>
                                                <td class="whitespace-nowrap text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
                                                    &lt;timestamp here&gt;
                                                </td>
                                                <td class="whitespace-nowrap text-base font-medium text-default border-r border-default text-left ml-4 col-span-1">
                                                    <!-- <div v-if="!taskInstance.schedule.enabled && taskInstance.schedule.intervals.length < 1">
                                                       
                                                    </div> -->
                                                
                                                    <input type="checkbox" v-model="taskInstance.schedule.enabled" class="ml-2 h-4 w-4 rounded "/>
                                                </td>
                                                <td class="whitespace-nowrap text-base font-medium text-default border-default mb-1 text-left ml-4 col-span-1">
                                                    <button v-if="!showDetails[index]" @click="taskDetailsBtn(index)" class="btn btn-secondary">View Details</button>
                                                    <button v-if="showDetails[index]" @click="closeDetailsBtn(index)" class="btn text-gray-50 bg-red-700 hover:bg-red-800 dark:hover:bg-red-900 dark:bg-red-800">Close Details</button>
                                                </td>
                                                <td v-if="showDetails[index]" class="col-span-8 h-full px-2 mx-2 py-1">
                                                    <!-- Details for ZFS Replication Task -->
                                                    <div v-if="taskInstance.template.name === 'ZFS Replication Task'" class="grid grid-cols-5 items-left text-left">
                                                        <div class="col-span-1">
                                                            <p class="my-2">
                                                                Task Type: <b>{{ taskInstance.template.name }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Send Type:
                                                                <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">Remote</b>
                                                                <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') === ''">Local</b> 
                                                            </p>
                                                        </div>
                                                        <div class="col-span-1">
                                                            <p class="my-2">
                                                                Source: <b>{{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/{{ findValue(taskInstance.parameters, 'sourceDataset', 'dataset') }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Destination: <b>{{ findValue(taskInstance.parameters, 'destDataset', 'pool') }}/{{ findValue(taskInstance.parameters, 'destDataset', 'dataset') }}</b>
                                                            </p> 
                                                            <p class="my-2" v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">
                                                                Remote SSH Host: <b>{{ findValue(taskInstance.parameters, 'destDataset', 'host') }}</b>
                                                                <br/>
                                                                Remote SSH Port: : <b>{{ findValue(taskInstance.parameters, 'destDataset', 'port') }}</b>
                                                            </p>
                                                        </div>
                                                        <div class="col-span-1">
                                                             <p class="my-2">
                                                                Recursive: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'recursive_flag')) }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Raw: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'raw_flag')) }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Compressed: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'compressed_flag')) }}</b>
                                                            </p>
                                                        </div>
                                                       
                                                        <div class="col-span-2">
                                                            <p class="my-2">Current Schedules:</p>
                                                            <div v-for="interval, idx in taskInstance.schedule.intervals" :key="idx" class="flex flex-row col-span-2 border border-default border-collapse p-1">
                                                                <p class="mx-1" v-if="interval.day">Day: {{interval.day.value}}</p>
                                                                <p class="mx-1" v-if="interval.month">Month: {{interval.month.value}}</p>
                                                                <p class="mx-1" v-if="interval.year">Year: {{interval.year.value}}</p>
                                                                <p class="mx-1" v-if="interval.hour">Hour: {{interval.hour.value}}</p>
                                                                <p class="mx-1" v-if="interval.minute">Minute: {{interval.minute.value}}</p>
                                                                <p class="mx-1" v-if="interval.dayOfWeek && interval.dayOfWeek.length > 0 && interval.dayOfWeek.length !== 1">Days of Week: {{interval.dayOfWeek.join(', ')}}</p>
                                                                <p class="mx-1" v-if="interval.dayOfWeek && interval.dayOfWeek.length == 1">Day of Week: {{interval.dayOfWeek[0]}}</p>
                                                            </div>
                                                        </div>                                        
                                                    </div>
                                                    <div class="button-group-row justify-center col-span-5 mt-2 ">

                                                        <button @click="runTaskBtn(taskInstance)" class="flex flex-row min-h-fit flex-nowrap btn btn-primary">
                                                            Run Now
                                                            <PlayIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                        <button @click="manageScheduleBtn(taskInstance)" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                            Manage Schedule
                                                            <CalendarDaysIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                        <button @click="editTaskBtn(taskInstance)" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                            Edit
                                                            <PencilIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                        <button @click="duplicateTaskBtn(taskInstance)" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                            Duplicate
                                                            <DocumentDuplicateIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                        <button @click="removeTaskBtn(taskInstance)" class="flex flex-row min-h-fit flex-nowrap btn btn-danger">
                                                            Remove
                                                            <TrashIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                            
                                                    </div>
                                                </td>           
                                            </tr>
                                        </tbody>
                                    </table>
                                    <div v-if="loading" class="flex items-center justify-center">
                                        <LoadingSpinner :width="'w-40'" :height="'h-40'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'"/>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
			</div>
            <div v-if="showTaskWizard" class="z-0">
                <AddTask :id-key="'add-task-modal'" />
            </div>

            <div v-if="showEditTaskWizard" class="z-0">
                <EditTask :id-key="'edit-task-modal'" :task="selectedTask!"/>
            </div>

            <div v-if="showThisScheduleWizard">
                <component :is="scheduleWizardComponent" @close="updateShowThisScheduleWizardComponent" :task="selectedTask" :mode="'edit'"/>
            </div>
		</div>
	</div>
</template>

<script setup lang="ts">
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import {computed, Ref, inject, ref, provide, onMounted} from 'vue';
import { ArrowPathIcon, Bars3Icon, BarsArrowDownIcon, BarsArrowUpIcon, PlayIcon, PencilIcon, TrashIcon, CalendarDaysIcon, DocumentDuplicateIcon } from '@heroicons/vue/24/outline';
import { boolToYesNo } from '../composables/helpers'
import LoadingSpinner from "../components/common/LoadingSpinner.vue";
import AddTask from "../components/wizard/AddTask.vue";
import EditTask from "../components/wizard/EditTask.vue";
import { ZFSReplicationTaskTemplate, TaskInstance, TaskTemplate, Scheduler, TaskExecutionLog, TaskExecutionResult } from '../models/Classes';

const taskInstances = inject<Ref<TaskInstanceType[]>>('task-instances')!;
const loading = inject<Ref<boolean>>('loading')!;
const myScheduler = inject<Scheduler>('scheduler')!;
const showTaskWizard = ref(false);
const showThisScheduleWizard = ref(false);
const showEditTaskWizard = ref(false)

const showDetails = ref({});
const selectedTask = ref<TaskInstanceType>();

async function refreshBtn() {
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;
}

function taskDetailsBtn(idx) {
    showDetails.value = {};
    showDetails.value[idx] = !showDetails.value[idx];
}

function closeDetailsBtn(idx) {
    showDetails.value[idx] = !showDetails.value[idx];
}

function addTaskBtn() {
    showTaskWizard.value = true;
}

function editTaskBtn(task) {
    selectedTask.value = task;
    showEditTaskWizard.value = true;
}
 
function manageScheduleBtn(task) {
    selectedTask.value = task;
    showThisScheduleWizardComponent();
}

function runTaskBtn(task) {

}

function duplicateTaskBtn(task) {
    
}

function removeTaskBtn(task) {
    
}

function findValue(obj, targetKey, valueKey) {
    if (!obj || typeof obj !== 'object') return null;

    // Checking the current level
    if (obj.key === targetKey) {
        let foundChild = obj.children?.find(child => child.key === valueKey);
        return foundChild ? (foundChild.value !== undefined ? foundChild.value : 'Not found') : 'Not found';
    }

    // Recursively checking in children
    if (Array.isArray(obj.children)) {
        for (let child of obj.children) {
            const result = findValue(child, targetKey, valueKey);
            if (result !== null) {  // Ensure '0', 'false', or empty string are valid returns
                return result;
            }
        }
    }
    
    return null;  // Return null if nothing is found
}


function getTaskStatus() {

}

function getLastRunTimestamp() {

}



// Show Schedule Wizard
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


// Searching + Sorting
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
</script> 