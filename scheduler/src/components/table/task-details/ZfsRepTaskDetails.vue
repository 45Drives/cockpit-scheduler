<template>
    <!-- Details for ZFS Replication Task -->
    <div v-if="taskInstance.template.name === 'ZFS Replication Task'"
        class="grid grid-cols-4 items-left text-left">
        <div class="col-span-1">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>ZFS Replication Task</b>
            </p>
            <p class="my-2 truncate" :title="`Send Type: ${findValue(taskInstance.parameters, 'destDataset', 'host') !== '' ? 'Remote' : 'Local'}`">
                Send Type:
                <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">Remote</b>
                <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') === ''">Local</b>
            </p>
            <p class="my-2 truncate" :title="`Source: ${findValue(taskInstance.parameters, 'sourceDataset', 'dataset')}`">
                Source: <b>
                    <!-- {{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/ -->
                    {{ findValue(taskInstance.parameters, 'sourceDataset',
                        'dataset') }}
                </b>
            </p>
            <p class="my-2 truncate" :title="`Source Snapshots to Keep: ${findValue(taskInstance.parameters, 'snapRetention', 'source')}`">
                Source Snapshots to Keep: <b>
                    {{ findValue(taskInstance.parameters, 'snapRetention',
                        'source') }}
                </b>
            </p>
            <p class="my-2"
                v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">
                <p class="truncate" :title="`Remote SSH Host: ${findValue(taskInstance.parameters,'destDataset', 'host')}`">
                    Remote SSH Host: <b>{{ findValue(taskInstance.parameters,'destDataset', 'host') }}</b>
                </p>
                <p class="truncate" :title="`Remote SSH Port: ${findValue(taskInstance.parameters,'destDataset', 'port')}`">
                    Remote SSH Port: : <b>{{ findValue(taskInstance.parameters,'destDataset', 'port') }}</b>
                </p>        
            </p>
        </div>
        <div class="col-span-1">
            <p class="my-2 truncate" 
            :title="`Compression: ${findValue(taskInstance.parameters, 'sendOptions', 'raw_flag') ? 'Raw' : findValue(taskInstance.parameters, 'sendOptions', 'compressed_flag') ? 'Compressed' : 'None'}`">
                Compression: <b>{{ findValue(taskInstance.parameters,
                    'sendOptions', 'raw_flag') ? 'Raw' :
                    findValue(taskInstance.parameters, 'sendOptions',
                        'compressed_flag') ? 'Compressed' : 'None' }}</b>
            </p>
            <p class="my-2 truncate" 
            :title="`Recursive Send: ${boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'recursive_flag'))}`">
                Recursive Send: <b>{{
                    boolToYesNo(findValue(taskInstance.parameters,
                        'sendOptions', 'recursive_flag')) }}</b>
            </p>
            <p class="my-2 truncate" :title="`Destination: ${findValue(taskInstance.parameters, 'destDataset', 'dataset')}`">
                Destination: <b>
                    <!-- {{ findValue(taskInstance.parameters, 'destDataset', 'pool') }}/ -->
                    {{ findValue(taskInstance.parameters, 'destDataset',
                        'dataset') }}
                </b>
            </p>
            <p class="my-2 truncate" :title="`Destination Snapshots to Keep: ${findValue(taskInstance.parameters, 'snapRetention', 'destination')}`">
                Destination Snapshots to Keep: <b>
                    {{ findValue(taskInstance.parameters, 'snapRetention',
                        'destination') }}
                </b>
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
import { boolToYesNo, injectWithCheck, findValue } from '../../../composables/utility'
import { schedulerInjectionKey } from '../../../keys/injection-keys';

interface ZfsRepTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<ZfsRepTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

</script>