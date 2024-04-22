<template>
    <Modal @close="closeModal" :isOpen="showScheduleWizard" :margin-top="'mt-12'" :width="'w-3/5'" :min-width="'min-w-3/5'">
        <template v-slot:title>
            <!-- Have this component be multi-function:
                    Add New Schedule (for existing task) 
                    Add New Schedule (during new task creation)
                    Edit Schedule
                    Remove Schedule
            -->
            Add New Schedule
        </template>
        <template v-slot:content>
            <div>
                <!-- INTERVAL PRESET - Select (hourly, daily, weekly, monthly, yearly) -->
                <!-- <div name="task-template" v-if="taskTemplates.length > 0">
					<label for="task-template-selection" class="block text-sm font-medium leading-6 text-default">Select Type of Task to Add</label>
					<select id="task-template-selection" v-model="selectedTemplate" name="task-template-selection" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option v-for="template, idx in taskTemplates" :key="idx" :value="template">{{ template.name }}</option>
					</select>
				</div> -->

                <!-- Date Details -->
                <!-- Day _____ Month _____ Year _____ -->

                <!-- Time Details -->
                <!-- Hour _____ Min _____ Sec? _____ -->

                <!-- Day of Week Selection - Checkboxes for each DoW (Sun - Sat) -->

                <!-- CalendarView to show preview of the currently selected schedule? -->

                <!-- Buttons to Add Interval & Remove Interval from this Schedule -->
                <!-- List of currently configured intervals -->

                <!-- Button to Save Schedule -->

            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
				<div class="button-group-row w-full justify-between">
					<div class="button-group-row mt-2">
                        <button @click.stop="closeModal" id="close-add-schedule-btn" name="close-add-schedule-btn" class="mt-1 btn btn-danger">Close</button>
					</div>
					<div class="button-group-row mt-2">
                       <!--  <button disabled v-if="!adding && !selectedTemplate" id="add-schedule-btn" class="btn btn-primary object-right justify-end h-fit w-full" @click="ManageScheduleBtn">Add schedule</button>
                        <button v-if="!adding && selectedTemplate" id="add-schedule-btn" class="btn btn-primary object-right justify-end h-fit w-full" @click="ManageScheduleBtn">Add schedule</button>
                        <button disabled v-if="adding" id="finish" type="button" class="btn btn-primary object-right justify-end">
                            <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                            </svg>
                            Adding...
                        </button> -->
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
import ConfirmationDialog from '../common/ConfirmationDialog.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import { Scheduler, TaskTemplate, ParameterNode, SelectionParameter, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter } from '../../models/Classes';

interface ManageScheduleProps {
	idKey: string;
    // type of schedule management (adding-new-task, adding-existing-task, editing)
    // if adding to existing-> what task to add schedule to? (or do this outside?)
    // if editing-> what schedule to edit
    // 
}

const props = defineProps<ManageScheduleProps>();
const emit = defineEmits(['close']);
const notifications = inject<Ref<any>>('notifications')!;
const newSchedule = ref<TaskScheduleType>();

const myScheduler = inject<Scheduler>('scheduler')!;

const showScheduleWizard = inject<Ref<boolean>>('show-schedule-wizard')!;

const closeModal = () => {
    showScheduleWizard.value = false;
    emit('close');
}

</script>