<template>
	<div :class="[props.bgColor]" class="divide-y divide-default overflow-hidden rounded-lg shadow">
		<div v-if="props.titleSection" class="px-3 py-3">
			<slot name="title"/>
		</div>
		<div v-if="props.contentSection" class="px-3 py-3">
			<slot name="content"/>
		</div>
		<div v-if="props.footerSection" class="px-3 py-3">
			<slot name="footer"/>
		</div>
	</div>
</template>

<script setup lang="ts">

interface CardProps {
	titleSection: boolean;
	contentSection: boolean;
	footerSection: boolean;
	bgColor: string;
}

const props = defineProps<CardProps>();

</script>