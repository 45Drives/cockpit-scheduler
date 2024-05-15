<template>
	<div class="min-h-screen h-full w-full min-w-fit flex flex-col bg-default overflow-auto">
		<!-- <HoustonHeader moduleName="Houston Scheduler" sourceURL=""
			issuesURL="" :pluginVersion="Number(pluginVersion)"
			:infoNudgeScrollbar="true" /> -->
		<!-- 	<Suspense>
				<template #default> -->
					<HoustonAppContainer moduleName="Houston Scheduler" >
						<!-- <SchedulerView class="z-0"/> -->
						test
					</HoustonAppContainer>
				<!-- </template>
				<template #fallback>
					<div>
						not working
					</div>
				</template>
			</Suspense> -->
		<!-- <Teleport to="body">
			<Notifications
                :notificationFIFO="notificationFIFO"
                ref="notifications" class="z-9999"
            />
		</Teleport> -->
	</div>
	
	
			
</template>

<script setup lang="ts">
import { ref, provide, onMounted, Teleport } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import { pluginVersion } from "./version";
import { HoustonHeader } from "@45drives/cockpit-vue-components";
import SchedulerView from './views/SchedulerView.vue';
import { ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskInstance, TaskTemplate, Scheduler, TaskExecutionLog, TaskExecutionResult } from './models/Classes';
import { HoustonAppContainer } from 'houston-common-ui'


// function initializeTaskTemplates(): TaskTemplate[] {
// 	const zfsRepTaskTemplate = new ZFSReplicationTaskTemplate();
// 	const autoSnapTaskTemplate = new AutomatedSnapshotTaskTemplate();
// 	return [
// 		zfsRepTaskTemplate,
// 		autoSnapTaskTemplate,
// 	]
// }

// // Instantiate task templates
// const taskTemplates = initializeTaskTemplates();
// const taskInstances = ref<TaskInstance[]>([]);
// const myScheduler = new Scheduler(taskTemplates, taskInstances.value);
// const loading = ref(false);

// const entries = ref<TaskExecutionResult[]>([]);
// const myTaskLog = new TaskExecutionLog(entries.value);

// onMounted(async () => {
// 	loading.value = true;
// 	initializeTaskTemplates();
// 	await myScheduler.loadTaskInstances();;
// 	loading.value = false;
// });

// provide('loading', loading);
// provide('scheduler', myScheduler);
// provide('log', myTaskLog);
// provide('task-instances', taskInstances);
// provide('task-templates', taskTemplates);
</script>

	