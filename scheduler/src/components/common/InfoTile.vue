<template>
    <span class="inline" :title="props.title"><InformationCircleIcon class="inline w-5 h-5 text-muted" aria-hidden="true" /></span>
</template>

<script setup lang="ts">
import { InformationCircleIcon } from '@heroicons/vue/20/solid';

interface InfoTileProps {
    title: string;
}

const props = defineProps<InfoTileProps>();
</script>