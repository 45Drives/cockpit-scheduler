<template>
    <div class="rounded border border-default bg-default p-3 space-y-1">
        <div class="flex items-start gap-2">
            <span v-if="showBadge"
                class="inline-flex items-center text-xs font-mono font-semibold bg-accent text-accent rounded px-1.5 py-0.5 flex-shrink-0"
                :title="`Snapshots for this interval are tagged with -t${index}`"
            >t{{ index }}</span>
            <p class="text-sm text-default break-words">Run {{ description }}.</p>
        </div>
        <template v-if="retention">
            <p v-if="retention.source || retention.destination" class="text-xs text-muted">
                Retention:
                <span v-if="retention.source">
                    Src {{ retention.source.retentionTime }} {{ retention.source.retentionUnit }}
                </span>
                <span v-if="retention.source && retention.destination"> / </span>
                <span v-if="retention.destination">
                    {{ isReplicationTask ? 'Dst ' : '' }}{{ retention.destination.retentionTime }} {{ retention.destination.retentionUnit }}
                </span>
            </p>
            <p v-else class="text-xs text-muted">No retention policy</p>
        </template>
    </div>
</template>

<script setup lang="ts">
defineProps<{
    index: number;
    showBadge?: boolean;
    description: string;
    retention?: any;
    isReplicationTask?: boolean;
}>();
</script>
