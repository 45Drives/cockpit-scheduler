<template>
    <DetailSection title="Configuration — SMART Test">
        <div class="grid grid-cols-2 gap-x-6 gap-y-1">
            <DetailField label="Test Type"
                :value="upperCaseWord(findValue(taskInstance.parameters, 'testType', 'testType'))" />
            <DetailField label="Disk Identifier"
                :value="findValue(taskInstance.parameters, 'identifier', 'identifier') || 'Default'" />
        </div>
        <div class="mt-3">
            <dt class="text-sm text-muted mb-1">Disks</dt>
            <div class="flex flex-wrap gap-1.5">
                <span v-for="(disk, idx) in disksArray" :key="idx"
                    class="px-2 py-0.5 text-sm font-medium border border-default rounded-lg bg-accent">
                    {{ disk }}
                </span>
            </div>
        </div>
    </DetailSection>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { findValue, splitAndClean, upperCaseWord } from '../../../composables/utility';
import DetailField from '../../common/DetailField.vue';
import DetailSection from '../../common/DetailSection.vue';

interface SmartTestTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<SmartTestTaskDetailsProps>();
const taskInstance = ref(props.task);

const disksArray = splitAndClean(findValue(taskInstance.value.parameters, 'disks', 'disks'), true);
</script>