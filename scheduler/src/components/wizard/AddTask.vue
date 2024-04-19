<template>
    <Modal @close="closeModal" :isOpen="showWizard" :margin-top="'mt-12'" :width="'w-3/5'" :min-width="'min-w-3/5'">
        <template v-slot:title>
            Add New Task
        </template>
        <template v-slot:content>
            <div>
                <div name="task-template" v-if="taskTemplates.length > 0">
					<label for="task-template-selection" class="block text-sm font-medium leading-6 text-default">Select Type of Task to Add</label>
					<select id="task-template-selection" v-model="selectedTemplate" name="task-template-selection" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option v-for="template, idx in taskTemplates" :key="idx" :value="template">{{ template.name }}</option>
					</select>
				</div>
                <div name="task-name">
                    <div class="flex flex-row justify-between items-center">
                        <label class="mt-1 block text-sm leading-6 text-default">Task Name</label>
                        <ExclamationCircleIcon v-if="newTaskNameErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                    </div>
                    <input v-if="!newTaskNameErrorTag" type="text" v-model="newTaskName" class="my-1 block w-full input-textlike bg-default" placeholder="New Task"/> 
                    <input v-if="newTaskNameErrorTag" type="text" v-model="newTaskName" class="my-1 block w-full input-textlike bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="New Task"/> 
                </div>
                <div v-if="selectedTemplate">
                    <ParameterInput ref="parameterInputComponent" :selectedTemplate="selectedTemplate"/>
                </div>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
				<div class="button-group-row w-full justify-between">
					<div class="button-group-row mt-2">
                        <button @click.stop="closeModal" id="close-add-task-btn" name="close-add-task-btn" class="mt-1 btn btn-danger">Close</button>
					</div>
					<div class="button-group-row mt-2">
                        <button disabled v-if="!adding && !selectedTemplate" id="add-task-btn" class="btn btn-primary object-right justify-end h-fit w-full" @click="addTaskBtn">Add Task</button>
                        <button v-if="!adding && selectedTemplate" id="add-task-btn" class="btn btn-primary object-right justify-end h-fit w-full" @click="addTaskBtn">Add Task</button>
                        <button disabled v-if="adding" id="finish" type="button" class="btn btn-primary object-right justify-end">
                            <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                            </svg>
                            Adding...
                        </button>
					</div>
				</div>
			</div>
        </template>
    </Modal>
</template>
<script setup lang="ts">
import { inject, provide, reactive, ref, Ref, computed, watch, onMounted } from 'vue';
import Modal from '../common/Modal.vue';
import ParameterInput from '../common/ParameterInput.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import { Scheduler, TaskTemplate, ParameterNode, SelectionParameter, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter } from '../../models/Classes';


interface AddTaskProps {
	idKey: string;
}

const props = defineProps<AddTaskProps>();
const emit = defineEmits(['close']);
const notifications = inject<Ref<any>>('notifications')!;

const newTask = ref<TaskInstanceType>();

const taskTemplates = inject<Ref<TaskTemplateType[]>>('task-templates')!;
const myScheduler = inject<Scheduler>('scheduler')!;

const showWizard = inject<Ref<boolean>>('show-wizard')!;
const adding = ref(false);

const errorList = ref<string[]>([]);
const newTaskName = ref('');
const newTaskNameErrorTag = ref(false);
const selectedTemplate = ref<TaskTemplateType>();
const parameterInputComponent = ref();


const closeModal = () => {
    showWizard.value = false;
    emit('close');
}

function validateTaskName() {
    if (newTaskName.value === '') {
        errorList.value.push("Task name cannot be empty.");
        newTaskNameErrorTag.value = true;
    } else {
        if (newTaskName.value.includes('_')) {
            errorList.value.push("Task name cannot have underscores ('_').");
        newTaskNameErrorTag.value = true;
        }
    }
}

function clearAllErrors() {
    errorList.value = [];
    newTaskNameErrorTag.value = false;
    parameterInputComponent.value.clearTaskParamErrorTags();
}

function validateComponentParams() {
    clearAllErrors();
    validateTaskName();
    parameterInputComponent.value.validation();
    if (errorList.value.length > 0) {
        notifications.value.constructNotification('Task Save Failed', `Task submission has errors: \n- ${errorList.value.join("\n- ")}`, 'error', 8000);
        return false;
    } else {
        // notifications.value.constructNotification('Task Save Successful', `Task has been saved.`, 'success', 8000);
        return true;
    }
}

function addTaskBtn() {
    const taskParamsValid = validateComponentParams();

    if (taskParamsValid) {
        
    }
}


onMounted(() => {

});
    

provide('errors', errorList);
</script>

