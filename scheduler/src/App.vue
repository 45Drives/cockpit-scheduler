<template>
	<div class="min-h-screen h-full w-full min-w-fit flex flex-col bg-default overflow-auto">
		<HoustonHeader moduleName="Houston Scheduler" sourceURL=""
			issuesURL="" :pluginVersion="Number(pluginVersion)"
			:infoNudgeScrollbar="true" />
		<SchedulerView/>
	</div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, provide, onMounted } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import { pluginVersion } from "./version";
import { HoustonHeader } from "@45drives/cockpit-vue-components";
import { FIFO } from '@45drives/cockpit-helpers';
import Navigation from "./components/common/Navigation.vue";
import SchedulerView from './views/SchedulerView.vue';
import { Scheduler } from './models/Scheduler';

interface AppProps {
	notificationFIFO: FIFO;
}

const props = defineProps<AppProps>();
const notifications = ref<any>(null);
const scheduler = new Scheduler();


provide('notifications', notifications);
provide('notification-fifo', props.notificationFIFO);
</script>

	