<template>
    <!-- Details for Custom Task -->
    <div v-if="taskInstance.template.name === 'Custom Task'"
        class="grid grid-cols-4 items-left text-left">
        <div class="col-span-1">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>Custom Task</b>
            </p>
            <!-- <p class="my-2 truncate" :title="`Pool: ${findValue(taskInstance.parameters, 'pool', 'pool')}`">
                Pool: <b>
                    {{ findValue(taskInstance.parameters, 'pool', 'pool') }}
                </b>
            </p> -->

        </div>
        <div class="col-span-1">
           
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
    import { boolToYesNo, injectWithCheck, findValue } from '../../../composables/utility'
    import { schedulerInjectionKey } from '../../../keys/injection-keys';
    
    interface CustomTaskDetailsProps {
        task: TaskInstanceType;
    }
    
    const props = defineProps<CustomTaskDetailsProps>();
    const taskInstance = ref(props.task);
    console.log("Custom Task Details: props ", taskInstance )
    const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
    
    </script>
