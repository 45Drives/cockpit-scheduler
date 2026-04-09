<template>
    <DetailSection title="Configuration — Automated Snapshot Task">
        <div class="grid grid-cols-2 gap-x-6 gap-y-1">
            <DetailField label="Filesystem" :value="filesystemFullPath" wrap />
            <DetailField label="Recursive Snapshots"
                :value="boolToYesNo(findValue(taskInstance.parameters, 'recursive_flag', 'recursive_flag'))" />
            <DetailField v-if="findValue(taskInstance.parameters, 'customName_flag', 'customName_flag')"
                label="Custom Name"
                :value="findValue(taskInstance.parameters, 'customName', 'customName')" wrap />
        </div>
    </DetailSection>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue';
import { boolToYesNo, findValue } from '../../../composables/utility';
import DetailField from '../../common/DetailField.vue';
import DetailSection from '../../common/DetailSection.vue';

interface AutomatedSnapshotTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<AutomatedSnapshotTaskDetailsProps>();
const taskInstance = ref(props.task);

const filesystemFullPath = computed(() => {
    const pool = findValue(taskInstance.value.parameters, 'filesystem', 'pool') || '';
    const dataset = findValue(taskInstance.value.parameters, 'filesystem', 'dataset') || '';
    if (!pool || dataset.startsWith(pool + '/') || dataset === pool) return dataset;
    return `${pool}/${dataset}`;
});

const retentionLabel = computed(() => {
    const time = findValue(taskInstance.value.parameters, 'snapshotRetention', 'retentionTime');
    const unit = findValue(taskInstance.value.parameters, 'snapshotRetention', 'retentionUnit');
    if (!time || time === 0) return 'Keep Forever';
    return `${time} ${unit || ''}`;
});

</script>