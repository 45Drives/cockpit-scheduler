<template>
	<HoustonAppContainer moduleName="Task Scheduler" :appVersion="appVersion">
		<CenteredCardColumn>
			<CardContainer>
				<SchedulerView />
			</CardContainer>
		</CenteredCardColumn>
	</HoustonAppContainer>
</template>

<script setup lang="ts">
import { ref, provide, onMounted } from 'vue';
import SchedulerView from './views/SchedulerView.vue';
import { ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskInstance, TaskTemplate, RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate } from './models/Tasks';
import { Scheduler } from './models/Scheduler';
import { TaskExecutionLog, TaskExecutionResult } from './models/TaskLog';
import { HoustonAppContainer, CardContainer, CenteredCardColumn } from '@45drives/houston-common-ui';
import { loadingInjectionKey, schedulerInjectionKey, logInjectionKey, taskInstancesInjectionKey, taskTemplatesInjectionKey, truncateTextInjectionKey } from './keys/injection-keys';

const appVersion = __APP_VERSION__;

// Instantiate task templates -> These must corrolate with Template files located in /system_files/opt/45drives/houston/scheduler/templates
function initializeTaskTemplates(): TaskTemplate[] {
	const zfsRepTaskTemplate = new ZFSReplicationTaskTemplate();
	const autoSnapTaskTemplate = new AutomatedSnapshotTaskTemplate();
	const rsyncTaskTemplate = new RsyncTaskTemplate();
	const scrubTaskTemplate = new ScrubTaskTemplate();
	const smartTestTemplate = new SmartTestTemplate();

	return [
		zfsRepTaskTemplate,
		autoSnapTaskTemplate,
		rsyncTaskTemplate,
		scrubTaskTemplate,
		smartTestTemplate
	]
}

const taskTemplates = initializeTaskTemplates();
const taskInstances = ref<TaskInstance[]>([]);
const myScheduler = new Scheduler(taskTemplates, taskInstances.value);
const loading = ref(false);
const truncateText = ref('overflow-hidden whitespace-nowrap text-ellipsis');

const entries = ref<TaskExecutionResult[]>([]);
const myTaskLog = new TaskExecutionLog(entries.value);

onMounted(async () => {
	loading.value = true;
	initializeTaskTemplates();
	await myScheduler.loadTaskInstances();
	loading.value = false;
});

provide(loadingInjectionKey, loading);
provide(schedulerInjectionKey, myScheduler);
provide(logInjectionKey, myTaskLog);
provide(taskInstancesInjectionKey, taskInstances);
provide(taskTemplatesInjectionKey, taskTemplates);
provide(truncateTextInjectionKey, truncateText);
</script>
