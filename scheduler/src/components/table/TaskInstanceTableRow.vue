<template>
	<tr :class="isExpanded ? 'border-2 border-red-700 dark:border-red-800 bg-default' : 'border border-default border-collapse '"
		class="grid grid-cols-10 grid-flow-cols w-full text-center items-center rounded-sm p-1">
		<!-- Name -->
		<td :title="taskInstance.name"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			{{ taskInstance.name }}
		</td>

		<!-- Status -->
		<td v-if="taskInstance.schedule.enabled" :title="statusText"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span :class="taskStatusClass(statusText)">{{ statusText || 'N/A' }}</span>
		</td>
		<td v-else title="Disabled"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span :class="taskStatusClass(statusText)">{{ statusText || 'N/A' }}</span>
		</td>

		<!-- Scope -->
		<td :title="taskInstance.scope"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-1">
			<span>{{ taskInstance.scope }}</span>
		</td>

		<!-- Last run -->
		<td :title="lastRunText" class="truncate text-xs font-medium border-r border-default text-left ml-4 col-span-2">
			<span>{{ lastRunText }}</span>
		</td>

		<!-- Scheduled toggle -->
		<td class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-1">
			<input v-if="taskInstance.schedule.intervals.length > 0"
				:title="`Schedule is ${taskInstance.schedule.enabled ? 'Enabled' : 'Disabled'}`" type="checkbox"
				:checked="taskInstance.schedule.enabled" @click.prevent="toggleTaskSchedule"
				class="ml-2 h-4 w-4 rounded" />
			<input v-else disabled type="checkbox" title="No Schedule Found, Manage Schedule + add intervals to Enable"
				class="ml-2 h-4 w-4 rounded bg-gray-300 dark:bg-gray-400" />
		</td>

		<!-- Actions -->
		<td class="text-base font-medium text-default border-default m-1 col-span-2">
			<button v-if="isExpanded" @click="toggleTaskDetails()"
				class="btn text-gray-50 bg-red-700 hover:bg-red-800 dark:hover:bg-red-900 dark:bg-red-800">
				Close Details
			</button>
			<button v-else @click="toggleTaskDetails()" class="btn btn-secondary">
				View Details
			</button>
		</td>

		<!-- Progress bar (full width row) -->
		<td v-if="progress !== null && isRunning" class="col-span-10 h-full px-2 mx-2 py-1 border-t border-default">
			<div >
				<div class="w-full bg-slate-200 dark:bg-slate-700 h-2 rounded">
					<div class="h-2 rounded" :class="progressBarClass"
						:style="{ width: Math.min(progress, 100) + '%' }"></div>
				</div>
				<div class="text-xs mt-1">
					{{ Math.round(progress) }}%
				</div>
			</div>
		</td>

		<!-- Expanded details -->
		<td v-if="isExpanded" class="col-span-10 h-full px-2 mx-2 py-1 border-t border-default">
			<div>
				<TaskInstanceDetails :task="taskInstance" />
			</div>

			<div class="button-group-row justify-center mt-2">
				<button v-if="!isRunning" @click="runTaskBtn()"
					class="flex flex-row min-h-fit flex-nowrap btn btn-success">
					Run Now
					<PlayIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button v-else @click="stopTaskBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-danger">
					Stop Now
					<StopIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="editTaskBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
					Edit Task
					<PencilIcon class="h-5 ml-2 mt-0.5" />
				</button>
				<button @click="manageScheduleBtn()" class="flex flex-row min-h-fit flex-nowrap btn btn-primary">
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

	<!-- Enable/Disable confirmation dialogs -->
	<div v-if="showEnablePrompt">
		<component :is="enableDialog" @close="updateShowEnablePrompt" :showFlag="showEnablePrompt"
			title="Enable Schedule" message="Do you wish to enable the schedule for this task?" :confirmYes="enableYes"
			:confirmNo="enableNo" :operating="enabling" operation="enabling" />
	</div>

	<div v-if="showDisablePrompt">
		<component :is="disableDialog" @close="updateShowDisablePrompt" :showFlag="showDisablePrompt"
			title="Disable Schedule" message="Do you wish to disable the schedule for this task?"
			:confirmYes="disableYes" :confirmNo="disableNo" :operating="disabling" operation="disabling" />
	</div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, defineExpose, computed } from 'vue';
import {
	PlayIcon,
	PencilIcon,
	TrashIcon,
	CalendarDaysIcon,
	TableCellsIcon,
	PencilSquareIcon,
	StopIcon,
} from '@heroicons/vue/24/outline';
import { injectWithCheck } from '../../composables/utility';
import { schedulerInjectionKey, logInjectionKey } from '../../keys/injection-keys';
import TaskInstanceDetails from './TaskInstanceDetails.vue';
import { useLiveTaskStatus, taskStatusClass } from '../../composables/useLiveTaskStatus';

interface TaskInstanceTableRowProps {
	task: TaskInstanceType;
	isExpanded: boolean;
}

const props = defineProps<TaskInstanceTableRowProps>();
const taskInstance = ref(props.task);

const myScheduler = injectWithCheck(schedulerInjectionKey, 'scheduler not provided!');
const myTaskLog = injectWithCheck(logInjectionKey, 'log not provided!');

// Keep taskInstance in sync if parent replaces the object
watch(
	() => props.task,
	(newTask) => {
		taskInstance.value = newTask;
	},
	{ deep: true }
);

const isExpanded = computed(() => props.isExpanded);

// useLiveTaskStatus expects an array ref of tasks
const tasksRef = ref<TaskInstanceType[] | null | undefined>([taskInstance.value]);

const live = useLiveTaskStatus(tasksRef, myScheduler, myTaskLog, {
	intervalMs: 1500,
	completedWindowMs: 30_000,
});


const {
	start,
	stop,
	refreshAll,
	statusFor,
	lastRunFor,
	isCompleted: liveIsCompleted,
	isRunningNow: liveIsRunning,
	isFailed: liveIsFailed,
	isInactive: liveIsInactive,
} = live;

// Keep tasksRef up to date when this row's task changes
watch(
	taskInstance,
	(t) => {
		tasksRef.value = t ? [t] : [];
		refreshAll();
	},
	{ deep: true }
);

const manualRunUntil = ref<number>(0);
function markManualRun(windowMs = 60_000) {
	manualRunUntil.value = Date.now() + windowMs;
}

// Text shown in the Status column, with manual wording
const statusText = computed(() => {
	const baseRaw = statusFor(taskInstance.value);
	const enabled = taskInstance.value?.schedule?.enabled ?? false;
	const now = Date.now();
	const manualWindowActive = !enabled && now < manualRunUntil.value;

	// If no live status yet, provide simple fallbacks
	const base = baseRaw || (enabled ? 'Checking...' : 'Disabled');

	// Manual-only tasks (no schedule enabled) get special wording
	if (!enabled) {
		const running = liveIsRunning(taskInstance.value);
		const completed = liveIsCompleted(taskInstance.value);

		// While we're in the manual window, be explicit
		if (manualWindowActive) {
			if (running) return 'Running now (manual)';
			if (completed) return 'Completed (manual)';
		}

		// Outside window, still keep "Completed (manual)" instead of plain "Completed"
		if (completed) return 'Completed (manual)';
	}

	return base;
});

// Text shown in the "Last run" column
const lastRunText = computed(() => {
	return lastRunFor(taskInstance.value) ?? "Task hasn't run yet.";
});

// Boolean flags wrapped for the template
const isRunning = computed(() => {
	const enabled = taskInstance.value?.schedule?.enabled ?? false;
	const now = Date.now();
	const manualWindowActive = !enabled && now < manualRunUntil.value;

	if (liveIsRunning(taskInstance.value)) return true;

	if (manualWindowActive && !liveIsCompleted(taskInstance.value)) {
		return true;
	}

	return false;
});

const isCompleted = computed(() => liveIsCompleted(taskInstance.value));
const isFailed = computed(() => liveIsFailed(taskInstance.value));
const isInactive = computed(() => liveIsInactive(taskInstance.value));

// Progress tracking (separate from status)
const progress = ref<number | null>(null);

async function updateProgress(task: TaskInstanceType) {
	try {
		const p = await myScheduler.getTaskProgress(task);
		if (typeof p === 'number' && Number.isFinite(p)) {
			progress.value = p;
		} else {
			progress.value = null;
		}
	} catch (e) {
		console.error('Failed to get progress:', e);
		progress.value = null;
	}
}

const progressBarClass = computed(() => {
	const s = (statusText.value || '').toLowerCase();

	if (s.includes('failed') || s.includes('error')) {
		return 'bg-red-600';
	}

	if (s.includes('completed')) {
		return 'bg-green-600';
	}

	if (
		s.includes('active (running)') ||
		s.includes('running now') ||
		s.includes('starting') ||
		s.includes('activating')
	) {
		return 'bg-green-600';
	}

	if (s.includes('inactive (disabled)') || s.includes('disabled')) {
		return 'bg-slate-400';
	}

	return 'bg-slate-400';
});

// Emits
const emit = defineEmits([
	'runTask',
	'manageSchedule',
	'removeTask',
	'editTask',
	'viewLogs',
	'toggleDetails',
	'viewNotes',
	'stopTask',
]);


async function runTaskBtn() {
	// Mark this as a manual run so wording reflects that
	markManualRun();
	emit('runTask', taskInstance.value);
	refreshAll();
	updateProgress(taskInstance.value);
}

async function stopTaskBtn() {
	emit('stopTask', taskInstance.value);
	refreshAll();
	updateProgress(taskInstance.value);
}

function manageScheduleBtn() {
	emit('manageSchedule', taskInstance.value);
}

function removeTaskBtn() {
	emit('removeTask', taskInstance.value);
}

function editTaskBtn() {
	emit('editTask', taskInstance.value);
}

function viewLogsBtn() {
	emit('viewLogs', taskInstance.value);
}

function viewNotesBtn() {
	emit('viewNotes', taskInstance.value);
}

function toggleTaskDetails() {
	emit('toggleDetails', taskInstance.value.name);
}

// Confirmation dialog loader (shared)
async function loadConfirmationDialog(dialogRef: any) {
	const module = await import('../../components/common/ConfirmationDialog.vue');
	dialogRef.value = module.default;
}

// Enable Task Dialog Logic
const showEnablePrompt = ref(false);
const enableDialog = ref<any>();
const enabling = ref(false);

// Disable Task Dialog Logic
const showDisablePrompt = ref(false);
const disableDialog = ref<any>();
const disabling = ref(false);

const enableYes = async () => {
	enabling.value = true;
	await myScheduler.enableSchedule(taskInstance.value);
	await refreshAll();
	enabling.value = false;
	showEnablePrompt.value = false;
};
const enableNo = () => {
	showEnablePrompt.value = false;
};
const updateShowEnablePrompt = (v: boolean) => {
	showEnablePrompt.value = v;
};

const disableYes = async () => {
	disabling.value = true;
	await myScheduler.disableSchedule(taskInstance.value);
	await refreshAll();
	disabling.value = false;
	showDisablePrompt.value = false;
};
const disableNo = () => {
	showDisablePrompt.value = false;
};
const updateShowDisablePrompt = (v: boolean) => {
	showDisablePrompt.value = v;
};

async function toggleTaskSchedule(event: Event) {
	const intendedValue = !taskInstance.value.schedule.enabled;
	event.preventDefault();

	if (intendedValue) {
		await loadConfirmationDialog(enableDialog);
		showEnablePrompt.value = true;
	} else {
		await loadConfirmationDialog(disableDialog);
		showDisablePrompt.value = true;
	}
}

// Lifecycle: hook into live status engine + optional progress polling
let progressIntervalId: number | undefined;

onMounted(async () => {
	await refreshAll();
	start();

	await updateProgress(taskInstance.value);
	progressIntervalId = window.setInterval(() => {
		updateProgress(taskInstance.value);
	}, 1500);
});

onUnmounted(() => {
	stop();
	if (progressIntervalId) {
		clearInterval(progressIntervalId);
		progressIntervalId = undefined;
	}
});

// Expose for parent components (keeps old API working)
async function updateTaskStatus() {
	await refreshAll();
}
async function fetchLatestLog() {
	await refreshAll();
}

defineExpose({
	updateTaskStatus,
	fetchLatestLog,
	updateProgress,
	markManualRun,
	isCompleted,
	isFailed,
	isInactive,
	isRunning,
});
</script>
