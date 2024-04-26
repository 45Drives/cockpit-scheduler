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
import { ref, computed, watchEffect } from 'vue';

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

// watchEffect(() => {
//   	console.log('Interval prop in CalendarComponent', props.interval);
// });

function checkSchedule(date: Date, interval: TaskScheduleIntervalType): boolean {
	const dayOfWeekMap = {
		'Sun': 0,
		'Mon': 1,
		'Tue': 2,
		'Wed': 3,
		'Thu': 4,
		'Fri': 5,
		'Sat': 6,
	};

	const matches = (value: string | number, dateComponent: number) => {
		// console.log(`matches: Checking ${value} against ${dateComponent}`);
		if (value === '*') {
			return true;
		}
		return Number(value) === dateComponent;
	};

	// Log each component to ensure they are evaluated correctly
	// console.log(`Checking date: ${date.toISOString()} against interval`, interval);

	if (interval.dayOfWeek && interval.dayOfWeek.length > 0 && !interval.dayOfWeek.some(day => matches(dayOfWeekMap[day], date.getDay()))) {
		return false;
	}
	if (interval.year && !matches(interval.year.value, date.getFullYear())) {
		return false;
	}
	if (interval.month && !matches(interval.month.value, date.getMonth() + 1)) {
		return false;
	}
	if (interval.day && !matches(interval.day.value, date.getDate())) {
		return false;
	}
	if (interval.hour && !matches(interval.hour.value, date.getHours())) {
		return false;
	}
	if (interval.minute && !matches(interval.minute.value, date.getMinutes())) {
		return false;
	}

	// console.log(`Date ${date.toISOString()} passes all checks.`);
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
