<template>
    <!-- Details for SMART Test Task -->
    <div v-if="taskInstance.template.name === 'SMART Test'"
        class="grid grid-cols-4 items-left text-left">
        <div class="col-span-2">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>SMART Test Task</b>
            </p>
            <p class="my-2 truncate" :title="` Test Type: ${upperCaseWord(findValue(taskInstance.parameters, 'testType', 'testType'))}`">
                Test Type: <b>{{ upperCaseWord(findValue(taskInstance.parameters, 'testType', 'testType')) }}</b>
            </p>
            <p class="my-2" :title="`Disks: ${findValue(taskInstance.parameters, 'disks', 'disks')}`">
                Disks: <span v-for="disk, idx in disksArray" class="p-1 mx-1 font-medium border border-default rounded-lg bg-accent">{{ disksArray[idx] }}</span>
            </p>
        </div>

        <div class="col-span-2 row-span-2">
            <p class="my-2 font-bold">Current Schedules:</p>
            <div v-if="taskInstance.schedule.intervals.length > 0"
                v-for="interval, idx in taskInstance.schedule.intervals" :key="idx"
                class="flex flex-row col-span-2 divide divide-y divide-default p-1" :title="`Run ${myScheduler.parseIntervalIntoString(interval)}.`">
                <p>Run {{ myScheduler.parseIntervalIntoString(interval) }}.</p>
            </div>
            <div v-else>
                <p>No Intervals Currently Scheduled</p>
            </div>
        </div>
    
    </div>
</template>

<script setup lang="ts">
import { ref} from 'vue';
import { boolToYesNo, injectWithCheck, findValue, splitAndClean, upperCaseWord } from '../../../composables/utility'
import { schedulerInjectionKey } from '../../../keys/injection-keys';

interface SmartTestTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<SmartTestTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

const disksArray = splitAndClean(findValue(taskInstance.value.parameters, 'disks', 'disks'), true);
</script>