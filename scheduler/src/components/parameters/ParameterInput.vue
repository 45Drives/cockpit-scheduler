<template>
    <div class="mt-3">
        <ZfsRepTaskParams v-if="template.name == 'ZFS Replication Task'" ref="activeComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
        <AutomatedSnapshotTaskParams v-else-if="template.name == 'Automated Snapshot Task'" ref="activeComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
        <RsyncTaskParams v-else-if="template.name == 'Rsync Task'" ref="activeComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
        <ScrubTaskParams v-else-if="template.name == 'Scrub Task'" ref="activeComponent" :parameterSchema="template.parameterSchema" :task="props.task"/>
        <!-- <SmartTestTaskParams v-else-if="template.name == 'SMART Test'" ref="activeComponent" :parameterSchema="template.parameterSchema" :task="props.task"/> -->
    </div>
</template>
<script setup lang="ts">

import { ref, computed } from 'vue';
import ZfsRepTaskParams from './task-parameters/ZfsRepTaskParams.vue'
import AutomatedSnapshotTaskParams from './task-parameters/AutomatedSnapshotTaskParams.vue'
import RsyncTaskParams from './task-parameters/RsyncTaskParams.vue';
import ScrubTaskParams from './task-parameters/ScrubTaskParams.vue';
import SmartTestTaskParams from './task-parameters/SmartTestTaskParams.vue';

interface ParameterInputProps {
    selectedTemplate: TaskTemplateType;
    task?: TaskInstanceType;
}

const props = defineProps<ParameterInputProps>();

const template = computed(() => props.selectedTemplate);
// const activeComponent = ref<InstanceType<typeof ZfsRepTaskParams | typeof AutomatedSnapshotTaskParams | typeof RsyncTaskParams > | null>(null);
const activeComponent = ref<InstanceType<typeof ZfsRepTaskParams | typeof AutomatedSnapshotTaskParams | typeof RsyncTaskParams | typeof ScrubTaskParams> | null>(null);

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