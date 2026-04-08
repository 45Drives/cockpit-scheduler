<template>
    <!-- Details for Automated Snapshot Task -->
    <div v-if="taskInstance.template.name === 'Automated Snapshot Task'" class="grid grid-cols-4 items-left text-left">
        <div class="col-span-1">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>Automated Snapshot Task</b>
            </p>
            <p class="my-2 truncate"
                :title="`Filesystem: ${findValue(taskInstance.parameters, 'filesystem', 'dataset')}`">
                Filesystem: <b>
                    <!-- {{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/ -->
                    {{ findValue(taskInstance.parameters, 'filesystem',
                    'dataset') }}
                </b>
            </p>
            <p v-if="findValue(taskInstance.parameters, 'customName_flag', 'customName_flag')" class="my-2 truncate"
                :title="`Custom Snapshot Name: ${findValue(taskInstance.parameters, 'customName', 'customName')}`">
                Custom Snapshot Name: <b>
                    <!-- {{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/ -->
                    {{ findValue(taskInstance.parameters, 'customName',
                    'customName') }}
                </b>
            </p>
        </div>
        <div class="col-span-1">
            <p class="my-2 truncate"
                :title="`Recursive Snapshots: ${boolToYesNo(findValue(taskInstance.parameters, 'recursive_flag', 'recursive_flag'))}`">
                Recursive Snapshots: <b>{{
                    boolToYesNo(findValue(taskInstance.parameters,
                    'recursive_flag', 'recursive_flag')) }}</b>
            </p>
        </div>
        <div class="col-span-2 row-span-2">
            <p class="mt-2 font-bold">Current Schedules:</p>
            <div v-if="taskInstance.schedule.intervals.length > 0">
                <div v-for="(interval, idx) in taskInstance.schedule.intervals" :key="idx"
                    class="flex flex-col col-span-2 divide divide-y divide-default p-1"
                    :title="`Run ${myScheduler.parseIntervalIntoString(interval)}.`">
                    <p>Run {{ myScheduler.parseIntervalIntoString(interval) }}.</p>
                    <p v-if="interval.retention" class="text-xs text-muted ml-2">
                        Retention:
                        <span v-if="interval.retention.source">
                            {{ interval.retention.source.retentionTime }} {{ interval.retention.source.retentionUnit }}
                        </span>
                        <span v-else-if="interval.retention.destination">
                            {{ interval.retention.destination.retentionTime }} {{ interval.retention.destination.retentionUnit }}
                        </span>
                    </p>
                    <p v-else class="text-xs text-muted ml-2">No retention policy</p>
                </div>
            </div>
            <div v-else>
                <p>No Intervals Currently Scheduled</p>
            </div>
        </div>

    </div>
</template>
<script setup lang="ts">
import { ref } from 'vue';
import { boolToYesNo, injectWithCheck, findValue } from '../../../composables/utility'
import { schedulerInjectionKey } from '../../../keys/injection-keys';

interface AutomatedSnapshotTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<AutomatedSnapshotTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

</script>