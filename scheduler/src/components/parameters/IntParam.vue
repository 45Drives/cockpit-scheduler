<template>
    <input type="number" :name="props.name" v-model="props.value">
</template>
<script setup lang="ts">

interface IntParamProps {
    name: string;
    value: string;
}

const props = defineProps<IntParamProps>();
</script>