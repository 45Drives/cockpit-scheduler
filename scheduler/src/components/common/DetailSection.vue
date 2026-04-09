<template>
    <section class="rounded-md border border-default bg-accent p-4">
        <h4 v-if="$slots.title || title" class="text-sm font-semibold text-default mb-3">
            <slot name="title">{{ title }}</slot>
        </h4>
        <slot />
    </section>
</template>

<script setup lang="ts">
defineProps<{
    title?: string;
}>();
</script>
