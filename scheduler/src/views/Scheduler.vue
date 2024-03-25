<template>
	<div>
		<!-- <div class="w-full h-dvh min-h-dvh overflow-visible bg-default text-default">


		</div> -->
	</div>
</template>

<script setup lang="ts">
import { ref, Ref, provide, watchEffect } from 'vue';
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";


interface SchedulerProps {
  	tag: string;
}

const props = defineProps<SchedulerProps>();


</script>