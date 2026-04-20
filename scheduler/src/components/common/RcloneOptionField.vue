<template>
    <div>
        <div class="flex items-start justify-between gap-2">
            <label :for="option.name" class="block text-sm font-medium text-default">
                {{ formatLabel(option.name) }}
                <span v-if="option.required" class="text-danger">*</span>
            </label>
            <InfoTile v-if="option.help" class="ml-1 shrink-0" :title="option.help" />
        </div>

        <!-- Select (exclusive examples) -->
        <select v-if="option.type === 'select' && option.examples" v-model="localValue"
            :id="option.name" class="block w-full mt-1 input-textlike text-default bg-default">
            <option value="">{{ option.default ? `Default: ${option.default}` : 'Select...' }}</option>
            <option v-for="ex in option.examples" :key="ex.value" :value="ex.value">
                {{ ex.value }}{{ ex.help ? ` — ${ex.help}` : '' }}
            </option>
        </select>

        <!-- Bool -->
        <div v-else-if="option.type === 'bool'" class="flex items-center mt-1">
            <input type="checkbox" v-model="localValue" :id="option.name"
                class="w-4 h-4 text-success border-default rounded focus:ring-green-500" />
            <span class="ml-2 text-xs text-muted">{{ option.default ? 'Default: true' : 'Default: false' }}</span>
        </div>

        <!-- Int / SizeSuffix / Duration -->
        <input v-else-if="option.type === 'int' || option.type === 'sizesuffix' || option.type === 'duration'"
            type="text" v-model="localValue" :id="option.name"
            class="block w-full mt-1 input-textlike text-default bg-default"
            :placeholder="option.default !== undefined && option.default !== '' ? `Default: ${option.default}` : 'Not set'" />

        <!-- Password -->
        <div v-else-if="option.is_password" class="relative mt-1">
            <input :type="showPassword ? 'text' : 'password'" v-model="localValue" :id="option.name"
                class="block w-full input-textlike text-default bg-default pr-10"
                :placeholder="option.default !== undefined && option.default !== '' ? `Default: ${option.default}` : 'Not set'" />
            <button type="button" @click="showPassword = !showPassword"
                class="absolute inset-y-0 right-0 px-3 flex items-center text-muted">
                <svg v-if="!showPassword" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.542-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.542 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
            </button>
        </div>

        <!-- String with non-exclusive examples (combobox-style) -->
        <div v-else-if="option.type === 'string' && option.examples && option.examples.length > 0">
            <input type="text" v-model="localValue" :id="option.name" :list="option.name + '-list'"
                class="block w-full mt-1 input-textlike text-default bg-default"
                :placeholder="option.default !== undefined && option.default !== '' ? `Default: ${option.default}` : 'Not set'" />
            <datalist :id="option.name + '-list'">
                <option v-for="ex in option.examples" :key="ex.value" :value="ex.value">
                    {{ ex.help || ex.value }}
                </option>
            </datalist>
        </div>

        <!-- Default: plain string -->
        <input v-else type="text" v-model="localValue" :id="option.name"
            class="block w-full mt-1 input-textlike text-default bg-default"
            :placeholder="option.default !== undefined && option.default !== '' ? `Default: ${option.default}` : 'Not set'" />
    </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import InfoTile from './InfoTile.vue';
import type { RcloneOption } from '../../composables/useRcloneProviders';

interface Props {
    option: RcloneOption;
    modelValue: any;
}

const props = defineProps<Props>();
const emit = defineEmits<{
    (e: 'update:modelValue', value: any): void;
}>();

const showPassword = ref(false);

const localValue = computed({
    get: () => props.modelValue,
    set: (val) => emit('update:modelValue', val),
});

function formatLabel(name: string): string {
    return name
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}
</script>
