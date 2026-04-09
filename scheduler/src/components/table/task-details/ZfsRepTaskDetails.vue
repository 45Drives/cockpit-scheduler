<template>
    <div class="grid grid-cols-2 gap-4">
        <DetailSection title="Configuration — ZFS Replication Task">
            <!-- Direction visual -->
            <div class="flex items-end justify-around text-center pb-2 mb-2 border-b border-default">
                <div class="min-w-0 flex-1 text-left">
                    <span class="text-xs text-muted block">Source</span>
                    <span class="text-sm font-semibold text-default block truncate"
                        :title="sourceFullPath">
                        {{ sourceFullPath || '—' }}
                    </span>
                </div>
                <div class="flex items-center mx-2 mb-0.5 flex-shrink-0"
                    :class="isPull ? 'rotate-180' : ''"
                    :title="isPull ? 'Pull' : 'Push'">
                    <ChevronDoubleRightIcon class="w-4 h-4 text-muted" />
                    <ChevronDoubleRightIcon class="w-4 h-4 text-muted" />
                    <ChevronDoubleRightIcon class="w-4 h-4 text-muted" />
                </div>
                <div class="min-w-0 flex-1 text-right">
                    <span class="text-xs text-muted block">Destination</span>
                    <span class="text-sm font-semibold text-default block truncate"
                        :title="destFullPath">
                        {{ destFullPath || '—' }}
                    </span>
                </div>
            </div>
            <!-- Fields -->
            <div class="grid grid-cols-2 gap-x-6 gap-y-1">
                <DetailField label="Send Type" :value="sendTypeLabel" />
                <template v-if="remoteHost !== ''">
                    <DetailField :label="`${remoteLabel} Host`" :value="remoteHost" wrap />
                    <DetailField :label="`${remoteLabel} Port`"
                        :value="String(findValue(taskInstance.parameters, 'destDataset', 'port') ?? '')" />
                    <DetailField label="Protocol" :value="remoteProtoLabel" />
                    <DetailField label="SSH User"
                        :value="findValue(taskInstance.parameters, 'destDataset', 'user') || 'root'" />
                </template>
            </div>
        </DetailSection>
        <DetailSection title="Transfer Options">
            <div class="grid grid-cols-2 gap-x-6 gap-y-1">
                <DetailField label="Direction" :value="isPull ? 'Pull' : 'Push'" />
                <DetailField label="Compression" :value="compressionValue" />
                <DetailField label="Recursive Send"
                    :value="boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'recursive_flag'))" />
                <DetailField label="Resume on Failure"
                    :value="boolToYesNo(!!findValue(taskInstance.parameters, 'sendOptions', 'resumeFailAllowOverwrite'))" />
                <DetailField v-if="isRemote" label="Transfer Method" :value="effectiveTransferMethod === 'netcat' ? 'Netcat' : 'SSH'" />
            </div>
        </DetailSection>
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { boolToYesNo, findValue } from '../../../composables/utility';
import { ChevronDoubleRightIcon } from '@heroicons/vue/24/outline';
import DetailField from '../../common/DetailField.vue';
import DetailSection from '../../common/DetailSection.vue';

interface ZfsRepTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<ZfsRepTaskDetailsProps>();
const taskInstance = ref(props.task);

const direction = computed(() => {
    const node = taskInstance.value?.parameters?.children?.find((c: any) => c.key === 'direction');
    return String(node?.value ?? 'push').toLowerCase();
});

const isPull = computed(() => direction.value === 'pull');

const transferMethod = computed(() => (findValue(taskInstance.value.parameters, 'sendOptions', 'transferMethod') || '').toLowerCase());
const remoteHost = computed(() => findValue(taskInstance.value.parameters, 'destDataset', 'host') || '');
const isRemote = computed(() => remoteHost.value !== '');

const effectiveTransferMethod = computed(() => {
    if (!transferMethod.value && isRemote.value) return 'ssh';
    return transferMethod.value;
});

const sendTypeLabel = computed(() => {
    if (!isRemote.value) return 'Local';
    if (isPull.value) return 'Pull (Remote via SSH)';
    if (effectiveTransferMethod.value === 'netcat') return 'Push (Remote via Netcat)';
    if (effectiveTransferMethod.value === 'ssh') return 'Push (Remote via SSH)';
    return 'Push (Remote)';
});

const remoteLabel = computed(() => (isPull.value ? 'Remote Source' : 'Remote Target'));
const remoteProtoLabel = computed(() => {
    if (isPull.value) return 'SSH';
    return effectiveTransferMethod.value === 'netcat' ? 'Netcat' : 'SSH';
});

const compressionValue = computed(() => {
    if (findValue(taskInstance.value.parameters, 'sendOptions', 'raw_flag')) return 'Raw';
    if (findValue(taskInstance.value.parameters, 'sendOptions', 'compressed_flag')) return 'Compressed';
    return 'None';
});

const sourceFullPath = computed(() => {
    const pool = findValue(taskInstance.value.parameters, 'sourceDataset', 'pool') || '';
    const dataset = findValue(taskInstance.value.parameters, 'sourceDataset', 'dataset') || '';
    if (!pool || dataset.startsWith(pool + '/') || dataset === pool) return dataset;
    return `${pool}/${dataset}`;
});

const destFullPath = computed(() => {
    const pool = findValue(taskInstance.value.parameters, 'destDataset', 'pool') || '';
    const dataset = findValue(taskInstance.value.parameters, 'destDataset', 'dataset') || '';
    if (!pool || dataset.startsWith(pool + '/') || dataset === pool) return dataset;
    return `${pool}/${dataset}`;
});
</script>
