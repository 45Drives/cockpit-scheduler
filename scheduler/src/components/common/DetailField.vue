<template>
    <div class="min-w-0 py-0.5">
        <dt class="text-xs text-muted" :title="label">{{ label }}</dt>
        <dd class="text-sm text-default font-semibold min-w-0"
            :class="wrap ? 'break-all' : 'truncate'"
            :title="title ?? value ?? ''">
            <slot>{{ value }}</slot>
        </dd>
    </div>
</template>

<script setup lang="ts">
defineProps<{
    label: string;
    value?: string;
    title?: string | null;
    wrap?: boolean;
}>();
</script>
