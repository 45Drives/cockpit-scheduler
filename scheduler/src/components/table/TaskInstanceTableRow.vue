<template>
	<tr :class="isExpanded ? 'border-2 border-red-700 dark:border-red-800 bg-default' : 'border border-default border-collapse '"
		class="grid grid-cols-8 grid-flow-cols w-full text-center items-center rounded-sm p-1">
		<td :title="taskInstance.name"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			{{ taskInstance.name }}
		</td>
		<td :title="taskInstance.schedule.enabled ? displayedStatus : 'Disabled'"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span :class="displayedStatusClass">
				{{ displayedStatus }}
			</span>
		</td>
		<td :title="latestTaskExecution" class="truncate font-medium border-r border-default text-left ml-4 col-span-2">
			<span>
				{{ latestTaskExecution }}
			</span>
		</td>

		<td class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-1">
			<input v-if="taskInstance.schedule.intervals.length > 0"
				:title="`Schedule is ${taskInstance.schedule.enabled ? 'Enabled' : 'Disabled'}`" type="checkbox"
				:checked="taskInstance.schedule.enabled" @click.prevent="toggleTaskSchedule"
				class="ml-2 h-4 w-4 rounded" />
			<input v-else disabled type="checkbox"
				:title="'No Schedule Found, Manage Schedule + add intervals to Enable'"
				class="ml-2 h-4 w-4 rounded bg-gray-300 dark:bg-gray-400" />
		</td>
		<td class="truncate text-base font-medium text-default border-default m-1 col-span-1">
			<button v-if="isExpanded" @click="toggleTaskDetails()"
				class="btn text-gray-50 bg-red-700 hover:bg-red-800 dark:hover:bg-red-900 dark:bg-red-800">Close
				Details</button>
			<button v-else @click="toggleTaskDetails()" class="btn btn-secondary">View Details</button>
		</td>
		<td v-if="isExpanded" class="col-span-8 h-full px-2 mx-2 py-1 border-t border-default">
			<div>
				<TaskInstanceDetails :task="taskInstance" />
			</div>

			<div class="button-group-row justify-center col-span-5 mt-2">
				<button @click="runTaskBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-primary">
					Run Now
					<PlayIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="editTaskBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					Edit Task
					<PencilIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="manageScheduleBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					Manage Schedule
					<CalendarDaysIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="viewLogsBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					View Logs
					<TableCellsIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="viewNotesBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					Notes
					<PencilSquareIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="removeTaskBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-danger">
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
import { ref, onMounted, onUnmounted, watch, defineExpose, computed } from 'vue';
import { PlayIcon, PencilIcon, TrashIcon, CalendarDaysIcon, TableCellsIcon,PencilSquareIcon } from '@heroicons/vue/24/outline';
import { injectWithCheck } from '../../composables/utility'
import { schedulerInjectionKey, logInjectionKey } from '../../keys/injection-keys';
import TaskInstanceDetails from './TaskInstanceDetails.vue';

interface TaskInstanceTableRowProps {
	task: TaskInstanceType;
	isExpanded: boolean;
}

const props = defineProps<TaskInstanceTableRowProps>();
const taskInstance = ref(props.task);

const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
const myTaskLog = injectWithCheck(logInjectionKey, "log not provided!");

const latestTaskExecution = ref<string>('');
const taskStatus = ref<string>('');
const manualRunUntil = ref<number>(0);
function markManualRun(windowMs = 60_000) {
	manualRunUntil.value = Date.now() + windowMs;
}

const emit = defineEmits(['runTask', 'manageSchedule', 'removeTask', 'editTask', 'viewLogs', 'toggleDetails', 'viewNotes']);

async function runTaskBtn() {
	emit('runTask', props.task);
}

function manageScheduleBtn() {
	emit('manageSchedule', props.task);
}

let intervalId: number | undefined;

function removeTaskBtn() {
	if (intervalId) {
		clearInterval(intervalId);
		intervalId = undefined;
	}
	emit('removeTask', props.task);
}

function editTaskBtn() {
	emit('editTask', props.task);
}

function viewLogsBtn() {
	emit('viewLogs', props.task);
}
function viewNotesBtn(){
	emit('viewNotes',props.task);
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
	if (intervalId) {
		clearInterval(intervalId);
		intervalId = undefined;
	}
	await myScheduler.enableSchedule(taskInstance.value);
	await updateTaskStatus(taskInstance.value, taskInstance.value.schedule.enabled);
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
	if (intervalId) {
		clearInterval(intervalId);
		intervalId = undefined;
	}
	await myScheduler.disableSchedule(taskInstance.value);
	await updateTaskStatus(taskInstance.value, taskInstance.value.schedule.enabled);
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

const displayedStatus = computed(() => {
	if (!taskInstance.value?.schedule?.enabled) return 'Disabled';
	return taskStatus.value || 'N/A';
});

const displayedStatusClass = computed(() => {
	const s = (displayedStatus.value || '').toLowerCase();
	if (s.includes('active') || s.includes('starting') || s.includes('completed')) return 'text-success';
	if (s.includes('inactive') || s.includes('disabled') || s.includes('not scheduled')) return 'text-warning';
	if (s.includes('failed') || s.includes('error')) return 'text-danger';
	if (s.includes('no schedule found') || s.includes('not scheduled')) return 'text-muted';
	return '';
});


/* Getting Task Status + Last Run Time */
onMounted(async () => {
	await updateTaskStatus(taskInstance.value, taskInstance.value.schedule.enabled);
	await fetchLatestLog(taskInstance.value);

	intervalId = setInterval(async () => {
		try {
			await updateTaskStatus(taskInstance.value, taskInstance.value.schedule.enabled);
			await fetchLatestLog(taskInstance.value);
		} catch (error) {
			console.error('Polling failed:', error);
			clearInterval(intervalId);
		}
	}, 1500);

	onUnmounted(() => {
		if (intervalId) {
			clearInterval(intervalId);
		}
	});
});


// Ensure updates when taskInstance changes
watch(taskInstance, async (newTask, oldTask) => {
	if (!newTask) {
		if (intervalId) {
			clearInterval(intervalId);
			intervalId = undefined;
		}
		return;
	}
	try {
		await updateTaskStatus(newTask, newTask.schedule.enabled);
		await fetchLatestLog(newTask);
	} catch (error: any) {
		console.error(`Error updating task status:`, error);
		if (error.stderr && error.stderr.includes('Unit could not be found')) {
			if (intervalId) {
				clearInterval(intervalId);
				intervalId = undefined;
			}
		}
	}
});

async function updateTaskStatus(task, timerEnabled) {
	try {
		if (!timerEnabled) {
			taskStatus.value = 'Disabled';
			// Optional: if you want to stop polling entirely when disabled:
			if (intervalId) { clearInterval(intervalId); intervalId = undefined; }
			return;
		}

		const status = await myScheduler.getTimerStatus(task);

		// If the backend told us the unit is gone, stop polling gently
		if (status === 'Unit inactive or not found.') {
			taskStatus.value = 'Disabled';
			if (intervalId) { clearInterval(intervalId); intervalId = undefined; }
			return;
		}

		taskStatus.value = status.toString();
	} catch (error) {
		// Unexpected error — stop polling this row so we don’t spam
		console.error(`Failed to get status for ${task.name}:`, error);
		taskStatus.value = 'Error';
		if (intervalId) { clearInterval(intervalId); intervalId = undefined; }
	}
}


async function fetchLatestLog(task) {
	try {
		const latestLog = await myTaskLog.getLatestEntryFor(task);
		if (latestLog) {
			// Update the latestTaskExecution to reflect the start time or output
			if (latestLog.startDate) {
				latestTaskExecution.value = latestLog.startDate;
			} else {
				latestTaskExecution.value = latestLog.output || "Task hasn't run yet.";
			}
		} else {
			latestTaskExecution.value = "Task hasn't run yet.";
		}
	} catch (error) {
		console.error("Failed to fetch logs:", error);
		if (intervalId) {
			clearInterval(intervalId);
		}
	}
}

defineExpose({
	updateTaskStatus,
	fetchLatestLog,
	markManualRun
});
</script>