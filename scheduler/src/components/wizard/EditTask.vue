<template>
    <Modal @close="closeModal" :isOpen="showEditTaskWizard" :margin-top="'mt-10'" :width="'w-3/5'" :min-width="'min-w-3/5'" :close-on-background-click="false">
        <template v-slot:title>
            Edit <span class="text-base">{{taskInstance.name}}</span> <br/><span class="text-base text-muted italic">{{taskInstance.template.name}}</span>
        </template>
        <template v-slot:content>
            <div>
                <ParameterInput ref="parameterInputComponent" :selectedTemplate="taskInstance.template" :task="taskInstance"/>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
				<div class="button-group-row w-full justify-between">
                    <div class="button-group-row">
                        <button @click.stop="closeModal" id="close-edit-task-btn" name="close-edit-task-btn" class="btn btn-danger h-fit w-full">Close</button>
                    </div>
                    <div class="button-group-row">
                        <button v-if="!saving" id="edit-task-btn" class="btn btn-primary h-fit w-full" @click="saveChangesBtn">Save Task</button>
                        <button disabled v-if="saving" id="editing-task-btn" type="button" class="btn btn-primary h-fit w-full">
                            <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                            </svg>
                            Saving...
                        </button>
                    </div>
				</div>
			</div>
        </template>
    </Modal>


    <div v-if="showSaveConfirmation">
        <component :is="confirmationComponent" @close="updateShowSaveConfirmation" :showFlag="showSaveConfirmation" :title="'Save Task'" :message="'Save your edits?'" :confirmYes="confirmSaveChanges" :confirmNo="cancelEdit" :operation="'saving'" :operating="saving"/>
    </div>
</template>
<script setup lang="ts">
import { inject, provide, ref, Ref } from 'vue';
import Modal from '../common/Modal.vue';
import ParameterInput from './ParameterInput.vue';
import { Scheduler, TaskInstance, ZFSReplicationTaskTemplate, TaskSchedule } from '../../models/Classes';

interface EditTaskProps {
    idKey: string;
    task: TaskInstanceType;
}

const props = defineProps<EditTaskProps>();
const emit = defineEmits(['close']);
const notifications = inject<Ref<any>>('notifications')!;
const showEditTaskWizard = inject<Ref<boolean>>('show-edit-task-wizard')!;
const saving = ref(false);
const myScheduler = inject<Scheduler>('scheduler')!;
const loading = inject<Ref<boolean>>('loading')!;
const taskInstance = ref(props.task);
const initialTaskData = ref(props.task);

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

const showSaveConfirmation = ref(false);
const confirmationComponent = ref();
const loadConfirmationComponent = async () => {
    const module = await import('../common/ConfirmationDialog.vue');
    confirmationComponent.value = module.default;
}

async function showConfirmationDialog() {
    await loadConfirmationComponent();
    showSaveConfirmation.value = true;
    console.log('Showing confirmation dialog...');
}

const confirmSaveChanges : ConfirmationCallback = async () => {
    console.log('Saving and scheduling task now...');
    saving.value = true;
    await saveEditedTask();
    saving.value = false;
    updateShowSaveConfirmation(false);
    loading.value = true;
    await myScheduler.loadTaskInstances();
    loading.value = false;
    showEditTaskWizard.value = false;
}

const cancelEdit : ConfirmationCallback = async () => {
    updateShowSaveConfirmation(false);
}

async function saveEditedTask() {
    console.log('save changes triggered');
    if (taskInstance.value!.template.name == 'ZFS Replication Task') {
        const template = new ZFSReplicationTaskTemplate();
        
        let sanitizedName = taskInstance.value.name.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
        if (sanitizedName.startsWith('_')) {
            sanitizedName = 'task' + sanitizedName;
        }
        console.log('sanitizedName:', sanitizedName);

        const schedule = new TaskSchedule(taskInstance.value.schedule.enabled, taskInstance.value.schedule.intervals);
        const task = new TaskInstance(sanitizedName, template, parameters.value, schedule);
        console.log('edited task: ', task);

        // if (initialTaskData.value !== task) {
        //     await myScheduler.updateTaskInstance(task);

        //     notifications.value.constructNotification('Changes Saved', `Task has successfully been edited.`, 'success', 8000);
        // } else {
        //     notifications.value.constructNotification('No Changes Detected', `Task has not been edited.`, 'success', 8000);
        // }
        await myScheduler.updateTaskInstance(task);

        notifications.value.constructNotification('Changes Saved', `Task has successfully been edited.`, 'success', 8000);
    }
}

const updateShowSaveConfirmation = (newVal) => {
    showSaveConfirmation.value = newVal;
}

async function saveChangesBtn() {
    errorList.value = [];
    if (validateComponentParams()) {
        showConfirmationDialog();
    }
   
}


provide('task-for-editing', taskInstance);
provide('parameters', parameters);
provide('errors', errorList);
</script> 