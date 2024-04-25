<template>
    <Modal @close="closeModal" :isOpen="showScheduleWizard" :margin-top="'mt-12'" :width="'w-3/5'" :min-width="'min-w-3/5'">
        <template v-slot:title>
            Manage Schedule
        </template>
        <template v-slot:content>
            <div name="new-schedule-interval" class="">
                <div class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
                     <!-- LEFT -->
                    <div name="schedule-input" class="border border-default rounded-md p-2 col-span-2 row-span-1 col-start-1 row-start-1 bg-accent grid grid-cols-1">
                        <div name="schedule-preset" class="col-span-1">
                            <label for="schedule-preset-selection" class="block text-sm font-medium leading-6 text-default">Interval Preset</label>
                            <select id="task-template-selection" v-model="selectedPreset" name="task-template-selection" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                                <option value="none">None</option>
                                <option value="hourly">Hourly</option>
                                <option value="daily">Daily</option>
                                <option value="weekly">Weekly</option>
                                <option value="monthly">Monthly</option>
                                <option value="yearly">Yearly</option>
                            </select>
                        </div>

                        <div name="schedule-fields" class="col-span-1 grid grid-cols-2 gap-2 mt-2">
                            <div name="hour">  
                                <label class="block text-sm leading-6 text-default">Hour</label>
                                <input v-model="hour" type="text" placeholder="(0-23)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="minute">
                                <label class="block text-sm leading-6 text-default">Minute</label>
                                <input v-model="minute" type="text" placeholder="(0-59)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="day">
                                <label class="block text-sm leading-6 text-default">Day</label>
                                <input v-model="day" type="text" placeholder="(1-31)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="month">
                                <label class="block text-sm leading-6 text-default">Month</label>
                                <input v-model="month" type="text" placeholder="(1-12)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="year">
                                <label class="block text-sm leading-6 text-default">Year</label>
                                <input v-model="year" type="text" placeholder="(YYYY)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="info" class="mt-5">
                                <label class="block text-base leading-6 text-default px-3">
                                    Use asterisk (*) for all values, hyphen (-) for ranges, and commas for lists:
                                    eg. 2-7 (range) or 2,4,7 (list).
                                </label>
                            </div>
                            <div name="dayOfWeek" class="col-span-2">
                                <label class="block text-sm leading-6 text-default">Day of Week</label>
                                <table class="w-full">
                                    <tr class="grid grid-cols-7">
                                        <td v-for="day in daysOfWeek" class="px-0.5 col-span-1">
                                            <button class="flex items-center w-full h-full border border-default rounded-lg bg-default"
                                            :class="daySelectedClass(day)">
                                                <label :for="`${day}`" class="flex flex-col items-center whitespace-nowrap w-full p-1 px-1 text-sm gap-0.5 bg-default rounded-lg" :class="daySelectedClass(day)">
                                                    <p class="w-full mt-0.5 text-sm text-default">{{ day }}</p>
                                                    <input :id="`${day}`" v-model="selectedDays" type="checkbox" :value="`${day}`" :name="`${day}`" 
                                                    class="mb-0.5 w-4 h-4 text-success bg-well border-default rounded focus:ring-green-500 dark:focus:ring-green-600 dark:ring-offset-gray-800 focus:ring-2"/>	
                                                </label>
                                            </button>
                                        </td>
                                    </tr>
                                </table>
                            </div>
                            <div name="buttons" class="col-span-2 button-group-row justify-between mt-2">
                                <button name="clearFields" @click="clearFields()" class="btn btn-danger whitespace-nowrap h-min">Clear Interval</button>
                                <button name="saveInterval" @click="" class="btn btn-secondary whitespace-nowrap h-min">Save Interval</button>
                            </div>
                        </div>
                    </div>


                    
                    <div name="schedule-preview" class="col-start-1 row-start-2 border border-default rounded-md p-2 col-span-1 bg-accent">
                        <label class="block text-sm font-medium leading-6 text-default">Interval Preview</label>
                        <div class="mt-1">
                            <CalendarComponent :schedule="props.task.schedule" />
                        </div>
                    </div>


                    <div name="schedule-interval-list"  @click="clearSelectedInterval()" class="col-start-2 row-start-2 border border-default rounded-md p-2 col-span-1 bg-accent">
                        <div @click="clearSelectedInterval()">
                            <label class="block text-sm font-medium leading-6 text-default">Currently Scheduled Intervals</label>
                            <ul role="list" class="divide-y divide-default rounded-lg bg-default mt-2 ">
                                <li v-for="interval, idx in task.schedule.intervals" :key="idx" class="py-4 text-default rounded-lg"  :class="intervalSelectedClass(interval)">
                                    <button class="h-full whitespace-nowrap w-full rounded-lg" @click.stop="selectIntervalToManage(interval)" :class="intervalSelectedClass(interval)">{{ myScheduler.parseIntervalIntoString(interval) }}</button>
                                </li>
                            </ul>
                        </div>
                        <div v-if="selectedInterval !== undefined" class="button-group-row justify-between mt-2">
                            <button name="remove-interval" @click="" class="btn btn-danger h-min whitespace-nowrap">Remove Selected Interval</button>
                            <button name="edit-interval" @click="editSelectedInterval(selectedInterval)" class="btn btn-secondary h-min whitespace-nowrap">Edit Selected Interval</button>
                        </div>
                    </div>
                </div>
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
import CalendarComponent from '../common/CalendarComponent.vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import ConfirmationDialog from '../common/ConfirmationDialog.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import { Scheduler, TaskTemplate, ParameterNode, SelectionParameter, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter, TaskInstance } from '../../models/Classes';

interface ManageScheduleProps {
    idKey: string;
    mode: 'add' | 'edit';
    task: TaskInstanceType;
    isNewTask: boolean;
}

const props = defineProps<ManageScheduleProps>();
const emit = defineEmits(['close']);
const notifications = inject<Ref<any>>('notifications')!;
const myScheduler = inject<Scheduler>('scheduler')!;
const showScheduleWizard = inject<Ref<boolean>>('show-schedule-wizard')!;

const closeModal = () => {
    showScheduleWizard.value = false;
    emit('close');
}

const schedule = ref<TaskScheduleType>();
const selectedPreset = ref('none');
const scheduleEnabled = ref(true);
const intervals = ref<TaskScheduleIntervalType[]>([]);

const daysOfWeek = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const selectedDays = ref<string[]>([]);

const newInterval: TaskScheduleIntervalType = {
    minute: { value: '*' },
    hour: { value: '*' },
    day: { value: '*' },
    month: { value: '*' },
    year: { value: '*' },
    dayOfWeek: []
};

const hour = ref();
const minute = ref();
const day = ref();
const month = ref();
const year = ref();

function clearFields() {
    hour.value = '';
    minute.value = '';
    day.value = '';
    month.value = '';
    year.value = '';
    selectedDays.value = [];
}

function setFields(min, hr, d, mon, y) {
    minute.value = min;
    hour.value = hr;
    day.value = d;
    month.value = mon;
    year.value = y;
}

const selectedInterval = ref<TaskScheduleIntervalType>();
function selectIntervalToManage(interval : TaskScheduleIntervalType) {
    selectedInterval.value = interval;
}

function clearSelectedInterval() {
    selectedInterval.value = undefined;
}

function removeSelectedInterval(interval : TaskScheduleIntervalType) {
    if (selectedInterval.value == interval) {

    }
}

function editSelectedInterval(interval : TaskScheduleIntervalType) {
     // Assuming '*' is your default value for each time component
     const defaultTimeComponent = '*';

    // Set each field value, falling back to default if not present
    hour.value = interval.hour?.value ?? defaultTimeComponent;
    minute.value = interval.minute?.value ?? defaultTimeComponent;
    day.value = interval.day?.value ?? defaultTimeComponent;
    month.value = interval.month?.value ?? defaultTimeComponent;
    year.value = interval.year?.value ?? defaultTimeComponent;

    // Set selectedDays to the days from the interval or to an empty array if not present
    selectedDays.value = interval.dayOfWeek ?? [];
}

watch(selectedPreset, (newVal, oldVal) => {
    switch (selectedPreset.value) {
        case 'none':
            clearFields();
            break;
        case 'hourly':
            setFields('0', '*', '*', '*', '*');
            selectedDays.value = [];
            break;
        case 'daily':  
            setFields('0', '0', '*', '*', '*');
            selectedDays.value = [];
            break;
        case 'weekly':
            setFields('0', '0', '*', '*', '*');
            break;
        case 'monthly':   
            setFields('0', '0', '1', '*', '*');
            break;
        case 'yearly':
            setFields('0', '0', '1', '1', '*');
            break;
        default:
            break;
    }
});


const daySelectedClass = (dayOfWeek) => {
    const isSelected = selectedDays.value.includes(dayOfWeek);
    return isSelected ? 'bg-green-30 dark:bg-green-700' : '';
}

const intervalSelectedClass = (interval) => {
    if (selectedInterval.value == interval) {
        return 'bg-green-30 dark:bg-green-700';
    }
}

onMounted(() => {
    if (!props.isNewTask) {
        // schedule.value = myScheduler.loadSchedulesFor(props.task);
    }
})

</script>