<template>
	<div class="flex flex-col items-center p-4">
		<div class="flex justify-between w-full mb-4">
			<button @click="changeMonth(-1)" class="btn btn-secondary">
				Prev
			</button>
			<span class="text-lg font-semibold text-default">{{ monthNames[currentMonth] }} {{ currentYear }}</span>
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
			<div v-for="day in days" :key="day.id" :class="{'bg-well text-muted': day.isPadding, 'bg-yellow-200': day.isMarked && !day.isPadding}" class="p-2 text-default text-center border rounded">
				{{ day.date }}
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

interface CalendarComponentProps {
	schedule: TaskScheduleType;
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
		const isMarked = props.schedule.intervals.some(interval => checkSchedule(date, interval));
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

function checkSchedule(date, schedule) {
	// Add your logic to determine if the date matches the conditions in schedule
	// This is just a placeholder function
	return false;
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
