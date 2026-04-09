<template>
    <div class="grid grid-cols-2 gap-4">
        <DetailSection title="Configuration — Cloud Sync Task">
            <!-- Direction visual -->
            <div class="flex items-end justify-around text-center pb-2 mb-2 border-b border-default">
                <div class="min-w-0 flex-1 text-left">
                    <span class="text-xs text-muted block">{{ isPush ? 'Source (Local)' : 'Target (Local)' }}</span>
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
                    <span class="text-xs text-muted block">{{ isPush ? 'Target (Remote)' : 'Source (Remote)' }}</span>
                    <span class="text-sm font-semibold text-default block truncate"
                        :title="findValue(taskInstance.parameters, 'target_path', 'target_path')">
                        {{ findValue(taskInstance.parameters, 'target_path', 'target_path') || '—' }}
                    </span>
                </div>
            </div>
            <!-- Fields -->
            <div class="grid grid-cols-2 gap-x-6 gap-y-1">
                <DetailField label="Transfer Type"
                    :value="`${upperCaseWord(findValue(taskInstance.parameters, 'type', 'type'))} (${upperCaseWord(findValue(taskInstance.parameters, 'direction', 'direction'))})`" />
                <div class="min-w-0 py-0.5" v-if="cloudRemote">
                    <dt class="text-xs text-muted">Rclone Remote</dt>
                    <dd class="text-sm text-default font-semibold min-w-0 flex items-center gap-1.5">
                        <span class="truncate">{{ cloudRemote.name }}</span>
                        <img :src="getProviderLogo(undefined, cloudRemote)" alt=""
                            class="w-4 h-4 flex-shrink-0"
                            :title="`Provider: ${cloudRemote.getProviderName()}`" />
                    </dd>
                </div>
                <div v-else class="min-w-0 py-0.5">
                    <dt class="text-xs text-muted">Rclone Remote</dt>
                    <dd class="text-sm text-muted">Loading…</dd>
                </div>
                <DetailField
                    v-if="findValue(taskInstance.parameters, 'rcloneOptions', 'include_pattern') !== ''"
                    label="Include Pattern"
                    :value="findValue(taskInstance.parameters, 'rcloneOptions', 'include_pattern')" wrap />
            </div>
        </DetailSection>
        <DetailSection title="Transfer Options">
            <div class="grid grid-cols-2 gap-x-6 gap-y-1">
                <DetailField label="Dry Run"
                    :value="boolToYesNo(findValue(taskInstance.parameters, 'rcloneOptions', 'dry_run_flag'))" />
                <DetailField label="Check First"
                    :value="boolToYesNo(findValue(taskInstance.parameters, 'rcloneOptions', 'check_first_flag'))" />
                <DetailField label="Bandwidth Limit" :value="bandwidthLabel" />
                <DetailField label="Num. of Transfers" :value="transfersLabel" />
                <DetailField
                    v-if="findValue(taskInstance.parameters, 'rcloneOptions', 'exclude_pattern') !== ''"
                    label="Exclude Pattern"
                    :value="findValue(taskInstance.parameters, 'rcloneOptions', 'exclude_pattern')" wrap />
            </div>
        </DetailSection>
    </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { boolToYesNo, findValue, upperCaseWord, injectWithCheck } from '../../../composables/utility';
import { getProviderLogo } from '../../../models/CloudSync';
import { remoteManagerInjectionKey } from '../../../keys/injection-keys';
import { ChevronDoubleRightIcon } from '@heroicons/vue/24/outline';
import DetailField from '../../common/DetailField.vue';
import DetailSection from '../../common/DetailSection.vue';

interface CloudSyncTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<CloudSyncTaskDetailsProps>();
const taskInstance = ref(props.task);
const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remotes not found!");
const cloudRemote = ref();

const isPush = computed(() => (findValue(taskInstance.value.parameters, 'direction', 'direction') || '').toLowerCase() !== 'pull');

const bandwidthLabel = computed(() => {
    const limit = findValue(taskInstance.value.parameters, 'rcloneOptions', 'bandwidth_limit_kbps');
    return limit !== 0 ? `${limit} kb/s` : 'No';
});

const transfersLabel = computed(() => {
    const transfers = findValue(taskInstance.value.parameters, 'rcloneOptions', 'transfers');
    return transfers !== 0 ? `${transfers}` : '4 (Default)';
});

onMounted(async () => {
    cloudRemote.value = await myRemoteManager.getRemoteByName(findValue(taskInstance.value.parameters, 'rclone_remote', 'rclone_remote'));
});

</script>
