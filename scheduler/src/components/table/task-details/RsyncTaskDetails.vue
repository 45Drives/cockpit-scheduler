<template>
    <div class="grid grid-cols-2 gap-4">
        <DetailSection title="Configuration — Rsync Task">
            <!-- Direction visual -->
            <div class="flex items-end justify-around text-center pb-2 mb-2 border-b border-default">
                <div class="min-w-0 flex-1 text-left">
                    <span class="text-xs text-muted block">{{ isPush ? 'Source' : 'Target' }}</span>
                    <span class="text-sm font-semibold text-default block truncate"
                        :title="findValue(taskInstance.parameters, 'local_path', 'local_path')">
                        {{ findValue(taskInstance.parameters, 'local_path', 'local_path') || '—' }}
                    </span>
                </div>
                <div class="flex items-center mx-2 mb-0.5 flex-shrink-0"
                    :class="isPush ? '' : 'rotate-180'"
                    :title="isPush ? 'Push' : 'Pull'">
                    <ChevronDoubleRightIcon class="w-4 h-4 text-muted" />
                    <ChevronDoubleRightIcon class="w-4 h-4 text-muted" />
                    <ChevronDoubleRightIcon class="w-4 h-4 text-muted" />
                </div>
                <div class="min-w-0 flex-1 text-right">
                    <span class="text-xs text-muted block">{{ isPush ? 'Target' : 'Source' }}</span>
                    <span class="text-sm font-semibold text-default block truncate"
                        :title="findValue(taskInstance.parameters, 'target_info', 'path')">
                        {{ findValue(taskInstance.parameters, 'target_info', 'path') || '—' }}
                    </span>
                </div>
            </div>
            <!-- Fields -->
            <div class="grid grid-cols-2 gap-x-6 gap-y-1">
                <DetailField label="Transfer Type" :value="transferTypeLabel" />
                <template v-if="findValue(taskInstance.parameters, 'target_info', 'host') !== ''">
                    <DetailField label="Remote SSH Host"
                        :value="findValue(taskInstance.parameters, 'target_info', 'host')" wrap />
                    <DetailField label="Remote SSH Port"
                        :value="String(findValue(taskInstance.parameters, 'target_info', 'port') ?? '')" />
                </template>
            </div>
        </DetailSection>
        <DetailSection title="Transfer Options">
            <div class="grid grid-cols-2 gap-x-6 gap-y-1">
                <DetailField label="Archive Mode"
                    :value="boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'archive_flag'))" />
                <DetailField label="Recursive"
                    :value="boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'recursive_flag'))" />
                <DetailField label="Compressed"
                    :value="boolToYesNo(findValue(taskInstance.parameters, 'rsyncOptions', 'compressed_flag'))" />
                <DetailField label="Bandwidth Limit" :value="bandwidthLabel" />
                <DetailField label="Delete When Removed"
                    :value="boolToYesNo(!!findValue(taskInstance.parameters, 'rsyncOptions', 'delete_when_removed_flag'))" />
                <DetailField label="Skip Newer"
                    :value="boolToYesNo(!!findValue(taskInstance.parameters, 'rsyncOptions', 'skip_newer_flag'))" />
                <DetailField label="Keep Partial"
                    :value="boolToYesNo(!!findValue(taskInstance.parameters, 'rsyncOptions', 'keep_partial_flag'))" />
                <DetailField label="Checksum"
                    :value="boolToYesNo(!!findValue(taskInstance.parameters, 'rsyncOptions', 'checksum_flag'))" />
                <DetailField v-if="findValue(taskInstance.parameters, 'rsyncOptions', 'filter_include')"
                    label="Include Filter"
                    :value="findValue(taskInstance.parameters, 'rsyncOptions', 'filter_include')" wrap />
                <DetailField v-if="findValue(taskInstance.parameters, 'rsyncOptions', 'filter_exclude')"
                    label="Exclude Filter"
                    :value="findValue(taskInstance.parameters, 'rsyncOptions', 'filter_exclude')" wrap />
            </div>
        </DetailSection>
    </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue';
import { boolToYesNo, findValue, upperCaseWord } from '../../../composables/utility';
import { ChevronDoubleRightIcon } from '@heroicons/vue/24/outline';
import DetailField from '../../common/DetailField.vue';
import DetailSection from '../../common/DetailSection.vue';

interface RsyncTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<RsyncTaskDetailsProps>();
const taskInstance = ref(props.task);

const isRemote = computed(() => findValue(taskInstance.value.parameters, 'target_info', 'host') !== '');
const directionLabel = computed(() => upperCaseWord(findValue(taskInstance.value.parameters, 'direction', 'direction')));
const isPush = computed(() => (findValue(taskInstance.value.parameters, 'direction', 'direction') || '').toLowerCase() !== 'pull');

const transferTypeLabel = computed(() => {
    return isRemote.value
        ? `Remote (${directionLabel.value})`
        : `Local (${directionLabel.value})`;
});

const bandwidthLabel = computed(() => {
    const limit = findValue(taskInstance.value.parameters, 'rsyncOptions', 'bandwidth_limit_kbps');
    return limit !== 0 ? `${limit} kb/s` : 'No';
});

</script>