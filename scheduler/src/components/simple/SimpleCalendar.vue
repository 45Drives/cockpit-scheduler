<template>
    <div class="h-full rounded-md border border-default flex flex-col bg-accent text-default min-h-0">
        <div class="p-2 shrink-0">
            <label for="frequency-select" class="block text-sm font-medium">Backup Frequency</label>
            <select id="frequency-select" v-model="schedule.repeatFrequency" class="input-textlike w-full ">
                <option value="hour">Hourly</option>
                <option value="day">Daily</option>
                <option value="week">Weekly</option>
                <option value="month">Monthly</option>
            </select>

            <div class="grid grid-cols-2 gap-2 mt-2">
                <div v-if="schedule.repeatFrequency !== 'week'">
                    <label class="block text-sm">Start Day</label>
                    <input type="number" v-model="dayValue" @input="updateStartDate" min="1" max="31"
                        :disabled="schedule.repeatFrequency === 'hour'" class="input-textlike w-full text-sm" />
                </div>

                <div v-else>
                    <label class="block text-sm">Weekday</label>
                    <select class="input-textlike w-full text-sm" v-model="weekdayName" @change="setWeekdayByName">
                        <option v-for="n in DOW_NAMES" :key="n" :value="n">{{ n }}</option>
                    </select>
                </div>

                <div>
                    <label class="block text-sm">Start Month</label>
                    <input type="number" v-model="monthValue" @input="updateStartDate" min="1" max="12"
                        :disabled="schedule.repeatFrequency === 'hour' || schedule.repeatFrequency === 'week'"
                        class="input-textlike w-full text-sm" />
                </div>

                <div>
                    <label class="block text-sm">Start Hour</label>
                    <input type="number" v-model="hourValue" @input="updateStartDate" min="0" max="23"
                        class="input-textlike w-full text-sm" />
                </div>

                <div>
                    <label class="block text-sm">Start Minute</label>
                    <input type="number" v-model="minuteValue" @input="updateStartDate" min="0" max="59"
                        class="input-textlike w-full text-sm" />
                </div>
            </div>

            <p v-if="showInvalidDateWarning" class="text-warning text-base mt-1">
                Selected day is invalid for this month. Adjusted to last valid day.
            </p>
        </div>

        <div :title="parsedIntervalString"
            class="items-center col-span-1 text-base text-default bg-well p-1 rounded-md text-center w-full max-w-[600px] max-h-64 mx-auto shrink-0">
            <p class="text-sm text-default">Start date/time: {{ schedule.startDate.toLocaleString() }}</p>

            <p><strong>Will run backup {{ parsedIntervalString }}.</strong> </p>
        </div>

        <div class="p-1 mt-1 flex-1 min-h-0 text-center border border-default rounded-md">
            <div class="flex justify-between w-full p-1 bg-default text-center rounded-md">
                <button @click="changeMonth(-1)" class="btn btn-secondary">
                    Prev
                </button>
                <span class="text-lg font-semibold text-default text-center">{{ monthNames[currentMonth] }} {{
                    currentYear
                    }}</span>
                <button @click="changeMonth(1)" class="btn btn-secondary">
                    Next
                </button>
            </div>
            <div class="grid grid-cols-7 w-full my-1">
                <div v-for="day in DOW_NAMES" :key="day" class="text-center text-default font-medium">
                    {{ day }}
                </div>
            </div>
            <div class="grid grid-cols-7 gap-1 w-full grid-rows-6 auto-rows-fr">
                <div v-for="day in days" :key="day.id" :class="[ day.isPadding ? 'bg-accent text-muted cursor-default' : 'cursor-pointer hover:bg-gray-700',
                        day.isMarked && !day.isPadding ? 'bg-green-600 dark:bg-green-800 text-white' : 'bg-default' ]"
                    class="p-2 text-default text-center border border-default rounded"
                    @click="!day.isPadding && selectDay(Number(day.date))">
                    {{ day.date }}
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, toRef } from 'vue';
import { CardContainer } from '@45drives/houston-common-ui';
import { type TaskSchedule, parseTaskScheduleIntoString } from "@45drives/houston-common-lib";

interface Props {
    title: string;
    taskSchedule: TaskSchedule;
}
const props = defineProps<Props>();

// const schedule = toRef(props, 'taskSchedule')
const schedule = defineModel<TaskSchedule>('taskSchedule', { required: true });
const DOW_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const weekdayName = ref(DOW_NAMES[schedule.value.startDate.getDay()]);
function setWeekdayByName() {
    const now = new Date();
    const targetIdx = DOW_NAMES.indexOf(String(weekdayName.value).slice(0, 3));
    const d = new Date(
        now.getFullYear(), now.getMonth(), now.getDate(),
        schedule.value.startDate.getHours(), schedule.value.startDate.getMinutes()
    );
    const delta = (targetIdx - d.getDay() + 7) % 7;
    if (delta !== 0 || d <= now) d.setDate(d.getDate() + (delta || 7));
    schedule.value = { ...schedule.value, startDate: d };
}

// Extract day/month values from startDate
const dayValue = ref(schedule.value.startDate.getDate());
const monthValue = ref(schedule.value.startDate.getMonth() + 1);
const hourValue = ref(schedule.value.startDate.getHours());
const minuteValue = ref(schedule.value.startDate.getMinutes());
const yearValue = ref(schedule.value.startDate.getFullYear());

/// Calendar logic
// const today = new Date();
// const currentMonth = ref(today.getMonth());
// const currentYear = ref(today.getFullYear());
const currentMonth = ref(schedule.value.startDate.getMonth());
const currentYear = ref(schedule.value.startDate.getFullYear());

// Update startDate when inputs change and check for valid day/month combos
// const updateStartDate = () => {
//     let day = dayValue.value;
//     const month = monthValue.value - 1; // JS months are 0-indexed
//     const year = yearValue.value;

//     if (schedule.value.repeatFrequency === 'month') {
//         const daysInMonth = new Date(year, month + 1, 0).getDate();
//         if (day > daysInMonth) {
//             day = daysInMonth;
//             dayValue.value = day; // Adjust UI to show new valid day
//         }
//     }

//     schedule.value.startDate = new Date(year, month, day, hourValue.value, minuteValue.value);
// };
const updateStartDate = () => {
    let day = dayValue.value;
    const month = monthValue.value - 1;
    const year = yearValue.value;

    if (schedule.value.repeatFrequency === 'month') {
        const dim = new Date(year, month + 1, 0).getDate();
        if (day > dim) { day = dim; dayValue.value = day; }
    }
    schedule.value = {
        ...schedule.value,
        startDate: new Date(year, month, day, hourValue.value, minuteValue.value),
    };
};

const showInvalidDateWarning = computed(() => {
    if (schedule.value.repeatFrequency !== 'month') return false;
    const daysInMonth = new Date(yearValue.value, monthValue.value, 0).getDate();
    return dayValue.value > daysInMonth;
});

function selectDay(d: number) {
    dayValue.value = d;
    monthValue.value = currentMonth.value + 1;
    yearValue.value = currentYear.value;
    updateStartDate();
}

watch(() => schedule.value.repeatFrequency, (newFrequency) => {
    if (newFrequency === 'hour') {
        minuteValue.value = 0;
        updateStartDate();
    }
});

watch([hourValue, minuteValue, dayValue, monthValue, yearValue], () => {
    if (hourValue.value != null && minuteValue.value != null) {
        updateStartDate();
    }
});
watch(
    () => props.taskSchedule.startDate,
    (newDate) => {
        dayValue.value = newDate.getDate();
        monthValue.value = newDate.getMonth() + 1;
        yearValue.value = newDate.getFullYear();
        currentMonth.value = newDate.getMonth();
        hourValue.value = newDate.getHours();
        minuteValue.value = newDate.getMinutes();
        weekdayName.value = DOW_NAMES[newDate.getDay()]; // <-- keep select in sync
    },
    { immediate: true }
);

const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const days = computed(() => {
    const firstDayOfMonth = new Date(currentYear.value, currentMonth.value, 1).getDay();
    const numDays = new Date(currentYear.value, currentMonth.value + 1, 0).getDate();

    const daysArray = Array.from({ length: numDays }, (_, i) => {
        const date = new Date(currentYear.value, currentMonth.value, i + 1);
        const id = date.toISOString().split('T')[0];
        return { id, date: i + 1, isMarked: isScheduled(date), isPadding: false };
    });

    const startPaddingDays = Array.from({ length: firstDayOfMonth }, (_, i) => ({
        id: `pad-start-${i}`,
        date: '',
        isMarked: false,
        isPadding: true,
    }));

    const totalCells = 42;
    const endPaddingCount = totalCells - (startPaddingDays.length + daysArray.length);
    const endPaddingDays = Array.from({ length: endPaddingCount }, (_, i) => ({
        id: `pad-end-${i}`,
        date: '',
        isMarked: false,
        isPadding: true,
    }));

    return [...startPaddingDays, ...daysArray, ...endPaddingDays];
});

// Function to check if a date should be marked based on schedule
const isScheduled = (date: Date): boolean => {
    if (!schedule.value.startDate) return false;

    const startDate = new Date(schedule.value.startDate);
    startDate.setHours(0, 0, 0, 0); // Normalize to midnight
    date.setHours(0, 0, 0, 0); // Ensure uniform comparison

    if (date.getTime() === startDate.getTime()) return true; //  Always highlight the start date
    if (date < startDate) return false; //  Don't mark days before start date

    const freq = schedule.value.repeatFrequency;
    if (freq === 'hour' || freq === 'day') return date >= startDate;
    if (freq === 'week') return date >= startDate && date.getDay() === startDate.getDay();
    if (freq === 'month') return date >= startDate && date.getDate() === startDate.getDate();

    return false;
};



// Change month in calendar
const changeMonth = (delta: number) => {
    let m = currentMonth.value + delta;
    let y = currentYear.value;
    if (m < 0) { m = 11; y--; }
    else if (m > 11) { m = 0; y++; }
    currentMonth.value = m;
    currentYear.value = y;
    yearValue.value = y;
};


const parsedIntervalString = computed(() => parseTaskScheduleIntoString(schedule.value));
</script>

<style scoped>
.grid-rows-6 {
    grid-template-rows: repeat(6, minmax(0, 1fr));
}
</style>
