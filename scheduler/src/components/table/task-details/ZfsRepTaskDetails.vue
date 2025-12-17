<template>
    <!-- Details for ZFS Replication Task -->
    <div v-if="taskInstance.template.name === 'ZFS Replication Task'" class="grid grid-cols-4 items-left text-left">
        <div class="col-span-1">
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

            <p v-if="hasSnapshotRetentionPolicy(taskInstance)" class="my-2 truncate"
                :title="`Keep Src. Snapshots For: ${findNestedValue(taskInstance.parameters, 'snapshotRetention.source.retentionTime')} ${findNestedValue(taskInstance.parameters, 'snapshotRetention.source.retentionUnit')}`">
                Keep Src. Snapshots For:
                <b>{{
                    findNestedValue(taskInstance.parameters, 'snapshotRetention.source.retentionTime')
                    }} {{
                        findNestedValue(taskInstance.parameters, 'snapshotRetention.source.retentionUnit')
                    }}</b>
            </p>

            <p v-else class="my-2 truncate text-sm" :title="`No Snapshot Retention Policy Configured`">
                <b>No Snapshot Retention Policy Configured</b>
            </p>

            <p class="my-2" v-if="remoteHost !== ''">
                <span class="truncate" :title="`${remoteLabel} ${remoteProtoLabel} Host: ${remoteHost}`">
                    {{ remoteLabel }} {{ remoteProtoLabel }} Host:
                    <b>{{ remoteHost }}</b>
                </span>

                <span class="truncate"
                    :title="`${remoteLabel} ${remoteProtoLabel} Port: ${findValue(taskInstance.parameters, 'destDataset', 'port')}`">
                    {{ remoteLabel }} {{ remoteProtoLabel }} Port:
                    <b>{{ findValue(taskInstance.parameters, 'destDataset', 'port') }}</b>
                </span>
            </p>
        </div>

        <div class="col-span-1">
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
                :title="`Destination: ${findValue(taskInstance.parameters, 'destDataset', 'dataset')}`">
                Destination: <b>
                    {{ findValue(taskInstance.parameters, 'destDataset', 'dataset') }}
                </b>
            </p>

            <p v-if="hasSnapshotRetentionPolicy(taskInstance)" class="my-2 truncate"
                :title="`Keep Dest. Snapshots For: ${findNestedValue(taskInstance.parameters, 'snapshotRetention.destination.retentionTime')} ${findNestedValue(taskInstance.parameters, 'snapshotRetention.destination.retentionUnit')}`">
                Keep Dest. Snapshots For:
                <b>{{
                    findNestedValue(taskInstance.parameters, 'snapshotRetention.destination.retentionTime')
                    }} {{
                        findNestedValue(taskInstance.parameters, 'snapshotRetention.destination.retentionUnit')
                    }}</b>
            </p>

            <p v-else class="my-2 truncate text-sm" :title="`No Snapshot Retention Policy Configured`">
                <b>No Snapshot Retention Policy Configured</b>
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
import { ref, computed } from 'vue';
import { boolToYesNo, injectWithCheck, findValue } from '../../../composables/utility'
import { schedulerInjectionKey } from '../../../keys/injection-keys';

interface ZfsRepTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<ZfsRepTaskDetailsProps>();
const taskInstance = ref(props.task);
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

function findNestedValue(obj: any, path: string) {
    const keys = path.split('.');
    let current = obj;

    for (const key of keys) {
        if (!current) return null;
        if (current.children) {
            current = current.children.find((child: any) => child.key === key);
        } else {
            return null;
        }
    }
    return current?.value ?? null;
}

function hasSnapshotRetentionPolicy(taskInstance: any) {
    const sourceRetentionTime = findNestedValue(taskInstance.parameters, 'snapshotRetention.source.retentionTime');
    const destinationRetentionTime = findNestedValue(taskInstance.parameters, 'snapshotRetention.destination.retentionTime');
    return (sourceRetentionTime > 0 || destinationRetentionTime > 0);
}

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
