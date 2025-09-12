<template>
	<tr :class="isExpanded ? 'border-2 border-red-700 dark:border-red-800 bg-default' : 'border border-default border-collapse '"
		class="grid grid-cols-9 grid-flow-cols w-full text-center items-center rounded-sm p-1">
		<td :title="taskInstance.name"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			{{ taskInstance.name }}
		</td>

		<!-- Status -->
		<td v-if="taskInstance.schedule.enabled" :title="statusText"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span :class="taskStatusClass(statusText)">{{ statusText || 'N/A' }}</span>
		</td>
		<td v-else :title="'Disabled'"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-2">
			<span :class="taskStatusClass(statusText)">{{ statusText || 'N/A' }}</span>
		</td>

		<!-- Scope -->
		<td :title="taskInstance.scope"
			class="truncate text-base font-medium text-default border-r border-default text-left ml-4 col-span-1">
			<span>{{ taskInstance.scope }}</span>
		</td>

		<!-- Last run -->
		<td :title="lastRunText" class="truncate font-medium border-r border-default text-left ml-4 col-span-2">
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
		<td class="truncate text-base font-medium text-default border-default m-1 col-span-1">
			<button v-if="isExpanded" @click="toggleTaskDetails()"
				class="btn text-gray-50 bg-red-700 hover:bg-red-800 dark:hover:bg-red-900 dark:bg-red-800">
				Close Details
			</button>
			<button v-else @click="toggleTaskDetails()" class="btn btn-secondary">View Details</button>
		</td>

		<!-- Expanded details -->
		<td v-if="isExpanded" class="col-span-9 h-full px-2 mx-2 py-1 border-t border-default">
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
import { PlayIcon, PencilIcon, TrashIcon, CalendarDaysIcon, TableCellsIcon,PencilSquareIcon } from '@heroicons/vue/24/outline';
import { injectWithCheck } from '../../composables/utility'
import { schedulerInjectionKey, logInjectionKey } from '../../keys/injection-keys';
import TaskInstanceDetails from './TaskInstanceDetails.vue';
import { useLiveTaskStatus } from '../../composables/useLiveTaskStatus';

interface TaskInstanceTableRowProps {
	task: TaskInstanceType;
	isExpanded: boolean;
}

const props = defineProps<TaskInstanceTableRowProps>();
const taskInstance = ref(props.task);

const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
const myTaskLog = injectWithCheck(logInjectionKey, "log not provided!");

// ── Live status/last-run (same engine as Simple view) ──────────────────────────
const oneTask = computed(() => [taskInstance.value]);
const live = useLiveTaskStatus(oneTask, myScheduler, myTaskLog, {
	intervalMs: 1500,
	formatMs: (ms) => myScheduler.formatLocal(ms),
});

const statusText = computed(() => live.statusFor(taskInstance.value) ?? '—');
const lastRunText = computed(() => live.lastRunFor(taskInstance.value) ?? '—');

// ── Row events ─────────────────────────────────────────────────────────────────
const emit = defineEmits(['runTask', 'manageSchedule', 'removeTask', 'editTask', 'viewLogs', 'toggleDetails', 'viewNotes']);

function runTaskBtn() { emit('runTask', taskInstance.value); }
function manageScheduleBtn() { emit('manageSchedule', taskInstance.value); }
function removeTaskBtn() { emit('removeTask', taskInstance.value); }
function editTaskBtn() { emit('editTask', taskInstance.value); }
function viewLogsBtn() { emit('viewLogs', taskInstance.value); }
function viewNotesBtn() { emit('viewNotes', taskInstance.value); }
function toggleTaskDetails() { emit('toggleDetails', taskInstance.value.name); }

// ── Enable/Disable dialogs ─────────────────────────────────────────────────────
const showEnablePrompt = ref(false);
const enableDialog = ref<any>();
const enabling = ref(false);

/* Generic loading function for Confirmation Dialogs */
async function loadConfirmationDialog(dialogRef) {
	const module = await import('../../components/common/ConfirmationDialog.vue');
	dialogRef.value = module.default;
}

async function showEnableDialog() {
	await loadConfirmationDialog(enableDialog);
	return new Promise((resolve) => {
		showEnablePrompt.value = true;
		const unwatch = watch(showEnablePrompt, (v) => { if (!v) { unwatch(); resolve(enableDialog.value === 'yes'); } });
	});
}

const enableYes = async () => {
	enabling.value = true;
	await myScheduler.enableSchedule(taskInstance.value);
	await live.refreshAll();
	updateShowEnablePrompt(false);
	enabling.value = false;
};
const enableNo = () => updateShowEnablePrompt(false);
const updateShowEnablePrompt = (v: boolean) => { showEnablePrompt.value = v; };

// Disable Task Dialog Logic
const showDisablePrompt = ref(false);
const disableDialog = ref();
const disabling = ref(false);


async function showDisableDialog() {
	await loadConfirmationDialog(disableDialog);
	return new Promise((resolve) => {
		showDisablePrompt.value = true;
		const unwatch = watch(showDisablePrompt, (v) => { if (!v) { unwatch(); resolve(disableDialog.value === 'yes'); } });
	});
}
const disableYes = async () => {
	disabling.value = true;
	await myScheduler.disableSchedule(taskInstance.value);
	await live.refreshAll();
	updateShowDisablePrompt(false);
	disabling.value = false;
};
const disableNo = () => updateShowDisablePrompt(false);
const updateShowDisablePrompt = (v: boolean) => { showDisablePrompt.value = v; };

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

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => { await live.refreshAll(); live.start(); });
onUnmounted(() => live.stop());
watch(taskInstance, () => { if (taskInstance.value) live.refreshAll(); });

// ── Helpers ────────────────────────────────────────────────────────────────────
function taskStatusClass(status?: string) {
	if (status) {
		const s = status.toLowerCase();
		if (s.includes('active') || s.includes('starting') || s.includes('completed')) return 'text-success';
		if (s.includes('inactive') || s.includes('disabled')) return 'text-warning';
		if (s.includes('failed')) return 'text-danger';
		if (s.includes('no schedule found') || s.includes('not scheduled')) return 'text-muted';
	}
	return '';
}

defineExpose({
	async updateTaskStatus() { await live.refreshAll(); },
	async fetchLatestLog() { await live.refreshAll(); },
});
</script>