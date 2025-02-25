<template>
    <div>
        <ZfsRepTaskDetails v-if="template.name == 'ZFS Replication Task'" ref="activeComponent" :task="props.task" />
        <AutomatedSnapshotTaskDetails v-else-if="template.name == 'Automated Snapshot Task'" ref="activeComponent"
            :task="props.task" />
        <RsyncTaskDetails v-else-if="template.name == 'Rsync Task'" ref="activeComponent" :task="props.task" />
        <ScrubTaskDetails v-else-if="template.name == 'Scrub Task'" ref="activeComponent" :task="props.task" />
        <SmartTestTaskDetails v-else-if="template.name == 'SMART Test'" ref="activeComponent" :task="props.task" />
        <CloudSyncTaskDetails v-else-if="template.name == 'Cloud Sync Task'" ref="activeComponent" :task="props.task" />
        <CustomTaskDetails v-else-if="template.name == 'Custom Task'" ref="activeComponent" :task="props.task" />
    </div>
    <div v-if="task.notes !== ''" class="text-left border-2 border-default mt-1 p-2 text-medium w-full bg-well">
        <p><b>Notes:</b></p>
        <p class="mt-1 p-2 bg-default rounded-md">
            {{ task.notes }}
        </p>
    </div>
</template>
<script setup lang="ts">

import { ref, computed } from 'vue';
import ZfsRepTaskDetails from './task-details/ZfsRepTaskDetails.vue'
import AutomatedSnapshotTaskDetails from './task-details/AutomatedSnapshotTaskDetails.vue'
import RsyncTaskDetails from './task-details/RsyncTaskDetails.vue';
import ScrubTaskDetails from './task-details/ScrubTaskDetails.vue';
import SmartTestTaskDetails from './task-details/SmartTestTaskDetails.vue';
import CloudSyncTaskDetails from './task-details/CloudSyncTaskDetails.vue';
import CustomTaskDetails from './task-details/CustomTaskDetails.vue';

interface TaskInstanceDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<TaskInstanceDetailsProps>();

const template = computed(() => props.task.template);

const activeComponent = ref<InstanceType<typeof ZfsRepTaskDetails | typeof AutomatedSnapshotTaskDetails | typeof RsyncTaskDetails | typeof ScrubTaskDetails | typeof SmartTestTaskDetails | typeof CloudSyncTaskDetails | typeof CustomTaskDetails> | null>(null);

</script>