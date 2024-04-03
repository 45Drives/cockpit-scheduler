<template>
    <input type="text" :name="props.name" v-model="props.value">
</template>
<script setup lang="ts">

interface StringParamProps {
    name: string;
    value: string;
}

const props = defineProps<StringParamProps>();
</script>