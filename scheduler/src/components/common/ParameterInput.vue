<template>
    <div class="mt-3">
        <div v-if="template.name == 'ZFS Replication Task'">
            <ZfsRepTaskParams ref="zfsRepTaskParamsComponent" :parameterSchema="template.parameterSchema"/>
        </div>
    </div>
</template>
<script setup lang="ts">

import { ref, Ref, reactive, computed, onMounted, watch, inject } from 'vue';
import { ZFSReplicationTaskTemplate, TaskTemplate, ParameterNode, ZfsDatasetParameter, SelectionOption, SelectionParameter, IntParameter, StringParameter, BoolParameter, TaskInstance } from '../../models/Classes';
import ZfsRepTaskParams from './ZfsRepTaskParams.vue'
interface ParameterInputProps {
//    parameterSchema: ParameterNode;
    selectedTemplate: TaskTemplateType;
}

const props = defineProps<ParameterInputProps>();

const errorList = inject<Ref<string[]>>('errors')!;

const template = ref(props.selectedTemplate)

const zfsRepTaskParamsComponent = ref();

function validation() {
    zfsRepTaskParamsComponent.value.validateParams();
    // console.log('ParameterInput Validation ErrorList:', errorList.value);
}

onMounted(() => {

});

defineExpose({
    validation,
});
</script>