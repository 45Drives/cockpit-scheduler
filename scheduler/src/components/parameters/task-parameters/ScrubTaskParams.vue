<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'"/>
        </div>
    </div>
    <div v-else class="grid grid-flow-cols grid-cols-2 my-2 gap-2">
        <div name="scrub-data" class="border border-default rounded-md p-2 col-span-2 bg-accent">
            <div class="flex flex-row justify-between items-center text-center">
                <label class="block text-base leading-6 text-default">Pool to Scrub</label>
                <div class="mt-1 flex flex-col items-center text-center">
                    <label class="block text-xs text-default">Custom</label>
                    <input type="checkbox" v-model="inputPoolName" class="h-4 w-4 rounded"/>
                </div>
            </div>   
            <div name="pool-name">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                    <ExclamationCircleIcon v-if="poolNameErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <div v-if="inputPoolName">
                    <input
                        type="text"
                        v-model="pool"
                        :class="[
                        'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                        poolNameErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]"
                        placeholder="Specify Pool"
                    />
                </div>
                <div v-else>
                    <select
                        v-model="pool"
                        :class="[
                            'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                            poolNameErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]"
                    >
                        <option value="">Select a Pool</option>
                        <option v-if="!loadingPools" v-for="pool in pools" :value="pool">{{ pool }}</option>
                        <option v-if="loadingPools">Loading...</option>
                    </select>
                </div>
            </div>
        </div>
    
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, watch, inject } from 'vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import { ParameterNode, ZfsDatasetParameter, IntParameter, StringParameter, BoolParameter } from '../../../models/Parameters';
import { getPoolData } from '../../../composables/utility';

interface ScrubTaskParamsProps {
   parameterSchema: ParameterNodeType;
   task?: TaskInstanceType;
}

const props = defineProps<ScrubTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;

const pools = ref<string[]>([]);
const loadingPools = ref(false);

const pool = ref('');
const poolNameErrorTag = ref(false);
const inputPoolName = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

async function initializeData() {
    // if props.task, then edit mode active (retrieve data)
    if (props.task) {
        loading.value = true;
        await getPools();
        const params = props.task.parameters.children;
        const zfsParams = params.find(p => p.key === 'pool')!.children;
        pool.value = zfsParams.find(p => p.key === 'pool')!.value;

        loading.value = false;
    } else {
        //if no props.task, new task configuration (default values)
        await getPools();
    }
}

const getPools = async () => {
    loadingPools.value = true;
    pools.value = await getPoolData();
    loadingPools.value = false;
    console.log('pools:', pools.value);
}


function validatescrub() {
    if (inputPoolName.value) { 
        if (!isValidPoolName(pool.value)) {
            errorList.value.push("Pool is invalid.");
            poolNameErrorTag.value = true;
        }

        if (!doesItExist(pool.value, pools.value)) {
            errorList.value.push("Pool does not exist.");
            poolNameErrorTag.value = true;
        }
    } else {
        if (pool.value === '') {
            errorList.value.push("Pool is needed.");
            poolNameErrorTag.value = true;
        } else {
            if (!doesItExist(pool.value, pools.value)) {
                errorList.value.push("Pool does not exist.");
                poolNameErrorTag.value = true;
            }
        }
    }
}

function isValidPoolName(poolName) {
    if (poolName === '') {
        return false;
    }
    if (/^(c[0-9]|log|mirror|raidz[123]?|spare)/.test(poolName)) {
        return false;
    }
    if (/^[0-9._: -]/.test(poolName)) {
        return false;
    }
    if (!/^[a-zA-Z0-9_.:-]*$/.test(poolName)) {
        return false;
    }
    if (poolName.match(/[ ]$/)) {
        return false;
    }
    return true;
}

function doesItExist(thisName: string, list: string[]) {
    if (list.includes(thisName)) {
        return true;
    } else {
        return false;
    }
}

function clearErrorTags() {
    poolNameErrorTag.value = false;
    errorList.value = [];
}

function validateParams() {
    validatescrub();

    if (errorList.value.length == 0) {
        setParams();
    }

}

function setParams() {
    const newParams = new ParameterNode("Scrub Task Config", "scrubConfig")
            .addChild(new ZfsDatasetParameter('Pool', 'pool', '', 0, '', pool.value, ''));

        parameters.value = newParams;
        console.log('newParams:', newParams);
}

onMounted(async () => {
    await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
});
</script>