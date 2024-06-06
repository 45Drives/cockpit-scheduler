<template>
	<tr 
		:class="isExpanded ? 'border-2 border-red-700 dark:border-red-800 bg-default' : ''"
		class="border border-default border-collapse grid grid-cols-8 grid-flow-cols w-full text-center items-center rounded-sm p-1">
		<td
			:title="taskInstance.name" class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			{{ taskInstance.name }}
		</td>
		<td v-if="taskInstance.schedule.enabled"
			:title="taskStatus ?
				upperCaseWord(taskStatus) : 'N/A' || 'n/a'" 
				class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span :class="taskStatusClass(taskStatus)">
				{{ taskStatus ?
					upperCaseWord(taskStatus) : 'N/A' || 'n/a' }}
			</span>
		</td>
		<td v-if="!taskInstance.schedule.enabled"
			:title="'Disabled'" 
				class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span :class="taskStatusClass('Disabled')">
				Disabled
			</span>
		</td>
		<td
			:title="latestTaskExecution || 'N/A'" 
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span>
				{{ latestTaskExecution || 'N/A' }}
			</span>
		</td>
		<td class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-1">
			<input
			v-if="taskInstance.schedule.intervals.length > 0"
			:title="`Schedule is ${taskInstance.schedule.enabled ? 'Enabled' : 'Disabled'}`"
			type="checkbox"
			:checked="taskInstance.schedule.enabled"
			@click.prevent="toggleTaskSchedule"
			class="ml-2 h-4 w-4 rounded"
			/>
			<input
			v-else
			disabled
			type="checkbox"
			:title="'No Schedule Found'"
			class="ml-2 h-4 w-4 rounded bg-gray-300 dark:bg-gray-400"
			/>
		</td>
		<td
			class="truncate text-base font-medium text-default border-default m-1 col-span-1">
			<button v-if="isExpanded" @click="toggleTaskDetails()"
				class="btn text-gray-50 bg-red-700 hover:bg-red-800 dark:hover:bg-red-900 dark:bg-red-800">Close
				Details</button>
			<button v-else @click="toggleTaskDetails()"
				class="btn btn-secondary">View Details</button>
		</td>
		<td v-if="isExpanded"
			class="col-span-8 h-full px-2 mx-2 py-1 border-t border-default">
			<div>
				<TaskInstanceDetails :task="taskInstance"/>
			</div>

			<div class="button-group-row justify-center col-span-5 mt-2">
				<button @click="runTaskBtn()"
					class="flex flex-row min-h-fit flex-nowrap btn btn-primary">
					Run Now
					<PlayIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="manageScheduleBtn()"
					class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					Manage Schedule
					<CalendarDaysIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="editTaskBtn()"
					class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					Edit
					<PencilIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="viewLogsBtn()"
					class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					View Logs
					<TableCellsIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="removeTaskBtn()"
					class="flex flex-row min-h-fit flex-nowrap btn btn-danger">
					Remove
					<TrashIcon class="h-5 ml-2 mt-0.5" />
				</button>
			</div>
		</td>
	</tr>

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

</template>

<script setup lang="ts">
import { ref, onMounted, watchEffect, onUnmounted, watch } from 'vue';
import { PlayIcon, PencilIcon, TrashIcon, CalendarDaysIcon, TableCellsIcon } from '@heroicons/vue/24/outline';
import { upperCaseWord, injectWithCheck } from '../../composables/utility'
import { schedulerInjectionKey, logInjectionKey, taskInstancesInjectionKey } from '../../keys/injection-keys';
import TaskInstanceDetails from './TaskInstanceDetails.vue';

interface TaskInstanceTableRowProps {
	task: TaskInstanceType;
	isExpanded: boolean;
}

const props = defineProps<TaskInstanceTableRowProps>();
const taskInstance = ref(props.task);

const taskInstances = injectWithCheck(taskInstancesInjectionKey, "taskInstances not provided!");
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
const myTaskLog = injectWithCheck(logInjectionKey, "log not provided!");

const latestTaskExecution = ref<string>('');
const taskStatus = ref<string>('');

const emit = defineEmits(['runTask', 'manageSchedule', 'removeTask', 'editTask', 'viewLogs', 'toggleDetails']);

function runTaskBtn() {
	emit('runTask', props.task);
}

function manageScheduleBtn() {
	emit('manageSchedule', props.task);
}

function removeTaskBtn() {
	emit('removeTask', props.task);
}

function editTaskBtn() {
	emit('editTask', props.task);
}

function viewLogsBtn() {
	emit('viewLogs', props.task);
}


/* Toggle task details */
function toggleTaskDetails() {
	emit('toggleDetails', taskInstance.value.name);
}


/* Generic loading function for Confirmation Dialogs */
async function loadConfirmationDialog(dialogRef) {
	const module = await import('../../components/common/ConfirmationDialog.vue');
	dialogRef.value = module.default;
}


// Enable Task Dialog Logic
const showEnablePrompt = ref(false);
const enableDialog = ref();
const enabling = ref(false);

async function showEnableDialog() {
	await loadConfirmationDialog(enableDialog);
	return new Promise((resolve) => {
		showEnablePrompt.value = true;
		const unwatch = watch(showEnablePrompt, (newValue) => {
			if (!newValue) {
				unwatch();
				resolve(enableDialog.value === 'yes');
			}
		});
	});
}

const enableYes = async () => {
	enabling.value = true;
	console.log('enabling schedule for:', taskInstance.value.name);
	await myScheduler.enableSchedule(taskInstance.value);
	await updateTaskStatus(taskInstance.value);
	updateShowEnablePrompt(false);
	enabling.value = false;
};

const enableNo = () => {
	console.log('leaving task schedule as is');
	updateShowEnablePrompt(false);
};

const updateShowEnablePrompt = (newVal) => {
	showEnablePrompt.value = newVal;
};

// Disable Task Dialog Logic
const showDisablePrompt = ref(false);
const disableDialog = ref();
const disabling = ref(false);

async function showDisableDialog() {
	await loadConfirmationDialog(disableDialog);
	return new Promise((resolve) => {
		showDisablePrompt.value = true;
		const unwatch = watch(showDisablePrompt, (newValue) => {
			if (!newValue) {
				unwatch();
				resolve(disableDialog.value === 'yes');
			}
		});
	});
}

const disableYes = async () => {
	disabling.value = true;
	console.log('disabling schedule for:', taskInstance.value.name);
	await myScheduler.disableSchedule(taskInstance.value);
	await updateTaskStatus(taskInstance.value);
	updateShowDisablePrompt(false);
	disabling.value = false;
};

const disableNo = () => {
	console.log('leaving task schedule as is');
	updateShowDisablePrompt(false);
};

const updateShowDisablePrompt = (newVal) => {
	showDisablePrompt.value = newVal;
};

async function toggleTaskSchedule(event) {
	const intendedValue = !taskInstance.value.schedule.enabled;
	event.preventDefault();

	if (intendedValue) {
		const confirmed = await showEnableDialog();
		if (confirmed) {
			enableYes().then(() => {
				taskInstance.value.schedule.enabled = true;
			});
		}
	} else {
		const confirmed = await showDisableDialog();
		if (confirmed) {
			disableYes().then(() => {
				taskInstance.value.schedule.enabled = false;
			});
		}
	}
}

// async function toggleTaskSchedule(event) {
//     const intendedValue = !taskInstance.value.schedule.enabled;
//     event.preventDefault();

//     if (intendedValue) {
//         const confirmed = await showEnableDialog();
//         if (confirmed) {
//             enabling.value = true;
//             await myScheduler.enableSchedule(taskInstance.value);
//             taskInstance.value.schedule.enabled = true;
//             enabling.value = false;
//             await updateTaskStatus(taskInstance.value);
//         }
//     } else {
//         const confirmed = await showDisableDialog();
//         if (confirmed) {
//             disabling.value = true;
//             await myScheduler.disableSchedule(taskInstance.value);
//             taskInstance.value.schedule.enabled = false;
//             disabling.value = false;
//             await updateTaskStatus(taskInstance.value);
//         }
//     }
// }

/* Getting Task Status + Last Run Time */
const pollingInterval = ref(10000);
const intervalId = ref();
async function updateTaskStatus(task) {
	const status = await myScheduler.getTaskStatusFor(task);
	taskStatus.value = status.toString();
	// console.log(`Status for ${task.name}:`, status);
}


// change color of status text
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
		} else if (status == 'Disabled') {
				return 'text-45d';
		}
	}
}

async function fetchLatestLog(task) {
	try {
		const latestLog = await myTaskLog.getLatestEntryFor(task);
		if (latestLog) {
				latestTaskExecution.value = latestLog.startDate;
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

//handle changes in taskInstances and check status/timestamp accordingly
watchEffect(() => {
	if (taskInstances.value.length > 0) {
		pollTaskStatus();
		pollTaskLastRun();
	}
});

</script>