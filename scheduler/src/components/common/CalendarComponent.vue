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
		<div class="flex justify-between w-full mb-2">
			<div v-for="day in weekDays" :key="day" class="w-1/7 text-center text-default font-medium">
				{{ day }}
			</div>
		</div>
		<div class="grid grid-cols-7 gap-2 w-full">
			<div v-for="day in days" :key="day.id" :class="{'bg-accent text-muted border-default': day.isPadding, 'bg-green-600 dark:bg-green-800': day.isMarked && !day.isPadding}" class="p-2 bg-default text-default text-center border border-default rounded">
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

		// Use the provided interval to check if this date should be marked
		const isMarked = checkSchedule(date, props.interval);

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

watchEffect(() => {
  	console.log('Interval prop in CalendarComponent', props.interval);
});

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

	// Helper function to check if the value matches the date component
	const matches = (value: string | number, dateComponent: number) => {
		// If the value is a wildcard, it matches any date component
		if (value == '*') return true;
		// Otherwise, convert value to a number and compare
		return Number(value) == dateComponent;
	};

	// console.log(`Checking date: ${date.toISOString()}`);
  	// console.log(`Against interval: ${JSON.stringify(interval)}`);

	// Check day of week
	if (interval.dayOfWeek && !interval.dayOfWeek.some(day => matches(dayOfWeekMap[day], date.getDay()))) {
		return false;
	}

	// Check year
	if (interval.year && !matches(interval.year.value, date.getFullYear())) {
		return false;
	}

	// Check month
	if (interval.month) {
		const monthMatch = matches(interval.month.value, date.getMonth() + 1);
		console.log(`Month Check - Interval Value: ${interval.month.value}, Date Month: ${date.getMonth() + 1}, Match: ${monthMatch}`);
		if (!monthMatch) return false;
	}

	// Check day
	if (interval.day) {
		const dayMatch = matches(interval.day.value, date.getDate());
		console.log(`Day Check - Interval Value: ${interval.day.value}, Date Day: ${date.getDate()}, Match: ${dayMatch}`);
		if (!dayMatch) return false;
	}

	// Check hour
	// if (interval.hour && !matches(interval.hour.value, date.getHours())) {
	// 	return false;
	// }

	// // Check minute
	// if (interval.minute && !matches(interval.minute.value, date.getMinutes())) {
	// 	return false;
	// }

	console.log(`Date: ${date.toISOString()}`);
	console.log(`Interval: `, interval);
	console.log(`Result of checks for ${date.toISOString()}: `, {
		dayOfWeekCheck: interval.dayOfWeek ? 'not empty' : 'empty',
		yearCheck: interval.year ? interval.year.value : 'empty',
		monthCheck: interval.month ? interval.month.value : 'empty',
		dayCheck: interval.day ? interval.day.value : 'empty',
		// hourCheck: interval.hour ? interval.hour.value : 'empty',
		// minuteCheck: interval.minute ? interval.minute.value : 'empty',
	});

	// If all checks passed, this date matches the interval
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
