<template>
    <div class="mt-3">
        <div v-if="template.name == 'ZFS Replication Task'">
            <ZfsRepTaskParams ref="zfsRepTaskParamsComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
        </div>
        <div v-if="template.name == 'Automated Snapshot Task'">
            <AutomatedSnapshotTaskParams ref="automatedSnapshotTaskParamsComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
        </div>
    </div>
</template>
<script setup lang="ts">

import { ref, watch, computed } from 'vue';
import ZfsRepTaskParams from '../parameters/ZfsRepTaskParams.vue'
import AutomatedSnapshotTaskParams from '../parameters/AutomatedSnapshotTaskParams.vue'
interface ParameterInputProps {
    selectedTemplate: TaskTemplateType;
    task?: TaskInstanceType;
}

const props = defineProps<ParameterInputProps>();

const template = ref(props.selectedTemplate)

const zfsRepTaskParamsComponent = ref();
const automatedSnapshotTaskParamsComponent = ref();

const activeComponent = computed(() => {
    switch (props.selectedTemplate.name) {
        case 'ZFS Replication Task':
            return zfsRepTaskParamsComponent.value;
        case 'Automated Snapshot Task':
            return automatedSnapshotTaskParamsComponent.value;
        default:
            return null;
    }
});

function validation() {
    activeComponent.value?.validateParams();
}

function clearTaskParamErrorTags() {
    activeComponent.value?.clearErrorTags();
}

// Watch for changes in selectedTemplate
watch(() => props.selectedTemplate, (newTemplate) => {
    template.value = newTemplate;
}, { deep: true });

defineExpose({
    validation,
    clearTaskParamErrorTags,
});
</script>