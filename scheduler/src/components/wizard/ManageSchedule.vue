<template>
    <Modal @close="closeModal" :isOpen="showScheduleWizard" :margin-top="'mt-12'" :width="'w-3/5'" :min-width="'min-w-3/5'">
        <template v-slot:title>
            Manage Schedule
        </template>
        <template v-slot:content>
            <div name="new-schedule-interval" class="">
                <div class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">

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
                                <div class="flex flex-row justify-between items-center">
                                    <label class="block text-sm leading-6 text-default">Hour</label>
                                    <ExclamationCircleIcon v-if="hourErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                                </div>
                                <input v-if="!hourErrorTag" v-model="newInterval.hour!.value" type="text" placeholder="(0-23)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                                <input v-if="hourErrorTag" v-model="newInterval.hour!.value" type="text" placeholder="(0-23)" class="my-1 block w-full text-default input-textlike bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="minute">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="block text-sm leading-6 text-default">Minute</label>
                                    <ExclamationCircleIcon v-if="minuteErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                                </div>
                                <input v-if="!minuteErrorTag" v-model="newInterval.minute!.value" type="text" placeholder="(0-59)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                                <input v-if="minuteErrorTag" v-model="newInterval.minute!.value" type="text" placeholder="(0-59)" class="my-1 block w-full text-default input-textlike bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="day">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="block text-sm leading-6 text-default">Day</label>
                                    <ExclamationCircleIcon v-if="dayErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                                </div>
                                <input v-if="!dayErrorTag" v-model="newInterval.day!.value" type="text" placeholder="(1-31)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                                <input v-if="dayErrorTag" v-model="newInterval.day!.value" type="text" placeholder="(1-31)" class="my-1 block w-full text-default input-textlike bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="month">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="block text-sm leading-6 text-default">Month</label>
                                    <ExclamationCircleIcon v-if="monthErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                                </div>
                                <input v-if="!monthErrorTag" v-model="newInterval.month!.value" type="text" placeholder="(1-12)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/> 
                                <input v-if="monthErrorTag" v-model="newInterval.month!.value" type="text" placeholder="(1-12)" class="my-1 block w-full text-default input-textlike bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="year">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="block text-sm leading-6 text-default">Year</label>
                                    <ExclamationCircleIcon v-if="yearErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                                </div>
                                <input v-if="!yearErrorTag" v-model="newInterval.year!.value" type="text" placeholder="(YYYY)" class="my-1 block w-full text-default input-textlike bg-default" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/> 
                                <input v-if="yearErrorTag" v-model="newInterval.year!.value" type="text" placeholder="(YYYY)" class="my-1 block w-full text-default input-textlike bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" title="Use asterisk (*) for all values, hyphen (-) for ranges (eg. 2-7), and commas for lists (eg. 2,4,7)"/>
                            </div>
                            <div name="info" class="mt-1 px-1">
                                <label class="block text-sm text-default mt-0.5">
                                    Every value: Use asterisk (*).
                                </label>
                                <label class="block text-sm text-default mt-0.5">
                                    Step values (all fields except for Month & Year): Use asterisk + slash (eg. */2).
                                </label>
                                <label class="block text-sm text-default mt-0.5">
                                    List of values: Use commas (eg. 1,4,9).
                                </label>
                                <label class="block text-sm text-default mt-0.5">
                                    Range of time values (Hour, Minute): Use hyphen (eg. 10-20).
                                </label>
                                <label class="block text-sm text-default mt-0.5">
                                    Range of dates (Day, Month, Year): Use two periods (eg. 1..4).
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
                                                    <input :id="`${day}`" v-model="newInterval.dayOfWeek" type="checkbox" :value="`${day}`" :name="`${day}`" 
                                                    class="mb-0.5 w-4 h-4 text-success bg-well border-default rounded focus:ring-green-500 dark:focus:ring-green-600 dark:ring-offset-gray-800 focus:ring-2"/>	
                                                </label>
                                            </button>
                                            <!-- <input v-if="newInterval.dayOfWeek!.includes(day)" type="number" v-model="newInterval.dayOfWeekSteps[day]" min="1" placeholder="Step (optional)" class="text-sm"/> -->
                                        </td>
                                    </tr>
                                </table>
                            </div>
                            <div name="buttons" class="col-span-2 button-group-row justify-between mt-2">
                                <button name="clearFields" @click="clearFields()" class="btn btn-danger h-min">Clear Interval</button>
                                <button name="saveInterval" @click="saveInterval(newInterval)" class="btn btn-secondary h-min">Save Interval</button>
                            </div>
                        </div>
                    </div>


                    <div name="schedule-preview" class="col-start-1 row-start-2 border border-default rounded-md p-2 col-span-1 bg-accent">
                        <label class="block text-sm font-medium leading-6 text-default">Interval Preview</label>
                        <div class="mt-1">
                            <CalendarComponent :key="calendarKey" :interval="newInterval!" />
                        </div>
                    </div>


                    <div name="schedule-interval-list"  @click="clearSelectedInterval()" class="col-start-2 row-start-2 border border-default rounded-md p-2 col-span-1 bg-accent">
                        <div @click="clearSelectedInterval()">
                            <div class="flex flex-row justify-between">
                                <label class="block text-sm font-medium leading-6 text-default whitespace-nowrap">Current Intervals</label>
                            </div>
                            <ul role="list" class="divide-y divide-default rounded-lg mt-2">
                                <li v-for="interval, idx in intervals" :key="idx" class="py-4 text-default rounded-lg"  :class="intervalSelectedClass(interval)">
                                    <button class="h-full w-full rounded-lg" @click.stop="selectIntervalToManage(interval)" :class="intervalSelectedClass(interval)"> {{ myScheduler.parseIntervalIntoString(interval) }}</button>
                                </li>
                            </ul>
                        </div>
                        <div v-if="selectedInterval !== undefined" class="button-group-row justify-between mt-2">
                            <button name="remove-interval" @click="" class="btn btn-danger h-min w-full">Remove Interval</button>
                            <button name="edit-interval" @click="editSelectedInterval(selectedInterval)" class="btn btn-secondary h-min w-full">Edit Interval</button>
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
                        <button v-if="!savingSchedule" id="add-schedule-btn" class="btn btn-primary object-right justify-end h-fit w-full" @click="saveScheduleBtn()">Save schedule</button>
                        <button disabled v-if="savingSchedule" id="finish" type="button" class="btn btn-primary object-right justify-end">
                            <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                            </svg>
                            Saving Schedule...
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
import CalendarComponent from '../common/CalendarComponent.vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import ConfirmationDialog from '../common/ConfirmationDialog.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import { Scheduler, TaskTemplate, ParameterNode, SelectionParameter, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter, TaskInstance, TaskSchedule, TaskScheduleInterval } from '../../models/Classes';

interface ManageScheduleProps {
    idKey: string;
    mode: 'add' | 'edit';
    task: TaskInstance;
}

const props = defineProps<ManageScheduleProps>();
const emit = defineEmits(['close']);
const notifications = inject<Ref<any>>('notifications')!;
const myScheduler = inject<Scheduler>('scheduler')!;
const showScheduleWizard = inject<Ref<boolean>>('show-schedule-wizard')!;

const savingSchedule = ref(false);

const closeModal = () => {
    showScheduleWizard.value = false;
    emit('close');
}

const schedule = ref<TaskScheduleType>();
const selectedPreset = ref('none');
const scheduleEnabled = ref(true);
const intervals = ref<TaskScheduleIntervalType[]>([]);

const daysOfWeek : DayOfWeek[] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const newInterval = reactive<TaskScheduleIntervalType>({
    minute: { value: '0' },
    hour: { value: '0' },
    day: { value: '1' },
    month: { value: '*' },
    year: { value: '*' },
    dayOfWeek: []
});

// function resetIntervalDefaults(interval) {
//     interval.hour.value = '0';
//     interval.minute.value = '0';
//     interval.day.value = '1';
//     interval.month.value = '*';
//     interval.year.value = '*';
//     interval.dayOfWeek = [];
// }

function clearFields() {
    Object.assign(newInterval, {
        minute: { value: '' },
        hour: { value: '' },
        day: { value: '' },
        month: { value: '' },
        year: { value: '' },
        dayOfWeek: []
    });
    forceUpdateCalendar();
}

function setFields(min, hr, d, mon, y, dow) {
    newInterval.hour!.value = hr;
    newInterval.minute!.value = min;
    newInterval.day!.value = d;
    newInterval.month!.value = mon;
    newInterval.year!.value = y;
    newInterval.dayOfWeek! = dow;
}

const errorList = ref<string[]>([]);
const hourErrorTag = ref(false);
const minuteErrorTag = ref(false);
const dayErrorTag = ref(false);
const monthErrorTag = ref(false);
const yearErrorTag = ref(false);

function clearAllErrors() {
    errorList.value = [];
    hourErrorTag.value = false;
    minuteErrorTag.value = false;
    dayErrorTag.value = false;
    monthErrorTag.value = false;
    yearErrorTag.value = false;
}


function isOnCalendarExpression(value, type) {
    // Check for empty value
    if (value.trim() === '') {
        return false;
    }

    // Function to validate the format with steps (e.g., "*/2")
    const validateStepFormat = (stepValue) => {
        const stepNumber = Number(stepValue);
        return !isNaN(stepNumber) && stepNumber > 0;
    };

    // Check for asterisk, steps like "*/3", or named day steps like "Mon/2"
    if (value === '*') {
        return true;
    } else if (value.includes('/') && type !== 'year' && type !== 'month') {
        const parts = value.split('/');
        if (parts.length === 2 && parts[0] === '*') {
            return validateStepFormat(parts[1]);
        }
        return false;
    }

    // Check for lists like "1,2,3"
    if (value.includes(',')) {
        const listValues = value.split(',').map(v => v.trim());
        return listValues.every(val => isOnCalendarExpression(val, type)); // Recursive call to handle each value in list
    }

    // Check for ranges like "1-5" or "1..5"
    const rangeDelimiter = value.includes('..') ? '..' : '-';
    if (value.includes(rangeDelimiter)) {
        const rangeParts = value.split(rangeDelimiter).map(v => v.trim());
        if (rangeParts.length !== 2 || rangeParts.some(rp => isNaN(Number(rp)))) {
            return false;
        }
        const range = rangeParts.map(Number);
        // Adjust these ranges based on the type
        let [min, max] = [0, 59]; // Defaults for minutes
        if (type === 'hour') [min, max] = [0, 23];
        else if (type === 'day') [min, max] = [1, 31];
        else if (type === 'month') [min, max] = [1, 12];
        else if (type === 'year') [min, max] = [1970, 9999];
        return range[0] >= min && range[0] <= max && range[1] >= min && range[1] <= max && range[0] < range[1];
    }

    // Check for single numbers or named days (for dayOfWeek)
    if (type !== 'dayOfWeek') {
        const number = Number(value);
        if (!isNaN(number)) {
            // Adjust these ranges based on the type
            let [min, max] = [0, 59]; // Defaults for minutes
            if (type === 'hour') [min, max] = [0, 23];
            else if (type === 'day') [min, max] = [1, 31];
            else if (type === 'month') [min, max] = [1, 12];
            return number >= min && number <= max;
        }
    }

    return false;
}


function validateFields(interval) {
    clearAllErrors();

    // Validate hour
    if (!isOnCalendarExpression(interval.hour.value, 'hour')) {
        hourErrorTag.value = true;
        errorList.value.push("Hour value is invalid.");
    }

    // Validate minute
    if (!isOnCalendarExpression(interval.minute.value, 'minute')) {
        minuteErrorTag.value = true;
        errorList.value.push("Minute value is invalid.");
    }

    // Validate day
    if (!isOnCalendarExpression(interval.day.value, 'day')) {
        dayErrorTag.value = true;
        errorList.value.push("Day value is invalid.");
    }

    // Validate month
    if (!isOnCalendarExpression(interval.month.value, 'month')) {
        monthErrorTag.value = true;
        errorList.value.push("Month value is invalid.");
    }

    // Validate year
    if (!isOnCalendarExpression(interval.year.value, 'year')) {
        yearErrorTag.value = true;
        errorList.value.push("Year value is invalid.");
    }

    // Print out errorList or do whatever you need with it
    if (errorList.value.length > 0) {
        // Handle errors
        console.log('Validation errors:', errorList);
        notifications.value.constructNotification('Schedule Interval Save Failed', `Submission has errors: \n- ${errorList.value.join("\n- ")}`, 'error', 8000);
        return false;
    } else {
        // No errors, continue with processing
        return true;
    }
}

const selectedInterval = ref<TaskScheduleIntervalType>();
function selectIntervalToManage(interval : TaskScheduleIntervalType) {
    selectedInterval.value = interval;
}

function saveInterval(interval) {
    if (validateFields(interval)) {
        // Deep clone the interval object to ensure no references are shared
        const clonedInterval = JSON.parse(JSON.stringify(interval));
        intervals.value.push(clonedInterval);
        console.log('newInterval saved:', clonedInterval);
        console.log('all intervals:', intervals.value);
    } 
}


function clearSelectedInterval() {
    selectedInterval.value = undefined;
}

function removeSelectedInterval(interval) {
    // intervals.value.pop
}

function editSelectedInterval(interval : TaskScheduleIntervalType) {
    const defaultTimeComponent = '0';

    // Set each field value, falling back to default if not present
    newInterval.hour!.value = interval.hour?.value ?? defaultTimeComponent;
    newInterval.minute!.value = interval.minute?.value ?? defaultTimeComponent;
    newInterval.day!.value = interval.day?.value ?? defaultTimeComponent;
    newInterval.month!.value = interval.month?.value ?? defaultTimeComponent;
    newInterval.year!.value = interval.year?.value ?? defaultTimeComponent;

    // Set selectedDays to the days from the interval or to an empty array if not present
    newInterval.dayOfWeek! = interval.dayOfWeek ?? [];
}

function saveScheduleBtn() {
    // myScheduler.registerTaskInstance(props.task);
    // myScheduler.updateTaskInstance(props.task);
    
    // myScheduler.updateSchedule(props.task);
    console.log('saving task:', props.task);
}

watch(selectedPreset, (newVal, oldVal) => {
    switch (selectedPreset.value) {
        case 'none':
            setFields('0', '0', '1', '*', '*', []);
            break;
        case 'hourly':
            setFields('0', '*', '*', '*', '*', []);
            break;
        case 'daily':  
            setFields('0', '0', '*', '*', '*', []);
            break;
        case 'weekly':
            setFields('0', '0', '*', '*', '*', [daysOfWeek[0]]);
            break;
        case 'monthly':   
            setFields('0', '0', '1', '*', '*', []);
            break;
        case 'yearly':
            setFields('0', '0', '1', '1', '*', []);
            break;
        default:
            break;
    }
});


const daySelectedClass = (dayOfWeek) => {
    const isSelected = newInterval.dayOfWeek!.includes(dayOfWeek);
    return isSelected ? 'bg-green-30 dark:bg-green-700' : '';
}

const intervalSelectedClass = (interval) => {
    return selectedInterval.value == interval ? 'bg-green-30 dark:bg-green-700' : 'bg-default'
}

watch(newInterval, (newVal, oldVal) => {
    console.log('newInterval changed:', newVal);
    forceUpdateCalendar();
}, { deep: true });

const calendarKey = ref(0);

function forceUpdateCalendar() {
  calendarKey.value++;
}

onMounted(() => {
   console.log('task data', props.task);
   intervals.value = props.task.schedule.intervals;
   console.log('intervals', intervals.value);
})

</script>