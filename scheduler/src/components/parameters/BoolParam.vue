<template>
    <input type="checkbox" :name="props.name" v-model="props.value"/>
</template>
<script setup lang="ts">

interface BoolParamProps {
    name: string;
    value: boolean;
}

const props = defineProps<BoolParamProps>();
</script>
