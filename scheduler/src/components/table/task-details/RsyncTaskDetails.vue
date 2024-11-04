<template>
    <!-- Details for Rsync Task -->
    <div v-if="taskInstance.template.name === 'Rsync Task'" class="grid grid-cols-4 items-left text-left">
        <div class="col-span-1">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>Rsync Task</b>
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
                :title="`Target Path: ${findValue(taskInstance.parameters, 'target_info', 'path')}`">
                Target Path: <b>{{ findValue(taskInstance.parameters, 'target_info', 'path') }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Send Type: ${findValue(taskInstance.parameters, 'target_info', 'host') !== '' ? 'Remote' : 'Local'}`">
                Transfer Type:
                <b v-if="findValue(taskInstance.parameters, 'target_info', 'host') !== ''">Remote</b>
                <b v-if="findValue(taskInstance.parameters, 'target_info', 'host') === ''">Local</b>
            </p>
            <p class="my-2" v-if="findValue(taskInstance.parameters, 'target_info', 'host') !== ''">
                <span class="truncate"
                    :title="`Remote SSH Host: ${findValue(taskInstance.parameters, 'target_info', 'host')}`">
                    Remote SSH Host: <b>{{ findValue(taskInstance.parameters, 'target_info', 'host') }}</b>
                </span>
                <span class="truncate"
                    :title="`Remote SSH Port: ${findValue(taskInstance.parameters, 'target_info', 'port')}`">
                    Remote SSH Port: : <b>{{ findValue(taskInstance.parameters, 'target_info', 'port') }}</b>
                </span>
            </p>
        </div>
        <div class="col-span-1">

            <p class="my-2 truncate"
                :title="`Archive Mode: ${boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'archive_flag'))}`">
                Archive Mode: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'archive_flag'))
                    }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Recursive: ${boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'recursive_flag'))}`">
                Recursive: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'recursive_flag'))
                    }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Compressed: ${boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'compressed_flag'))}`">
                Compressed: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'compressed_flag'))
                    }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Bandwidth Limit: ${((findValue(taskInstance.parameters, 'rsyncOptions', 'bandwidth_limit_kbps') !== 0 ? `${findValue(taskInstance.parameters, 'rsyncOptions', 'bandwidth_limit_kbps')} kb/s` : 'No'))}`">
                Bandwidth Limit: <b>{{ ((findValue(taskInstance.parameters, 'rsyncOptions', 'bandwidth_limit_kbps') !==
                    0 ? `${findValue(taskInstance.parameters, 'rsyncOptions', 'bandwidth_limit_kbps')} kb/s` : 'No'))
                    }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Parallel Threads: ${(findValue(taskInstance.parameters, 'rsyncOptions', 'parallel_threads') !== 0 ? findValue(taskInstance.parameters, 'rsyncOptions', 'parallel_threads') : 'No')}`">
                Parallel Threads: <b>{{ (findValue(taskInstance.parameters, 'rsyncOptions', 'parallel_threads') !== 0 ?
                    findValue(taskInstance.parameters, 'rsyncOptions', 'parallel_threads') : 'No') }}</b>
            </p>
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

interface RsyncTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<RsyncTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

</script>