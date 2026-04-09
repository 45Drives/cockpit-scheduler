<template>
    <div class="space-y-4 text-left">
        <!-- Task-specific metadata -->
        <ZfsRepTaskDetails v-if="template.name == 'ZFS Replication Task'" ref="activeComponent" :task="props.task" />
        <AutomatedSnapshotTaskDetails v-else-if="template.name == 'Automated Snapshot Task'" ref="activeComponent"
            :task="props.task" />
        <RsyncTaskDetails v-else-if="template.name == 'Rsync Task'" ref="activeComponent" :task="props.task" />
        <ScrubTaskDetails v-else-if="template.name == 'Scrub Task'" ref="activeComponent" :task="props.task" />
        <SmartTestTaskDetails v-else-if="template.name == 'SMART Test'" ref="activeComponent" :task="props.task" />
        <CloudSyncTaskDetails v-else-if="template.name == 'Cloud Sync Task'" ref="activeComponent"
            :task="props.task" />
        <CustomTaskDetails v-else-if="template.name == 'Custom Task'" ref="activeComponent" :task="props.task" />

        <!-- Schedules section (full width) -->
        <DetailSection title="Current Schedules">
            <div v-if="task.schedule.intervals.length > 0" class="space-y-2">
                <ScheduleCard v-for="(interval, idx) in task.schedule.intervals" :key="idx" :index="idx"
                    :showBadge="task.schedule.intervals.length > 1"
                    :description="myScheduler.parseIntervalIntoString(interval)" :retention="interval.retention" />
            </div>
            <p v-else class="text-sm text-muted">No Intervals Currently Scheduled</p>
        </DetailSection>

        <!-- Notes section (full width) -->
        <DetailSection v-if="task.notes !== ''" title="Notes">
            <p class="text-sm text-default bg-default rounded-md p-3 break-words">
                {{ task.notes }}
            </p>
        </DetailSection>
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
import DetailSection from '../common/DetailSection.vue';
import ScheduleCard from '../common/ScheduleCard.vue';
import { injectWithCheck } from '../../composables/utility';
import { schedulerInjectionKey } from '../../keys/injection-keys';

interface TaskInstanceDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<TaskInstanceDetailsProps>();

const template = computed(() => props.task.template);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

const activeComponent = ref<InstanceType<typeof ZfsRepTaskDetails | typeof AutomatedSnapshotTaskDetails | typeof RsyncTaskDetails | typeof ScrubTaskDetails | typeof SmartTestTaskDetails | typeof CloudSyncTaskDetails | typeof CustomTaskDetails> | null>(null);

</script>