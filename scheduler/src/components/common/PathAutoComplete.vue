<template>
    <div class="relative">
        <input ref="inputEl" type="text" :value="modelValue" @input="handleInput" @focus="ac.onFocus()"
            @blur="handleBlur" @keydown="handleKeydown" :class="[
                'block w-full input-textlike sm:text-sm bg-default text-default',
                error ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '',
                inputClass
            ]" :placeholder="placeholder" />
        <div v-if="ac.showSuggestions.value && ac.suggestions.value.length > 0" ref="listEl"
            class="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-md border border-default bg-default shadow-lg">
            <button v-for="(entry, idx) in ac.suggestions.value" :key="entry.path" type="button"
                :ref="el => { if (el) itemRefs[idx] = el as HTMLElement }" :class="[
                    'flex items-center gap-2 w-full px-3 py-1.5 text-sm text-default text-left',
                    idx === highlightIndex ? 'bg-well' : 'hover:bg-well'
                ]" @mousedown.prevent="selectEntry(entry)" @mouseenter="highlightIndex = idx">
                <svg v-if="entry.isDir" class="w-4 h-4 text-muted shrink-0" fill="none" viewBox="0 0 24 24"
                    stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round"
                        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                <svg v-else class="w-4 h-4 text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"
                    stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round"
                        d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                <span class="truncate">{{ entry.path }}</span>
            </button>
        </div>
        <div v-if="ac.loading.value"
            class="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
            <svg class="animate-spin h-4 w-4 text-muted" xmlns="http://www.w3.org/2000/svg" fill="none"
                viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed, toRef, onMounted } from 'vue';
import { usePathAutoComplete, type PathEntry } from '../../composables/usePathAutoComplete';

interface Props {
    modelValue: string;
    placeholder?: string;
    error?: boolean;
    dirsOnly?: boolean;
    inputClass?: string;
    remoteHost?: string;
    remoteUser?: string;
}

const props = withDefaults(defineProps<Props>(), {
    placeholder: '',
    error: false,
    dirsOnly: false,
    inputClass: '',
    remoteHost: '',
    remoteUser: 'root',
});

const emit = defineEmits<{
    (e: 'update:modelValue', value: string): void;
}>();

const internalPath = ref(props.modelValue);
const highlightIndex = ref(-1);
const inputEl = ref<HTMLInputElement>();
const listEl = ref<HTMLElement>();
const itemRefs: Record<number, HTMLElement> = {};

const remoteHostRef = toRef(props, 'remoteHost');
const remoteUserRef = toRef(props, 'remoteUser');

const ac = usePathAutoComplete(internalPath, {
    dirsOnly: props.dirsOnly,
    remoteHost: remoteHostRef,
    remoteUser: remoteUserRef,
});

watch(() => props.modelValue, (val) => {
    internalPath.value = val;
});

// Reset highlight when suggestions change (deferred to avoid TDZ in bundled output)
onMounted(() => {
    watch(() => ac.suggestions.value, () => {
        highlightIndex.value = -1;
    });
});

function handleInput(event: Event) {
    const val = (event.target as HTMLInputElement).value;
    internalPath.value = val;
    emit('update:modelValue', val);
    highlightIndex.value = -1;
    ac.onInput();
}

function handleBlur() {
    highlightIndex.value = -1;
    ac.hideSuggestions();
}

function handleKeydown(event: KeyboardEvent) {
    const suggestions = ac.suggestions.value;
    const isOpen = ac.showSuggestions.value && suggestions.length > 0;

    if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!isOpen) {
            // Open suggestions if we have a path
            if (internalPath.value && internalPath.value.startsWith('/')) {
                ac.fetchSuggestions(internalPath.value);
            }
            return;
        }
        highlightIndex.value = highlightIndex.value < suggestions.length - 1
            ? highlightIndex.value + 1
            : 0;
        scrollToHighlighted();
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!isOpen) return;
        highlightIndex.value = highlightIndex.value > 0
            ? highlightIndex.value - 1
            : suggestions.length - 1;
        scrollToHighlighted();
    } else if (event.key === 'Tab') {
        if (isOpen) {
            event.preventDefault();
            if (highlightIndex.value >= 0 && highlightIndex.value < suggestions.length) {
                selectEntry(suggestions[highlightIndex.value]);
            } else {
                // Nothing highlighted — select the first item
                selectEntry(suggestions[0]);
            }
        }
    } else if (event.key === 'Enter') {
        if (isOpen && highlightIndex.value >= 0 && highlightIndex.value < suggestions.length) {
            event.preventDefault();
            selectEntry(suggestions[highlightIndex.value]);
        }
    } else if (event.key === 'Escape') {
        ac.showSuggestions.value = false;
        highlightIndex.value = -1;
    }
}

function scrollToHighlighted() {
    nextTick(() => {
        const el = itemRefs[highlightIndex.value];
        if (el) el.scrollIntoView({ block: 'nearest' });
    });
}

function selectEntry(entry: PathEntry) {
    internalPath.value = entry.path;
    emit('update:modelValue', entry.path);
    highlightIndex.value = -1;
    ac.selectSuggestion(entry);
    // Keep focus on the input so user can keep typing
    nextTick(() => inputEl.value?.focus());
}
</script>
