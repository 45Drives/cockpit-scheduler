<template>
  <div class="mt-2">
        <div v-if="props.param.children.length > 0">
            <div v-for="child in props.param.children">
                <label class="mt-1 block text-sm leading-6 text-default">{{ child.label }}</label>
                <input type="text" v-model="props.param.value" class="mt-1 block w-full input-textlike bg-default" />
            </div>
        </div>
        <div v-else>
            <label class="mt-1 block text-sm leading-6 text-default">{{ props.param.label }}</label>
            <input type="text" v-model="props.param.value" class="mt-1 block w-full input-textlike bg-default" />
        </div>
    </div>
</template>
<script setup lang="ts">
import { ref } from 'vue';

interface ZFSDatasetParamProps {
    param: ParameterNodeType;
}

const props = defineProps<ZFSDatasetParamProps>();




</script>
  