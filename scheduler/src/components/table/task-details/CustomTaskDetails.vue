<template>
    <DetailSection title="Configuration — Custom Task">
        <div class="grid grid-cols-2 gap-x-6 gap-y-1">
            <DetailField label="Execution Type" :value="executionType" />
            <DetailField v-if="isScriptFile" label="Script Path"
                :value="findValue(taskInstance.parameters, 'filePath', 'filePath') || '—'" wrap />
            <DetailField v-else label="Command"
                :value="displayCommand" wrap />
        </div>
    </DetailSection>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue';
import { findValue } from '../../../composables/utility';
import DetailField from '../../common/DetailField.vue';
import DetailSection from '../../common/DetailSection.vue';

interface CustomTaskDetailsProps {
    task: TaskInstanceType;
}

const props = defineProps<CustomTaskDetailsProps>();
const taskInstance = ref(props.task);

const executionType = computed(() => {
    const isFilePath = taskInstance.value.parameters.children.find((child: any) => child.key === 'filePath_flag')?.value;
    return isFilePath ? 'Script File' : 'Custom Command';
});

const isScriptFile = computed(() => {
    return !!taskInstance.value.parameters.children.find((child: any) => child.key === 'filePath_flag')?.value;
});

const displayCommand = computed(() => {
    const raw = findValue(taskInstance.value.parameters, 'command', 'command') || '';
    // Unwrap /bin/bash -c "..." wrapper for display
    const prefix = '/bin/bash -c "';
    if (raw.startsWith(prefix) && raw.endsWith('"')) {
        const inner = raw.slice(prefix.length, -1);
        return inner
            .replace(/\\\\/g, '\\')
            .replace(/\\'/g, "'")
            .replace(/\\"/g, '"')
            .replace(/\\`/g, '`') || '—';
    }
    return raw || '—';
});

</script>
