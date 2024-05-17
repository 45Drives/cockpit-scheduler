<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'"/>
        </div>
    </div>
    <div v-if="!loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2">
        <div name="source-data" class="border border-default rounded-md p-2 col-span-2 bg-accent">
            <div class="flex flex-row justify-between items-center text-center">
                <label class="mt-1 block text-base leading-6 text-default">Filesystem to Snapshot</label>
                <div class="mt-1 flex flex-col items-center text-center">
                    <label class="block text-xs text-default">Custom</label>
                    <input type="checkbox" v-model="useCustomSource" class="h-4 w-4 rounded"/>
                </div>
            </div>   
            <div name="source-pool">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                    <ExclamationCircleIcon v-if="sourcePoolErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <div v-if="!useCustomSource">
                    <select v-if="!sourcePoolErrorTag" v-model="sourcePool" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option value="">Select a Pool</option>
                        <option v-if="!loadingSourcePools" v-for="pool in sourcePools" :value="pool">{{ pool }}</option>
                        <option v-if="loadingSourcePools">Loading...</option>
                    </select>
                    <select v-if="sourcePoolErrorTag" v-model="sourcePool" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6 outline outline-1 outline-rose-500 dark:outline-rose-700">
                        <option value="">Select a Pool</option>
                        <option v-if="!loadingSourcePools" v-for="pool in sourcePools" :value="pool">{{ pool }}</option>
                    </select>
                </div>
                <div v-if="useCustomSource">
                    <input v-if="!customSrcPoolErrorTag" type="text" v-model="sourcePool" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Pool"/> 
                    <input v-if="customSrcPoolErrorTag" type="text" v-model="sourcePool" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Pool"/> 
                </div>
            </div>
            <div name="source-dataset">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Dataset</label>
                    <ExclamationCircleIcon v-if="sourceDatasetErrorTag || customSrcDatasetErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <div v-if="!useCustomSource">
                    <select v-if="!sourceDatasetErrorTag" v-model="sourceDataset" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option value="">Select a Dataset</option>
                        <option v-if="!loadingSourceDatasets" v-for="dataset in sourceDatasets" :value="dataset">{{ dataset }}</option>
                        <option v-if="loadingSourceDatasets">Loading...</option>
                    </select>
                    <select v-if="sourceDatasetErrorTag" v-model="sourceDataset" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6 outline outline-1 outline-rose-500 dark:outline-rose-700">
                    <option value="">Select a Dataset</option>
                        <option v-if="!loadingSourceDatasets" v-for="dataset in sourceDatasets" :value="dataset">{{ dataset }}</option>
                    </select>
                </div>
                <div v-if="useCustomSource">
                    <input v-if="!customSrcDatasetErrorTag" type="text" v-model="sourceDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Dataset"/> 
                    <input v-if="customSrcDatasetErrorTag" type="text" v-model="sourceDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Dataset"/> 
                </div>
            </div>
            <div name="source-snapshot-retention">
                <label class="mt-1 block text-sm leading-6 text-default">Snapshots to Keep</label>
                <input type="number" min="0" v-model="snapsToKeep" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder=""/> 
            </div>

            <div class="flex flex-row gap-2 mt-2">
                <div name="custom-snapshot-name-toggle" class="flex flex-row items-center justify-between">
                    <div class="flex flex-row items-center gap-2 mt-2 whitespace-nowrap">
                        <label class="block text-sm leading-6 text-default">Use Custom Name Schema?</label>
                        <input type="checkbox" v-model="useCustomName" class=" h-4 w-4 rounded"/>
                    </div>
                    <ExclamationCircleIcon v-if="customNameErrorTag" class="mt-2 w-5 h-5 text-danger"/>
                </div>
                <div name="custom-snapshot-name-field" class="mt-1 flex-grow">
                    <input v-if="useCustomName && !customNameErrorTag" type="text" v-model="customName" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Name is CustomName + Timestamp"/>
                    <input v-if="useCustomName && customNameErrorTag" type="text" v-model="customName" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Name is CustomName + Timestamp"/>
                    <input v-if="!useCustomName" disabled type="text" v-model="customName" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Name is Timestamp"/>
                </div>
                <div name="send-opt-recursive" class="flex flex-row items-center gap-2 mt-2">
                    <label class="block text-sm leading-6 text-default">Recursive Snapshots</label>
                    <input type="checkbox" v-model="sendRecursive" class="h-4 w-4 rounded"/>
                </div>
            </div>
        </div>
    
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, watch, inject } from 'vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../common/CustomLoadingSpinner.vue';
import { ParameterNode, ZfsDatasetParameter, IntParameter, StringParameter, BoolParameter } from '../../models/Parameters';
import { getPoolData, getDatasetData } from '../../composables/utility';

interface AutomatedSnapshotTaskParamsProps {
   parameterSchema: ParameterNodeType;
   task?: TaskInstanceType;
}

const props = defineProps<AutomatedSnapshotTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;

const sourcePools = ref<string[]>([]);
const sourceDatasets = ref<string[]>([]);
const loadingSourcePools = ref(false);
const loadingSourceDatasets = ref(false);

const sourcePool = ref('');
const sourcePoolErrorTag = ref(false);
const sourceDataset = ref('');
const sourceDatasetErrorTag = ref(false);

const sendRecursive = ref(false);
const useCustomName = ref(false);
const customName = ref('');
const customNameErrorTag = ref(false);
const snapsToKeep = ref(5);

const useCustomSource = ref(false);
const customSrcPoolErrorTag = ref(false);
const customSrcDatasetErrorTag = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

async function initializeData() {
    // if props.task, then edit mode active (retrieve data)
    if (props.task) {
        loading.value = true;
        await getSourcePools();
        const params = props.task.parameters.children;
        const filesystemParams = params.find(p => p.key === 'filesystem')!.children;
        sourcePool.value = filesystemParams.find(p => p.key === 'pool')!.value;
        await getSourceDatasets();
        sourceDataset.value = filesystemParams.find(p => p.key === 'dataset')!.value;
        sendRecursive.value = params.find(p => p.key === 'recursive_flag')!.value;
        useCustomName.value = params.find(p => p.key === 'customName_flag')!.value;
        customName.value = params.find(p => p.key === 'customName')!.value;
        snapsToKeep.value = params.find(p => p.key === 'snapRetention')!.value;

        loading.value = false;
    } else {
        //if no props.task, new task configuration (default values)
        await getSourcePools();
    }
}

const getSourcePools = async () => {
    loadingSourcePools.value = true;
    sourcePools.value = await getPoolData();
    loadingSourcePools.value = false;
    console.log('sourcePools:', sourcePools.value);
}

const getSourceDatasets = async () => {
    loadingSourceDatasets.value = true;
    sourceDatasets.value = await getDatasetData(sourcePool.value);
    loadingSourceDatasets.value = false;
    console.log('sourceDatasets:', sourceDatasets.value);
}

const handleSourcePoolChange = async (newVal) => {
    if (newVal) {
        await getSourceDatasets();
    }
}


function validateCustomName() {
    if (useCustomName.value) {
        if (customName.value !== '') {
            const snapNameRegex = /^[a-zA-Z0-9_.-]+$/;
            if (!snapNameRegex.test(customName.value)) {
                errorList.value.push("Snapshot name must only contain valid characters (alphanumerics, dots, underscores, and hyphens).");
                customNameErrorTag.value = true;
            }
        } else {
            errorList.value.push("Custom name is required if box is checked.");
            customNameErrorTag.value = true;
        }
        
    }
}

function validateSource() {
    if (useCustomSource.value) { 
        if (!isValidPoolName(sourcePool.value)) {
            errorList.value.push("Pool is invalid.");
            customSrcPoolErrorTag.value = true;
        }
        if (!isValidDatasetName(sourceDataset.value)) {
            errorList.value.push("Dataset is invalid.");
            customSrcDatasetErrorTag.value = true;
        }
        if (!doesItExist(sourcePool.value, sourcePools.value)) {
            errorList.value.push("Pool does not exist.");
            customSrcPoolErrorTag.value = true;
        }
        if (!doesItExist(sourceDataset.value, sourceDatasets.value)) {
            errorList.value.push("Dataset does not exist.");
            customSrcDatasetErrorTag.value = true;
        }
    } else {
        if (sourcePool.value === '') {
            errorList.value.push("Pool is needed.");
            sourcePoolErrorTag.value = true;
        } else {
            if (!doesItExist(sourcePool.value, sourcePools.value)) {
                errorList.value.push("Pool does not exist.");
                customSrcPoolErrorTag.value = true;
            }
        }
        if (sourceDataset.value === '') {
            errorList.value.push("Dataset is needed.");
            sourceDatasetErrorTag.value = true;
        } else {
            if (!doesItExist(sourceDataset.value, sourceDatasets.value)) {
                errorList.value.push("Dataset does not exist.");
                customSrcDatasetErrorTag.value = true;
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


function isValidDatasetName(datasetName) {
    if (datasetName === '') {
        return false;
    }
    // Check if it starts with alphanumeric characters (not a slash)
    if (!/^[a-zA-Z0-9]/.test(datasetName)) {
        return false;
    }
    // Check if it ends with whitespace or a slash
    if (/[ \/]$/.test(datasetName)) {
        return false;
    }
    // Check for valid characters throughout the string, allowing internal slashes
    if (!/^[a-zA-Z0-9_.:\/-]*$/.test(datasetName)) {
        return false;
    }
    return true;
}

function clearErrorTags() {
    customNameErrorTag.value = false;
    sourcePoolErrorTag.value = false;
    sourceDatasetErrorTag.value = false;
    customSrcPoolErrorTag.value = false;
    customSrcDatasetErrorTag.value = false;
    errorList.value = [];
}

function validateParams() {
    validateSource();
    validateCustomName();

    if (errorList.value.length == 0) {
        setParams();
    }

}

function setParams() {
    const newParams = new ParameterNode("Automated Snapshot Task Config", "autoSnapConfig")
            .addChild(new ZfsDatasetParameter('Filesystem', 'filesystem', '', 0, '', sourcePool.value, sourceDataset.value))
            .addChild(new BoolParameter('Recursive', 'recursive_flag', sendRecursive.value))
            .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', useCustomName.value))
            .addChild(new StringParameter('Custom Name', 'customName', customName.value))
            .addChild(new IntParameter('Snapshot Retention', 'snapRetention', snapsToKeep.value)
        );

        parameters.value = newParams;
        console.log('newParams:', newParams);
}

watch(sourcePool, handleSourcePoolChange);

onMounted(async () => {
    await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
});
</script>