<template>
    <div class="mt-2">
        <div name="task-name">
            <label class="mt-1 block text-sm leading-6 text-default">Task Name</label>
            <input type="text" v-model="newTaskName" class="my-1 block w-full input-textlike bg-default" placeholder="New Task"/> 
            <!-- Limit name input to alphanumeric, special chars? (NO UNDERSCORE) -->
        </div>
        <div v-if="template.name == 'ZFS Replication Task'">
            <ZfsRepTaskParams :parameterSchema="template.parameterSchema"/>
        </div>
    </div>
</template>
<script setup lang="ts">

import { ref, Ref, reactive, computed, onMounted, watch } from 'vue';
import { ZFSReplicationTaskTemplate, TaskTemplate, ParameterNode, ZfsDatasetParameter, SelectionOption, SelectionParameter, IntParameter, StringParameter, BoolParameter, TaskInstance } from '../../models/Classes';
import ZfsRepTaskParams from './ZfsRepTaskParams.vue'
interface ParameterInputProps {
//    parameterSchema: ParameterNode;
    selectedTemplate: TaskTemplateType;
}

const props = defineProps<ParameterInputProps>();

const newTaskName = ref('');

const template = ref(props.selectedTemplate)


watch(template, (newVal, oldVal) => {
    if (template.value!.name == 'ZFS Replication Task') {
        template.value = new ZFSReplicationTaskTemplate;
    }
});




onMounted(() => {

});
</script>