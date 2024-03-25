<template>
	<div class="min-h-screen h-full w-full min-w-fit flex flex-col bg-default overflow-auto">
		<HoustonHeader moduleName="ZFS" sourceURL=""
			issuesURL="" :pluginVersion="Number(pluginVersion)"
			:infoNudgeScrollbar="true" />
		<Navigation :navigationItems="navigation" :currentNavigationItem="currentNavigationItem" :navigationCallback="navigationCallback" :show="show"/>
		<Scheduler :tag="navTag"/>
	</div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, provide } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import { pluginVersion } from "./version";
import { HoustonHeader } from "@45drives/cockpit-vue-components";
import { FIFO } from '@45drives/cockpit-helpers';
import Navigation from "./components/common/Navigation.vue";
import Scheduler from './views/Scheduler.vue';

interface AppProps {
	notificationFIFO: FIFO;
}

const props = defineProps<AppProps>();
const notifications = ref<any>(null);

const show = ref(true);
const navTag = ref('dashboard');

const currentNavigationItem = computed<NavigationItem | undefined>(() => navigation.find(item => item.current));

//navigation for tabs
const navigationCallback: NavigationCallback = (item: NavigationItem) => {
	navTag.value = item.tag;
};

//tabs for navigation
const navigation = reactive<NavigationItem[]>([
	{ name: 'Dashboard', tag: 'dashboard', current: computed(() => navTag.value == 'dashboard') as unknown as boolean, show: true, },
].filter(item => item.show));

provide('notifications', notifications);
provide('notification-fifo', props.notificationFIFO);
</script>

	