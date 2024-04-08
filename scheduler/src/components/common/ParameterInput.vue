<template>
    <div class="mt-2">
       <!--  <div v-if="props.param.children.length > 0">
            <div v-for="child in props.param.children">
                <label class="mt-1 block text-sm leading-6 text-default">{{ child.label }}</label>
                <input type="text" v-model="child.value" class="mt-1 block w-full input-textlike bg-default" />
            </div>
        </div>
        <div v-else>
            <label class="mt-1 block text-sm leading-6 text-default">{{ props.param.label }}</label>
            <input type="text" v-model="props.param.value" class="mt-1 block w-full input-textlike bg-default" />
        </div> -->
        <div>
            <!-- <StringParam v-if="props.type == 'string'" />
            <IntParam v-if="props.type == 'int'"/>
            <BoolParam v-if="props.type == 'bool'"/>
            <SelectParam v-if="props.type == 'select'"/> -->
        </div>
    </div>
</template>
<script setup lang="ts">
import StringParam from '../parameters/StringParam.vue';
import BoolParam from '../parameters/BoolParam.vue';
import SelectParam from '../parameters/SelectParam.vue';
import IntParam from '../parameters/IntParam.vue';
import { ref, Ref, reactive } from 'vue';

interface ParameterInputProps {
    param: ParameterNodeType;
    type: string;
}

const props = defineProps<ParameterInputProps>();
</script>