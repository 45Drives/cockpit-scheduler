<template>
	<HoustonAppContainer moduleName="Houston Scheduler">
		<CenteredCardColumn>
			<CardContainer>
				<SchedulerView/>
			</CardContainer>
		</CenteredCardColumn>
		
	</HoustonAppContainer>		
</template>

<script setup lang="ts">
import { ref, provide, onMounted } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import SchedulerView from './views/SchedulerView.vue';
import { ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskInstance, TaskTemplate, } from './models/Tasks';
import { Scheduler } from './models/Scheduler';
import { TaskExecutionLog, TaskExecutionResult } from './models/TaskLog';
import { HoustonAppContainer, CardContainer, CenteredCardColumn } from 'houston-common-ui'


function initializeTaskTemplates(): TaskTemplate[] {
	const zfsRepTaskTemplate = new ZFSReplicationTaskTemplate();
	const autoSnapTaskTemplate = new AutomatedSnapshotTaskTemplate();
	return [
		zfsRepTaskTemplate,
		autoSnapTaskTemplate,
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
	await myScheduler.loadTaskInstances();;
	loading.value = false;
});

provide('loading', loading);
provide('scheduler', myScheduler);
provide('log', myTaskLog);
provide('task-instances', taskInstances);
provide('task-templates', taskTemplates);
</script>

	