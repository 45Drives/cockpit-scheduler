<template>
	<div class="flex flex-col items-center p-2">
		<div class="flex justify-between w-full mb-4">
			<button @click="changeMonth(-1)" class="btn btn-secondary">
				Prev
			</button>
			<span class="text-lg font-semibold text-default mt-2">{{ monthNames[currentMonth] }} {{ currentYear }}</span>
			<button @click="changeMonth(1)" class="btn btn-secondary">
				Next
			</button>
		</div>
		<div class="grid grid-cols-7 w-full mb-2">
			<div v-for="day in weekDays" :key="day" class="text-center text-default font-medium">
				{{ day }}
			</div>
		</div>
		<div class="grid grid-cols-7 gap-2 w-full">
			<div v-for="day in days" :key="day.id" :class="{'bg-accent text-muted border-default': day.isPadding, 'bg-green-600 dark:bg-green-800': day.isMarked && !day.isPadding, 'bg-default' : !day.isMarked && !day.isPadding}" class="p-2 text-default text-center border border-default rounded">
				{{ day.date }}
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

interface CalendarComponentProps {
	interval: TaskScheduleIntervalType;
}

const props = defineProps<CalendarComponentProps>();
const today = new Date();
const currentMonth = ref(today.getMonth());
const currentYear = ref(today.getFullYear());

const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const days = computed(() => {
	const firstDayOfMonth = new Date(currentYear.value, currentMonth.value, 1).getDay();
	const numDays = new Date(currentYear.value, currentMonth.value + 1, 0).getDate();

	const daysArray = Array.from({ length: numDays }, (_, i) => {
		const date = new Date(currentYear.value, currentMonth.value, i + 1);
		const id = date.toISOString().split('T')[0]; // YYYY-MM-DD format
		const isMarked = checkSchedule(date, props.interval);
		// console.log(`Day ${date.getDate()} is marked: ${isMarked}`);
		return { id, date: i + 1, isMarked, isPadding: false };
	});

	// Padding for days before the first day of the month
	const startPaddingDays = Array.from({ length: firstDayOfMonth }, (_, i) => {
		const date = new Date(currentYear.value, currentMonth.value, -i);
		const id = date.toISOString().split('T')[0];
		return { id, date: '', isMarked: false, isPadding: true };
	}).reverse();

	// Determine end padding
	const lastDayOfMonth = new Date(currentYear.value, currentMonth.value, numDays).getDay();
	const endPaddingDays = Array.from({ length: 6 - lastDayOfMonth }, (_, i) => {
		const date = new Date(currentYear.value, currentMonth.value + 1, i + 1);
		const id = date.toISOString().split('T')[0];
		return { id, date: '', isMarked: false, isPadding: true };
	});

	return [...startPaddingDays, ...daysArray, ...endPaddingDays];
});


 function checkSchedule(date: Date, interval: TaskScheduleIntervalType): boolean {
    const dayOfWeekMap = {
        'Sun': '0', 'Mon': '1', 'Tue': '2', 'Wed': '3', 'Thu': '4', 'Fri': '5', 'Sat': '6',
    };

    const matches = (value: string, dateComponent: number) => {
        if (value === '*') {
            return true;
        } else if (value.includes('/')) {
            const [base, step] = value.split('/');
            const start = base === '*' ? 0 : parseInt(base);
            const interval = parseInt(step);
            return (dateComponent - start) % interval === 0;
        } else if (value.includes('-')) {
            const [start, end] = value.split('-').map(Number);
            return dateComponent >= start && dateComponent <= end;
        } else if (value.includes('..')) {
            const [start, end] = value.split('..').map(Number);
            return dateComponent >= start && dateComponent <= end;
        } else if (value.includes(',')) {
            const values = value.split(',').map(Number);
            return values.includes(dateComponent);
        } else {
            return parseInt(value) === dateComponent;
        }
    };

	if (interval.dayOfWeek && interval.dayOfWeek.length > 0 && !interval.dayOfWeek.some(day => matches(dayOfWeekMap[day], date.getDay()))) {
		return false;
	}
    if (interval.year && !matches(interval.year.value.toString(), date.getFullYear())) {
        return false;
    }
    if (interval.month && !matches(interval.month.value.toString(), date.getMonth() + 1)) {
        return false;
    }
    if (interval.day && !matches(interval.day.value.toString(), date.getDate())) {
        return false;
    }

    return true;
}


function changeMonth(delta) {
	currentMonth.value += delta;
	if (currentMonth.value < 0) {
		currentMonth.value = 11;
		currentYear.value--;
	} else if (currentMonth.value > 11) {
		currentMonth.value = 0;
		currentYear.value++;
	}
}
</script>
