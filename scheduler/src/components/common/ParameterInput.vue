<template>
    <div class="mt-3">
        <div v-if="template.name == 'ZFS Replication Task'">
            <ZfsRepTaskParams ref="zfsRepTaskParamsComponent" :parameterSchema="template.parameterSchema"/>
        </div>
    </div>
</template>
<script setup lang="ts">

import { ref } from 'vue';
import ZfsRepTaskParams from './ZfsRepTaskParams.vue'
interface ParameterInputProps {
    selectedTemplate: TaskTemplateType;
}

const props = defineProps<ParameterInputProps>();

const template = ref(props.selectedTemplate)

const zfsRepTaskParamsComponent = ref();

function validation() {
    zfsRepTaskParamsComponent.value.validateParams();
}

function clearTaskParamErrorTags() {
    zfsRepTaskParamsComponent.value.clearErrorTags();
}

defineExpose({
    validation,
    clearTaskParamErrorTags,
});
</script>