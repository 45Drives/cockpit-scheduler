<template>
    
</template>
<script setup lang="ts">
import { inject, provide, reactive, ref, Ref, computed, watch, onMounted } from 'vue';
import Modal from '../common/Modal.vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import { Scheduler, TaskTemplate, ParameterNode, SelectionParameter, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter, TaskInstance, ZFSReplicationTaskTemplate, TaskSchedule } from '../../models/Classes';

interface EditTaskProps {
    idKey: string;
    task: TaskInstanceType;
}

const props = defineProps<EditTaskProps>();
const emit = defineEmits(['close']);
const notifications = inject<Ref<any>>('notifications')!;
const showEditTaskWizard = inject<Ref<boolean>>('show-edit-task-wizard')!;
const saving = ref(false);

const errorList = ref<string[]>([]);
const parameterInputComponent = ref();
const parameters = ref();

const closeModal = () => {
    showEditTaskWizard.value = false;
    emit('close');
}


function validateComponentParams() {
    parameterInputComponent.value.clearTaskParamErrorTags();
    parameterInputComponent.value.validation();
    if (errorList.value.length > 0) {
        notifications.value.constructNotification('Task Edit Failed', `Task edit has errors: \n- ${errorList.value.join("\n- ")}`, 'error', 8000);
        return false;
    } else {
        return true;
    }
}

async function saveChangesBtn() {
    console.log('save changes triggered');

   
}

provide('parameters', parameters);
provide('errors', errorList);
</script> 