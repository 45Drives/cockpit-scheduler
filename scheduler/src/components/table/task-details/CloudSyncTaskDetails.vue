<template>
    <!-- Details for Cloud Sync Task -->
    <div v-if="taskInstance.template.name === 'Cloud Sync Task'" class="grid grid-cols-4 items-left text-left">
        <div class="col-span-1">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>Cloud Sync Task</b>
            </p>
            <p class="my-2 truncate"
                :title="`Direction: ${upperCaseWord(findValue(taskInstance.parameters, 'type', 'type'))}`">
                Transfer Type: <b>{{ upperCaseWord(findValue(taskInstance.parameters, 'type', 'type')) }} ({{
                    upperCaseWord(findValue(taskInstance.parameters, 'direction', 'direction')) }})</b>
            </p>
            <p class="my-2 truncate"
                :title="`Local Path: ${findValue(taskInstance.parameters, 'local_path', 'local_path')}`">
                Local Path: <b>{{ findValue(taskInstance.parameters, 'local_path', 'local_path') }}</b>
            </p>
            <p v-if="cloudRemote" class="my-2 truncate" :title="`Target Remote: ${cloudRemote.name}`">
                Rclone Remote: <b>{{ cloudRemote.name }}</b>
               <!-- <div class="rounded-full bg-white w-5 h-5">
                        <img :src="getProviderLogo(undefined, remote)" alt="provider-logo"
                            class="inline-block w-4 h-4" />
                    </div> -->
                <img v-if="cloudRemote" :src="getProviderLogo(undefined, cloudRemote)" alt="provider-logo"
                    class="inline-block w-5 h-5 ml-2 -mt-1" :title="`Provider: ${cloudRemote.getProviderName()}`" />
            </p>
            <p v-else>
                Loading Rclone Remote...
            </p>
            <p class="my-2 truncate"
                :title="`Target Path: ${findValue(taskInstance.parameters, 'target_path', 'target_path')}`">
                Target Path: <b>{{ findValue(taskInstance.parameters, 'target_path', 'target_path') }}</b>
            </p>
            <p class="my-2 truncate"
                v-if="(findValue(taskInstance.parameters, 'rcloneOptions', 'include_pattern') !== '')"
                :title="`Include Pattern: ${findValue(taskInstance.parameters, 'rcloneOptions', 'include_pattern')}`">
                Include Pattern: <b>{{ findValue(taskInstance.parameters, 'rcloneOptions', 'include_pattern') }}</b>
            </p>
        </div>
        <div class="col-span-1">
            <p class="my-2 truncate"
                :title="`Dry Run: ${boolToYesNo(findValue(taskInstance.parameters, 'rcloneOptions', 'dry_run_flag'))}`">
                Dry Run: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'rcloneOptions', 'dry_run_flag'))
                    }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Check First: ${boolToYesNo(findValue(taskInstance.parameters, 'rcloneOptions', 'check_first_flag'))}`">
                Check First: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'rcloneOptions',
                    'check_first_flag'))
                    }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Bandwidth Limit: ${((findValue(taskInstance.parameters, 'rcloneOptions', 'bandwidth_limit_kbps') !== 0 ? `${findValue(taskInstance.parameters, 'rcloneOptions', 'bandwidth_limit_kbps')} kb/s` : 'No'))}`">
                Bandwidth Limit: <b>{{ ((findValue(taskInstance.parameters, 'rcloneOptions', 'bandwidth_limit_kbps')
                    !==
                    0 ? `${findValue(taskInstance.parameters, 'rcloneOptions', 'bandwidth_limit_kbps')} kb/s` :
                    'No'))
                    }}</b>
            </p>
            <p class="my-2 truncate"
                :title="`Number of Transfers: ${((findValue(taskInstance.parameters, 'rcloneOptions', 'transfers') !== 0 ? `${findValue(taskInstance.parameters, 'rcloneOptions', 'transfers')}` : '4 (Default)'))}`">
                Number of Transfers: <b>{{ ((findValue(taskInstance.parameters, 'rcloneOptions', 'transfers') !==
                    0 ? `${findValue(taskInstance.parameters, 'rcloneOptions', 'transfers')}` : '4 (Default)')) }}</b>
            </p>
            <p class="my-2 truncate"
                v-if="(findValue(taskInstance.parameters, 'rcloneOptions', 'exclude_pattern') !== '')"
                :title="`Exclude Pattern: ${findValue(taskInstance.parameters, 'rcloneOptions', 'exclude_pattern')}`">
                Exclude Pattern: <b>{{ findValue(taskInstance.parameters, 'rcloneOptions', 'exclude_pattern') }}</b>
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
import { computed, onMounted, ref } from 'vue';
import { boolToYesNo, injectWithCheck, findValue, upperCaseWord } from '../../../composables/utility'
import { getProviderLogo } from '../../../models/CloudSync';
import { remoteManagerInjectionKey, schedulerInjectionKey } from '../../../keys/injection-keys';

interface CloudSyncTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<CloudSyncTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remotes not found!");
const cloudRemote = ref();

onMounted(async () => {
    cloudRemote.value = await myRemoteManager.getRemoteByName(findValue(taskInstance.value.parameters, 'rclone_remote', 'rclone_remote'));
    console.log('cloudRemote:', cloudRemote.value);
});


</script>
