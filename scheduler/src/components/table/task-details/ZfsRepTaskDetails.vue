<template>
    <!-- Details for ZFS Replication Task -->
    <div v-if="taskInstance.template.name === 'ZFS Replication Task'"
        class="grid w-full grid-cols-4 gap-x-8 items-start text-left">
        <div class="col-span-1 min-w-0">
            <p class="my-2 truncate" :title="`Task Type: ${taskInstance.template.name}`">
                Task Type: <b>ZFS Replication Task</b>
            </p>

            <p class="my-2 truncate" :title="sendTypeTitle">
                Send Type: <b>{{ sendTypeLabel }}</b>
            </p>

            <p class="my-2 truncate"
                :title="`Source: ${findValue(taskInstance.parameters, 'sourceDataset', 'dataset')}`">
                Source: <b>
                    {{ findValue(taskInstance.parameters, 'sourceDataset', 'dataset') }}
                </b>
            </p>

            <div v-if="remoteHost !== ''" class="my-2 flex flex-col gap-1 min-w-0">
                <div class="truncate" :title="`${remoteLabel} ${remoteProtoLabel} Host: ${remoteHost}`">
                    {{ remoteLabel }} {{ remoteProtoLabel }} Host: <b>{{ remoteHost }}</b>
                </div>

                <div class="truncate"
                    :title="`${remoteLabel} ${remoteProtoLabel} Port: ${findValue(taskInstance.parameters, 'destDataset', 'port')}`">
                    {{ remoteLabel }} {{ remoteProtoLabel }} Port:
                    <b>{{ findValue(taskInstance.parameters, 'destDataset', 'port') }}</b>
                </div>
            </div>
        </div>

        <div class="col-span-1 min-w-0">
            <p class="my-2 truncate"
                :title="`Compression: ${findValue(taskInstance.parameters, 'sendOptions', 'raw_flag') ? 'Raw' : findValue(taskInstance.parameters, 'sendOptions', 'compressed_flag') ? 'Compressed' : 'None'}`">
                Compression: <b>{{
                    findValue(taskInstance.parameters, 'sendOptions', 'raw_flag') ? 'Raw' :
                        findValue(taskInstance.parameters, 'sendOptions', 'compressed_flag') ? 'Compressed' : 'None'
                    }}</b>
            </p>

            <p class="my-2 truncate"
                :title="`Recursive Send: ${boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'recursive_flag'))}`">
                Recursive Send: <b>{{
                    boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'recursive_flag'))
                    }}</b>
            </p>

            <p class="my-2 truncate"
                :title="`Resume Failure Continue: ${boolToYesNo(!!findValue(taskInstance.parameters, 'sendOptions', 'resumeFailAllowOverwrite'))}`">
                Resume Failure Continue: <b>{{
                    boolToYesNo(!!findValue(taskInstance.parameters, 'sendOptions', 'resumeFailAllowOverwrite'))
                    }}</b>
            </p>

            <p class="my-2 truncate"
                :title="`Destination: ${findValue(taskInstance.parameters, 'destDataset', 'dataset')}`">
                Destination: <b>
                    {{ findValue(taskInstance.parameters, 'destDataset', 'dataset') }}
                </b>
            </p>
        </div>

        <div class="col-span-2 row-span-2 min-w-0">
            <p class="my-2 font-bold">Current Schedules:</p>
            <div v-if="taskInstance.schedule.intervals.length > 0">
                <div v-for="(interval, idx) in taskInstance.schedule.intervals" :key="idx"
                    class="flex flex-col col-span-2 divide divide-y divide-default p-1"
                    :title="`Run ${myScheduler.parseIntervalIntoString(interval)}.`">
                    <p>Run {{ myScheduler.parseIntervalIntoString(interval) }}.</p>
                    <p v-if="interval.retention" class="text-xs text-muted ml-2">
                        Retention:
                        <span v-if="interval.retention.source">
                            Src {{ interval.retention.source.retentionTime }} {{ interval.retention.source.retentionUnit }}
                        </span>
                        <span v-if="interval.retention.source && interval.retention.destination"> / </span>
                        <span v-if="interval.retention.destination">
                            Dst {{ interval.retention.destination.retentionTime }} {{ interval.retention.destination.retentionUnit }}
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
import { ref, computed } from 'vue';
import { boolToYesNo, injectWithCheck, findValue } from '../../../composables/utility'
import { schedulerInjectionKey } from '../../../keys/injection-keys';

interface ZfsRepTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<ZfsRepTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

const direction = computed(() => {
    const node = taskInstance.value?.parameters?.children?.find((c: any) => c.key === 'direction');
    return String(node?.value ?? 'push').toLowerCase();
});

const isPull = computed(() => direction.value === 'pull');

const transferMethod = computed(() => (findValue(taskInstance.value.parameters, 'sendOptions', 'transferMethod') || '').toLowerCase());
const remoteHost = computed(() => findValue(taskInstance.value.parameters, 'destDataset', 'host') || '');
const isRemote = computed(() => remoteHost.value !== '');

const effectiveTransferMethod = computed(() => {
    // If blank/unknown but remote exists, assume SSH for display
    if (!transferMethod.value && isRemote.value) return 'ssh';
    return transferMethod.value;
});

const sendTypeLabel = computed(() => {
    // If no remote host, it's local replication regardless of direction flag
    if (!isRemote.value) return 'Local';

    // Remote + pull is always SSH-only in your UI
    if (isPull.value) return 'Pull (Remote via SSH)';

    // Remote + push
    if (effectiveTransferMethod.value === 'netcat') return 'Push (Remote via Netcat)';
    if (effectiveTransferMethod.value === 'ssh') return 'Push (Remote via SSH)';
    return 'Push (Remote)';
});

const sendTypeTitle = computed(() => `Send Type: ${sendTypeLabel.value}`);

const remoteLabel = computed(() => (isPull.value ? 'Remote Source' : 'Remote Target'));
const remoteProtoLabel = computed(() => {
    // Pull: force SSH label
    if (isPull.value) return 'SSH';
    return effectiveTransferMethod.value === 'netcat' ? 'Netcat' : 'SSH';
});
</script>
