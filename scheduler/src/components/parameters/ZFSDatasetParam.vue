<template>
  <div class="mt-2">
        <!-- <div v-if="props.param.children.length > 0">
            <div v-for="child in props.param.children">
                <label class="mt-1 block text-sm leading-6 text-default">{{ child.label }}</label>
                <input type="text" v-model="props.param.value" class="mt-1 block w-full input-textlike bg-default" />
            </div>
        </div>
        <div v-else>
            <label class="mt-1 block text-sm leading-6 text-default">{{ props.param.label }}</label>
            <input type="text" v-model="props.param.value" class="mt-1 block w-full input-textlike bg-default" />
        </div> -->
        <!-- <div>
                <label>{{ label }}</label>
                <div>
                    <label>Host:</label>
                    <input v-model="host" />
                </div>
                <div>
                    <label>Port:</label>
                    <input v-model.number="port" type="number" />
                </div>
                 <div>
                    <label>User:</label>
                    <input v-model.number="user" />
                </div>
                <div>
                    <label>Pool:</label>
                    <select v-model="pool">
                        <option v-for="option in poolOptions" :value="option">{{ option }}</option>
                    </select>
                </div>
                <div>
                    <label>Dataset:</label>
                    <select v-model="dataset">
                        <option v-for="option in datasetOptions" :value="option">{{ option }}</option>
                    </select>
                </div>
            </div> -->
    </div>
</template>
<script setup lang="ts">
import { ref } from 'vue';

interface ZFSDatasetParamProps {
    param: ParameterNodeType;
}

const props = defineProps<ZFSDatasetParamProps>();




</script>
  