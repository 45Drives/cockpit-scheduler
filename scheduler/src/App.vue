<template>
	<!-- <SimplifiedView v-if="isSimple" /> -->
	<router-view v-if="isSimple" v-slot="{ Component, route }">
		<keep-alive include="SimpleTaskForm">
			<component :is="Component" :key="(route.query.session as string) || (route.name as string)" />
		</keep-alive>
	</router-view>

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
import { ref, provide, onMounted, onUnmounted, watch } from 'vue';
import SchedulerView from './views/SchedulerView.vue';
import {
	ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskInstance, TaskTemplate,
	RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate, CustomTaskTemplate, CloudSyncTaskTemplate
} from './models/Tasks';
import { Scheduler } from './models/Scheduler';
import { TaskExecutionLog, TaskExecutionResult } from './models/TaskLog';
import { HoustonAppContainer, CardContainer, CenteredCardColumn, NotificationView } from '@45drives/houston-common-ui'
import {
	loadingInjectionKey, schedulerInjectionKey, logInjectionKey, taskInstancesInjectionKey,
	taskTemplatesInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey, truncateTextInjectionKey
} from './keys/injection-keys';
import { RemoteManager } from './models/RemoteManager';
import { CloudSyncRemote } from './models/CloudSync';
import { router } from './router';
import { currentUserIsPrivileged } from './composables/utility';

const appVersion = __APP_VERSION__;

const isSimple = ref(false)

const updateFlag = () => {
	const qs = new URLSearchParams(window.location.search);
	const simpleQ = qs.get('simple') === '1';
	const simpleHash = location.hash.startsWith('#/simple') || location.hash === '#simple'; // support both
	isSimple.value = simpleQ || simpleHash;

	if (simpleQ && !location.hash.startsWith('#/simple')) {
		router.replace('/simple');
	}
};

// Build the full set
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

// Restrict set for non-privileged users
function filterTemplatesForPrivilege(templates: TaskTemplate[], isAdmin: boolean): TaskTemplate[] {
	if (isAdmin) return templates;
	return templates.filter(t => (t instanceof RsyncTaskTemplate) || (t instanceof CloudSyncTaskTemplate));
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

const syncSimpleModeClass = () => {
	const root = document.documentElement;
	if (isSimple.value) {
		root.classList.add('simple-mode');
	} else {
		root.classList.remove('simple-mode');
	}
};

onMounted(async () => {
	updateFlag();
	syncSimpleModeClass();

	window.addEventListener('popstate', updateFlag);
	window.addEventListener('hashchange', updateFlag);

	watch(isSimple, () => syncSimpleModeClass(), { immediate: true });

	loading.value = true;

	const isAdmin = await currentUserIsPrivileged();
	const filtered = filterTemplatesForPrivilege([...taskTemplates], isAdmin);
	taskTemplates.splice(0, taskTemplates.length, ...filtered);

	await myScheduler.init();

	// Load tasks + remotes in parallel
	await Promise.all([
		myScheduler.loadTaskInstances(),
		myRemoteManager.getRemotes(),
	]);

	loading.value = false;
});

onUnmounted(() => {
	window.removeEventListener('popstate', updateFlag)
	window.removeEventListener('hashchange', updateFlag)
})

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
