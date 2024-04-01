<template>
	<div>
		<div class="w-full h-dvh min-h-dvh overflow-visible bg-default text-default">
			<div class="p-2">
				<Dashboard/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, Ref, provide, watchEffect } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import Dashboard from '../components/dashboard/Dashboard.vue';
import { Scheduler } from '../models/Scheduler';

interface SchedulerProps {
  	tag: string;
}

const props = defineProps<SchedulerProps>();

const taskTemplates = ref<TaskTemplate[]>([
    {
        name: 'ZFS Replication Task',
        parameterSchema: {
            label: 'ZFS Replication Config',
            key: 'zfs_replication', // Unique key for the parameter schema
            children: [
                { label: 'Source', key: 'source', children: []},
                { label: 'Destination', key: 'dest', children: []},
                { label: 'Compression', key: 'compression', children: []},
                // Add other parameters as needed
            ]
        }
    },
    // Add more TaskTemplates as necessary
]);


const taskInstances = ref<TaskInstance[]>([
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


provide('task-instances', taskInstances);
provide('task-templates', taskTemplates);

</script> 