<template>
    <section :class="[
        'rounded-md bg-accent'
    ]">
        <header class="flex items-start justify-between gap-3">
            <div>
                <h3 class="text-base text-default font-medium leading-6">{{ title }}</h3>
                <p v-if="description" class="text-xs text-muted mt-1">{{ description }}</p>
            </div>
            <div v-if="$slots['header-right']" class="shrink-0">
                <slot name="header-right" />
            </div>
        </header>

        <div class="mt-3">
            <slot />
        </div>

        <footer v-if="$slots.footer" class="mt-3 pt-3 border-t border-default/40">
            <slot name="footer" />
        </footer>
    </section>
</template>

<script setup lang="ts">
interface Props {
    title: string
    description?: string
}
defineProps<Props>()
</script>
