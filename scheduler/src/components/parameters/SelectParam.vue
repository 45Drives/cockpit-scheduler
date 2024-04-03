<template>
    <select :name="name" v-model="selectedValue">
        <option v-for="option in options" :value="option.value">{{ option.label }}</option>
    </select>
</template>
<script setup lang="ts">
import { ref } from 'vue';

interface SelectParamProps {
    name: string;
    value: string;
    options: SelectionOptionType[];
}

const props = defineProps<SelectParamProps>();
const selectedValue = ref(props.value);
const emit = defineEmits(['update:value']);

  // Emit an event when the selected value changes
const updateValue = (newValue) => {
    selectedValue.value = newValue;
    // Emit an event to notify parent component of the value change
    emit('update:value', newValue);
};

</script>
  