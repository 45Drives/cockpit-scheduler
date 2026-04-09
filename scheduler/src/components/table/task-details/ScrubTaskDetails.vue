<template>
    <DetailSection title="Configuration — Scrub Task">
        <div class="grid grid-cols-2 gap-x-6 gap-y-1">
            <DetailField label="Pool" :value="findValue(taskInstance.parameters, 'pool', 'pool')" />
        </div>
    </DetailSection>
</template>
<script setup lang="ts">
import { ref } from 'vue';
import { findValue } from '../../../composables/utility';
import DetailField from '../../common/DetailField.vue';
import DetailSection from '../../common/DetailSection.vue';

interface ScrubTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<ScrubTaskDetailsProps>();
const taskInstance = ref(props.task);

</script>