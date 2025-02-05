<template>
    <Modal @close="closeModal" :isOpen="showNotesPrompt" :margin-top="'mt-10'" :width="'w-3/5'" :min-width="'min-w-3/5'" :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="false" :closeConfirm="closeBtn">
        <template v-slot:title>
            Notes <span class="text-base">{{taskInstance.name}}</span> <br/><span class="text-base text-muted italic">{{taskInstance.template.name}}</span>
        </template>
        <template v-slot:content>
            <div>
                <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
                    <div class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
                        <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'" />
                    </div>
                </div>

                <div v-else>
                    <div class="grid grid-flow-cols my-2 gap-2">
                        <!-- Displaying notes section -->
                        <div class="border border-default rounded-md p-2 col-span-2 bg-accent">
                            <label class="mt-1 block text-sm leading-6 text-default">Notes</label>
                            <textarea v-model="notes" rows="4" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Your notes here..."></textarea>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
				<div class="button-group-row w-full justify-between">
                    <div class="button-group-row">
                        <button @click.stop="closeBtn()" id="close-edit-task-btn" name="close-edit-task-btn" class="btn btn-danger h-fit w-full">Close</button>
                    </div>
                    <div class="button-group-row">
                        <button v-if="saving" disabled id="editing-task-btn" type="button" class="btn btn-primary h-fit w-full">
                            <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                            </svg>
                            Saving...
                        </button>
                        <button @click="saveChangesBtn" class="btn btn-primary">Save Notes</button>                    
                    </div>
				</div>
			</div>
        </template>
    </Modal>

    <div v-if="showSaveConfirmation">
        <component :is="confirmationComponent" @close="updateShowSaveConfirmation" :showFlag="showSaveConfirmation" :title="'Save Task'" :message="'Save your edits?'" :confirmYes="confirmSaveChanges" :confirmNo="cancelEdit" :operation="'saving'" :operating="saving"/>
    </div>

    <div v-if="showCloseConfirmation">
        <component :is="closeConfirmationComponent" @close="updateShowCloseConfirmation" :showFlag="showCloseConfirmation" :title="'Cancel Edit Task'" :message="'Are you sure? Any changes will be lost.'" :confirmYes="confirmCancel" :confirmNo="cancelCancel" :operation="'canceling'" :operating="cancelingEditTask"/>
    </div>

</template>
<script setup lang="ts">
import { inject, provide, ref, Ref,computed } from 'vue';
import Modal from '../common/Modal.vue';
import { TaskInstance, ZFSReplicationTaskTemplate, TaskSchedule, AutomatedSnapshotTaskTemplate, RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate, CustomTaskTemplate } from '../../models/Tasks';
import { pushNotification, Notification } from '@45drives/houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, schedulerInjectionKey } from '../../keys/injection-keys';

interface EditTaskProps {
    idKey: string;
    task: TaskInstanceType;
}

const props = defineProps<EditTaskProps>();
const emit = defineEmits(['close']);
const showNotesPrompt = inject<Ref<boolean>>('show-notes-view')!;
const saving = ref(false);

const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");
const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
const taskInstance = ref(props.task);
const notes = ref(taskInstance.value?.notes);
const isEditing = ref(false); // State for editing notes



const errorList = ref<string[]>([]);
const parameterInputComponent = ref();
const parameters = ref();

const closeModal = () => {
    showNotesPrompt.value = false;
    emit('close');
}

const cancelingEditTask = ref(false);
const showCloseConfirmation = ref(false);
const closeConfirmationComponent = ref();
async function loadCloseConfirmationComponent() {
    const module = await import('../common/ConfirmationDialog.vue');
    closeConfirmationComponent.value = module.default;    
}

const closeBtn = async () => {
        closeModal();
};

const updateShowCloseConfirmation = (newVal) => {
    showCloseConfirmation.value = newVal;
}

const confirmCancel: ConfirmationCallback = async () => {
    closeModal();
}

const cancelCancel: ConfirmationCallback = async () => {
    updateShowCloseConfirmation(false);
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
    showNotesPrompt.value = false;
}

const cancelEdit : ConfirmationCallback = async () => {
    updateShowSaveConfirmation(false);
}

async function saveEditedTask() {
    console.log('save changes triggered');
    const template = ref();
    console.log("Notes: taskInstance: ",taskInstance)
    if (taskInstance.value?.template.name == 'ZFS Replication Task') {
        template.value = new ZFSReplicationTaskTemplate();
    } else if (taskInstance.value?.template.name == 'Automated Snapshot Task') {
        template.value = new AutomatedSnapshotTaskTemplate();
    } else if (taskInstance.value?.template.name == 'Rsync Task') {
        template.value = new RsyncTaskTemplate();
    } else if (taskInstance.value?.template.name == "Scrub Task") {
        template.value = new ScrubTaskTemplate();
    } else if (taskInstance.value?.template.name == "SMART Test") {
        template.value = new SmartTestTemplate();
    }
    else if (taskInstance.value?.template.name == "Custom Task") {
        template.value = new CustomTaskTemplate();
    }
  
    let sanitizedName = taskInstance.value.name.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
    if (sanitizedName.startsWith('_')) {
        sanitizedName = 'task' + sanitizedName;
    }
    console.log('sanitizedName:', sanitizedName);

    const schedule = new TaskSchedule(taskInstance.value.schedule.enabled, taskInstance.value.schedule.intervals);
    const task = new TaskInstance(sanitizedName, template.value, parameters.value, schedule,notes.value);
    console.log('edited task: ', task);

    await myScheduler.updateTaskNotes(task);

    pushNotification(new Notification('Changes Saved', `Task has successfully been edited.`, 'success', 8000));
}

const updateShowSaveConfirmation = (newVal) => {
    showSaveConfirmation.value = newVal;
}

async function saveChangesBtn() {
    showConfirmationDialog();
    
}


const addNote = () => {
            notes.value = ''; 
};
const editNote = () => {
};


provide('task-for-editing', taskInstance);
provide('parameters', parameters);
provide('errors', errorList);
</script> 