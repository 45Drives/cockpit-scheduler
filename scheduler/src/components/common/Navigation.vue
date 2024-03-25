<template>
	<div class="bg-default">
		<div class="sm:hidden">
			<label for="tabs" class="sr-only">Select a tab</label>
			<!-- Use an "onChange" listener to redirect the user to the selected tab URL. -->
			<select id="tabs" name="tabs" class="block w-full rounded-md border-default py-2 pl-3 pr-10 text-base focus:border-fefault focus:outline-none focus:ring-slate-500 sm:text-sm">
				<option v-for="item in props.navigationItems" :key="item.name" @change="navigationCallback(item)" :selected="item.current">{{ item.name }}</option>
			</select>
		</div>
		<!--^^^ Mobile or very small screen --- DOES NOT WORK YET (onChange wont work for some reason) ^^^-->

		<!--vvv Desktop/Regular version vvv-->
		<div class="hidden sm:block">
			<div class="border-b border-default">
				<nav class="-mb-px flex justify-center" aria-label="Tabs">
					<a v-for="item in props.navigationItems" :key="item.name"
						@click.prevent="navigationCallback(item)"
						:class="[item.current ? 'border-default text-default' : 'border-transparent text-secondary hover:border-default hover:text-default', 'whitespace-nowrap border-b-4 py-4 px-4 text-sm font-medium']" :aria-current="item.current ? 'page' : undefined">{{ item.name }}</a>
				</nav>
				<Notifications
					:notificationFIFO="notificationFIFO"
					ref="notifications"
				/>
			</div>
		</div>

	
	</div>
</template>

<script setup lang="ts">
import { inject, Ref } from 'vue';
import Notifications from "../common/Notifications.vue";
import { FIFO } from '@45drives/cockpit-helpers';

interface NavigationProps {
	show: boolean;
	navigationItems: NavigationItem[];
	currentNavigationItem?: NavigationItem;
	navigationCallback: NavigationCallback;
}

const props = defineProps<NavigationProps>();

const notificationFIFO = inject<Ref<FIFO>>('notification-fifo')!;
const notifications = inject<Ref<any>>('notifications')!;
</script>