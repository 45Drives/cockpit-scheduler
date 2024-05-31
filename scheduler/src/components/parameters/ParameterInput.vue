<template>
    <div class="mt-3">
        <ZfsRepTaskParams v-if="template.name == 'ZFS Replication Task'" ref="activeComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
        <AutomatedSnapshotTaskParams v-else-if="template.name == 'Automated Snapshot Task'" ref="activeComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
    </div>
</template>
<script setup lang="ts">

import { ref, computed } from 'vue';
import ZfsRepTaskParams from '../parameters/ZfsRepTaskParams.vue'
import AutomatedSnapshotTaskParams from '../parameters/AutomatedSnapshotTaskParams.vue'
interface ParameterInputProps {
    selectedTemplate: TaskTemplateType;
    task?: TaskInstanceType;
}

const props = defineProps<ParameterInputProps>();

const template = computed(() => props.selectedTemplate);

const activeComponent = ref<InstanceType<typeof ZfsRepTaskParams | typeof AutomatedSnapshotTaskParams> | null>(null);

function validation() {
    activeComponent.value?.validateParams();
}

function clearTaskParamErrorTags() {
    activeComponent.value?.clearErrorTags();
}

defineExpose({
    validation,
    clearTaskParamErrorTags,
});
</script>