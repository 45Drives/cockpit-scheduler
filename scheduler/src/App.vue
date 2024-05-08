<template>
	<div class="min-h-screen h-full w-full min-w-fit flex flex-col bg-default overflow-auto">
		<HoustonHeader moduleName="Houston Scheduler" sourceURL=""
			issuesURL="" :pluginVersion="Number(pluginVersion)"
			:infoNudgeScrollbar="true" />
		<SchedulerView class="z-0"/>
		<Teleport to="body">
			<Notifications
                :notificationFIFO="notificationFIFO"
                ref="notifications" class="z-9999"
            />
		</Teleport>
		
	</div>
</template>

<script setup lang="ts">
import { useSpawn, errorString } from '@45drives/cockpit-helpers';
import { reactive, ref, computed, provide, onMounted, Teleport } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import { pluginVersion } from "./version";
import { HoustonHeader } from "@45drives/cockpit-vue-components";
import { FIFO } from '@45drives/cockpit-helpers';
import Notifications from "./components/common/Notifications.vue";
import SchedulerView from './views/SchedulerView.vue';
import { ZFSReplicationTaskTemplate, TaskInstance, TaskTemplate, Scheduler, TaskExecutionLog, TaskExecutionResult } from './models/Classes';

interface AppProps {
	notificationFIFO: FIFO;
}

const props = defineProps<AppProps>();
const notifications = ref<any>(null);
// const notificationFIFO = ref<FIFO>(props.notificationFIFO);

function initializeTaskTemplates(): TaskTemplate[] {
	const zfsRepTaskTemplate = new ZFSReplicationTaskTemplate();

	return [
		zfsRepTaskTemplate,
	]
}

// Instantiate task templates
const taskTemplates = initializeTaskTemplates();
const taskInstances = ref<TaskInstance[]>([]);
const myScheduler = new Scheduler(taskTemplates, taskInstances.value);
const loading = ref(false);

const entries = ref<TaskExecutionResult[]>([]);
const myTaskLog = new TaskExecutionLog(entries.value);

onMounted(async () => {
	loading.value = true;
	initializeTaskTemplates();
	await myScheduler.loadTaskInstances();
	await myTaskLog.loadEntries();
	loading.value = false;
});

provide('loading', loading);
provide('scheduler', myScheduler);
provide('log', myTaskLog);
provide('task-instances', taskInstances);
provide('task-templates', taskTemplates);
provide('notifications', notifications);
provide('notification-fifo', props.notificationFIFO);
</script>

	