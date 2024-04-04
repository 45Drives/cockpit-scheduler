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
import { ZFSReplicationTaskTemplate, TaskInstance, TaskTemplate } from './models/Tasks';
import { Scheduler } from './models/Scheduler';

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



// Example usage:
// taskTemplates.forEach(template => {
//     console.log(`Task Template: ${template.name}`);
//     console.log('Parameter Schema:');
//     console.log(template.parameterSchema); // Output the object directly
//     // Alternatively, you can access individual properties
//     console.log(`Label: ${template.parameterSchema.label}`);
//     console.log(`Key: ${template.parameterSchema.key}`);
//     console.log('Children:');
//     template.parameterSchema.children.forEach(child => {
//         console.log(`Child Label: ${child.label}`);
//         console.log(`Child Key: ${child.key}`);
// 		child.children.forEach(child => {
// 			console.log(`Child Label: ${child.label}`);
// 			console.log(`Child Key: ${child.key}`);
// 			// Output additional properties of the child if needed
// 		});
//     });
// });


/* export async function getTaskTemplates() {
	try {
		//['/usr/bin/env', 'python3', '-c', script, ...args ]
		const state = useSpawn([]);
		const templates = (await state.promise()).stdout;
		return templates;
	} catch (state) {
		console.error(errorString(state));
		return null;
	}

}

export async function loadTaskTemplates() {
	try {
		const rawJSON = await getTaskTemplates();
		const parsedJSON = JSON.parse(rawJSON);

		for (let i = 0; i < parsedJSON.length; i++) {
			const template = {
				
			}

			templateList.value.push(template);
		}
	} catch (error) {
		console.error("An error occurred getting templates:", error);
	}
} */

onMounted(() => {

});

provide('scheduler', myScheduler);
provide('task-templates', taskTemplates);
provide('notifications', notifications);
provide('notification-fifo', props.notificationFIFO);
</script>

	