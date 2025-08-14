<template>
	<!-- <SimplifiedView v-if="isSimple" /> -->
	<router-view v-if="isSimple" />
	<NotificationView v-if="isSimple" />

	<HoustonAppContainer v-else moduleName="Task Scheduler" :appVersion="appVersion">
		<CenteredCardColumn>
			<CardContainer>
				<SchedulerView />
			</CardContainer>
		</CenteredCardColumn>
	</HoustonAppContainer>
</template>

<script setup lang="ts">
import { ref, provide, onMounted, onUnmounted } from 'vue';
import SchedulerView from './views/SchedulerView.vue';
import { ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskInstance, TaskTemplate, RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate, CustomTaskTemplate, CloudSyncTaskTemplate} from './models/Tasks';
import { Scheduler } from './models/Scheduler';
import { TaskExecutionLog, TaskExecutionResult } from './models/TaskLog';
import { HoustonAppContainer, CardContainer, CenteredCardColumn, NotificationView } from '@45drives/houston-common-ui'
import { loadingInjectionKey, schedulerInjectionKey, logInjectionKey, taskInstancesInjectionKey, taskTemplatesInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey, truncateTextInjectionKey } from './keys/injection-keys';
import { RemoteManager } from './models/RemoteManager';
import { CloudSyncRemote } from './models/CloudSync';
import { router } from './router';

const appVersion = __APP_VERSION__;

const isSimple = ref(false)
const updateFlag = () => {
	const qs = new URLSearchParams(window.location.search);
	const simpleQ = qs.get('simple') === '1';
	const simpleHash = location.hash.startsWith('#/simple') || location.hash === '#simple'; // support both
	isSimple.value = simpleQ || simpleHash;

	// Optional: only force-route when the query flag is used
	if (simpleQ && !location.hash.startsWith('#/simple')) {
		router.replace('/simple');
	}
};

onMounted(() => {
	updateFlag()
	window.addEventListener('popstate', updateFlag)
	window.addEventListener('hashchange', updateFlag)
})
onUnmounted(() => {
	window.removeEventListener('popstate', updateFlag)
	window.removeEventListener('hashchange', updateFlag)
})

// Instantiate task templates -> These must corrolate with Template files located in /system_files/opt/45drives/houston/scheduler/templates
function initializeTaskTemplates(): TaskTemplate[] {
	const zfsRepTaskTemplate = new ZFSReplicationTaskTemplate();
	const autoSnapTaskTemplate = new AutomatedSnapshotTaskTemplate();
	const rsyncTaskTemplate = new RsyncTaskTemplate();
	const scrubTaskTemplate = new ScrubTaskTemplate();
	const smartTestTemplate = new SmartTestTemplate();
	const cloudSyncTaskTemplate = new CloudSyncTaskTemplate();
	const customTaskTemplate = new CustomTaskTemplate();
	
	return [
		zfsRepTaskTemplate,
		autoSnapTaskTemplate,
		rsyncTaskTemplate,
		scrubTaskTemplate,
		smartTestTemplate,
		cloudSyncTaskTemplate,
		customTaskTemplate
	]
}

const taskTemplates = initializeTaskTemplates();
const taskInstances = ref<TaskInstance[]>([]);
const cloudSyncRemotes = ref<CloudSyncRemote[]>([]);
const myScheduler = new Scheduler(taskTemplates, taskInstances.value);
const myRemoteManager = new RemoteManager(cloudSyncRemotes.value);
const loading = ref(false);
const truncateText = ref('overflow-hidden whitespace-nowrap text-ellipsis');

const entries = ref<TaskExecutionResult[]>([]);
const myTaskLog = new TaskExecutionLog(entries.value);

onMounted(async () => {
	loading.value = true;
	initializeTaskTemplates();
	await myScheduler.loadTaskInstances();
	await myRemoteManager.getRemotes();
	loading.value = false;
});

provide(loadingInjectionKey, loading);
provide(schedulerInjectionKey, myScheduler);
provide(remoteManagerInjectionKey, myRemoteManager);
provide(rcloneRemotesInjectionKey, cloudSyncRemotes);
provide(logInjectionKey, myTaskLog);
provide(taskInstancesInjectionKey, taskInstances);
provide(taskTemplatesInjectionKey, taskTemplates);
provide(truncateTextInjectionKey, truncateText);
provide(truncateTextInjectionKey, truncateText);
</script>
