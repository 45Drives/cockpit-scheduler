<template>
	<div class="min-h-screen h-full w-full min-w-fit flex flex-col bg-default overflow-auto">
		<HoustonHeader moduleName="Houston Scheduler" sourceURL=""
			issuesURL="" :pluginVersion="Number(pluginVersion)"
			:infoNudgeScrollbar="true" />
		<SchedulerView/>
	</div>
</template>

<script setup lang="ts">
import { useSpawn, errorString } from '@45drives/cockpit-helpers';
import { reactive, ref, computed, provide, onMounted } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import { pluginVersion } from "./version";
import { HoustonHeader } from "@45drives/cockpit-vue-components";
import { FIFO } from '@45drives/cockpit-helpers';
import SchedulerView from './views/SchedulerView.vue';
import { ZFSReplicationTaskTemplate, TaskInstance, TaskTemplate, Scheduler, TaskExecutionLog, TaskExecutionResult } from './models/Classes';

interface AppProps {
	notificationFIFO: FIFO;
}

const props = defineProps<AppProps>();
const notifications = ref<any>(null);
// const templateList = ref<TaskTemplateType[]>([]);

function initializeTaskTemplates(): TaskTemplate[] {
	const zfsRepTaskTemplate = new ZFSReplicationTaskTemplate();

	return [
		zfsRepTaskTemplate,
	]
}

// Instantiate task templates
const taskTemplates = initializeTaskTemplates();
const taskInstances = ref<TaskInstance[]>([]);
const myScheduler = new Scheduler(taskTemplates, taskInstances.value)

const dummyTaskInstances = ref<TaskInstanceType[]>([
    {
        name: 'ZFS Replication Task 1',
        template: taskTemplates[0], // Reference to the ZFS Replication TaskTemplate
        parameters: {
            label: 'zfs rep task config',
            key: 'zfs_rep_task_1',
            children: []
        },
        schedule: {
            enabled: true,
            intervals: []
        }
    },
    // Add more TaskInstances as necessary
]);

const entries = ref<TaskExecutionResult[]>([]);
const myTaskLog = new TaskExecutionLog(entries.value);

onMounted(() => {
	myScheduler.loadTaskInstances();
});

provide('scheduler', myScheduler);
provide('task-instances', dummyTaskInstances);
provide('task-templates', taskTemplates);
provide('notifications', notifications);
provide('notification-fifo', props.notificationFIFO);
</script>

	