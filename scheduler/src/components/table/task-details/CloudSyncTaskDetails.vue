<template>
    <!-- Details for Cloud Sync Task -->
    <div v-if="taskInstance.template.name === 'Cloud Sync Task'" class="grid grid-cols-4 items-left text-left">
        <div class="col-span-1">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>Cloud Sync Task</b>
            </p>
            <p class="my-2 truncate"
                :title="`Direction: ${upperCaseWord(findValue(taskInstance.parameters, 'direction', 'direction'))}`">
                Direction: <b>{{ upperCaseWord(findValue(taskInstance.parameters, 'direction', 'direction')) }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Local Path: ${findValue(taskInstance.parameters, 'local_path', 'local_path')}`">
                Local Path: <b>{{ findValue(taskInstance.parameters, 'local_path', 'local_path') }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Target Remote: ${findValue(taskInstance.parameters, 'cloud_sync_remote', 'cloud_sync_remote')}`">
                Target Remote: <b>{{ findValue(taskInstance.parameters, 'cloud_sync_remote', 'cloud_sync_remote') }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Target Path: ${findValue(taskInstance.parameters, 'target_info', 'path')}`">
                Target Path: <b>{{ findValue(taskInstance.parameters, 'target_info', 'path') }}</b>
            </p>
        </div>
        <div class="col-span-1">


        </div>
        <div class="col-span-2 row-span-2">
            <p class="my-2 font-bold">Current Schedules:</p>
            <div v-if="taskInstance.schedule.intervals.length > 0"
                v-for="interval, idx in taskInstance.schedule.intervals" :key="idx"
                class="flex flex-row col-span-2 divide divide-y divide-default p-1"
                :title="`Run ${myScheduler.parseIntervalIntoString(interval)}.`">
                <p>Run {{ myScheduler.parseIntervalIntoString(interval) }}.</p>
            </div>
            <div v-else>
                <p>No Intervals Currently Scheduled</p>
            </div>
        </div>
    </div>
</template>
<script setup lang="ts">
import { ref } from 'vue';
import { boolToYesNo, injectWithCheck, findValue, upperCaseWord } from '../../../composables/utility'
import { schedulerInjectionKey } from '../../../keys/injection-keys';

interface CloudSyncTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<CloudSyncTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

</script>