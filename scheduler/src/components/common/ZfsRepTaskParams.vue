<template>
    <div class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">

        <div name="source-data" class="border border-default rounded-md p-2 col-span-1 row-start-1 row-span-1 bg-accent">
            <label class="mt-1 block text-base leading-6 text-default">Source Location</label>
            <div name="source-pool">
                <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                <select v-model="sourcePool" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                    <option v-for="pool in sourcePools">{{ pool }}</option>
                </select>
            </div>
            <div name="source-dataset">
                <label class="mt-1 block text-sm leading-6 text-default">Dataset</label>
                <select v-model="sourceDataset" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                    <option v-for="dataset in sourceDatasets">{{ dataset }}</option>
                </select>
            </div>
            <div name="source-snapshot-retention">
                <label class="mt-1 block text-sm leading-6 text-default">Snapshots to Keep (Source)</label>
                <input type="number" v-model="snapsToKeepSrc" class="mt-1 block w-full input-textlike bg-default" placeholder=""/> 
            </div>
        </div>

        <div name="destination-data" class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent">
            <label class="mt-1 block text-base leading-6 text-default">Target Location</label>
            <div name="destination-pool">
                <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                <select v-model="destPool" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                    <option v-for="pool in destPools">{{ pool }}</option>
                </select>
            </div>
            <div name="destination-dataset">
                <label class="mt-1 block text-sm leading-6 text-default">Dataset</label>
                <select v-model="destDataset" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                    <option v-for="dataset in destDatasets">{{ dataset }}</option>
                </select>
            </div>
            <div name="destination-snapshot-retention">
                <label class="mt-1 block text-sm leading-6 text-default">Snapshots to Keep (Destination)</label>
                <input type="number" v-model="snapsToKeepDest" class="mt-1 block w-full input-textlike bg-default" placeholder=""/> 
            </div>
        </div>

        <div name="destination-ssh-data" class="border border-default rounded-md p-2 col-span-1 bg-accent">
            <div class="grid grid-cols-2 mt-1">
                <label class="col-span-1 block text-base leading-6 text-default">Remote Target</label>
                <div class="col-span-1 items-end text-end justify-end -mt-3">
                        <button v-if="!testingSSH" @click="confirmTest(destHost, destUser)" class="mt-1 btn btn-secondary object-right justify-end h-fit">Test SSH</button>
                        <button disabled v-if="testingSSH" class="btn btn-secondary object-right justify-end h-fit">
                                <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                    <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                                </svg>
                                Testing...
                        </button>
                    </div> 
                </div>
            <div name="destination-host" class="mt-0.5">
                <label class="block text-sm leading-6 text-default">Host</label>
                <input type="text" v-model="destHost" class="mt-0.5 block w-full input-textlike bg-default" placeholder="Leave blank for local replication."/> 
            </div>
            <div name="destination-user" class="mt-1">
                <label class="block text-sm leading-6 text-default">User</label>
                <input type="text" v-model="destUser" class="mt-0.5 block w-full input-textlike bg-default" placeholder="'root' is default"/> 
            </div>
            <div name="destination-port" class="mt-1">
                <label class="block text-sm leading-6 text-default">Port</label>
                <input type="number" v-model="destPort" class="mt-0.5 block w-full input-textlike bg-default" placeholder="22 is default"/> 
            </div>
            <div class="col-span-2">
                <p v-if="result" class="text-sm text-success mt-1">{{ resultMsg }}</p>
                <p v-if="!result" class="text-sm text-danger mt-1">{{ resultMsg }}</p>
            </div>
        </div>
        
        <div name="send-options" class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent">
            <label class="my-1 block text-base leading-6 text-default">Send Options</label>
            <div name="custom-snapshot-name-toggle" class="flex flex-row gap-3">
                <label class="block text-sm leading-6 text-default">Use Custom Snapshot Name?</label>
                <input type="checkbox" v-model="useCustomName" class="mt-0.5 h-4 w-4 rounded"/>
            </div>
            <div name="custom-snapshot-name-field" class="">
                <input v-if="useCustomName" type="text" v-model="customName" class="mt-1 block w-full input-textlike bg-default" placeholder="Name is CustomName + Timestamp"/>
                <input v-if="!useCustomName" disabled type="text" v-model="customName" class="mt-1 block w-full input-textlike bg-default" placeholder="Name is Timestamp"/>
            </div>
            <div name="send-opt-recursive" class="flex flex-row gap-3">
                <label class="mt-1 block text-sm leading-6 text-default">Send Recursive</label>
                <input type="checkbox" v-model="sendRecursive" class="mt-0.5 h-4 w-4 rounded"/>
            </div>
            <div name="send-opt-compressed" class="flex flex-row gap-3">
                <label class="mt-1 block text-sm leading-6 text-default">Send Compressed</label>
                <input type="checkbox" v-model="sendCompressed" class="mt-0.5 h-4 w-4 rounded"/>
            </div>
            <div name="send-opt-raw" class="flex flex-row gap-3">
                <label class="mt-1 block text-sm leading-6 text-default">Send Raw</label>
                <input type="checkbox" v-model="sendRaw" class="mt-0.5 h-4 w-4 rounded"/>
            </div>
            <div name="send-opt-mbuffer-size">

            </div>
            <div name="snapshot-mbuffer-unit">

            </div>
        </div>
    
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, reactive, computed, onMounted, watch } from 'vue';
import { ZFSReplicationTaskTemplate, TaskTemplate, ParameterNode, ZfsDatasetParameter, SelectionOption, SelectionParameter, IntParameter, StringParameter, BoolParameter, TaskInstance } from '../../models/Classes';
import { getTaskData, getPoolData, getDatasetData } from '../../composables/getData';
import { testSSH } from '../../composables/helpers';

interface ZfsRepTaskParamsProps {
   parameterSchema: ParameterNodeType;
}

const props = defineProps<ZfsRepTaskParamsProps>();


const sourcePools = ref([]);
const sourceDatasets = ref([]);
const destPools = ref([]);
const destDatasets = ref([]);

const sourcePool = ref('');
const sourceDataset = ref('');

const destPool = ref('');
const destDataset = ref('');

const destHost = ref('');
const destPort = ref(22);
const destUser = ref('root');

const sendRaw = ref(false);
const sendCompressed = ref(false);
const sendRecursive = ref(false);
const mbufferSize = ref(1);
const mbufferUnit = ref('G');
const useCustomName = ref(false);
const customName = ref('');
const snapsToKeepSrc = ref(0);
const snapsToKeepDest = ref(0);

const testingSSH = ref(false);
const resultMsg = ref('');
const result = ref(false);


// Function to handle actions when destHost changes
const handleDestHostChange = async (newVal) => {
    if (newVal !== "") {
        await getRemoteDestinationPools();
        await getRemoteDestinationDatasets();
    } else {
        await getLocalDestinationPools();
        await getLocalDestinationDatasets();
    }
}

const handleDestPoolChange = async (newVal) => {
    if (newVal) {
        await getRemoteDestinationDatasets();
    }
}

const handleSourcePoolChange = async (newVal) => {
    if (newVal) {
        await getLocalSourceDatasets();
    }
}

// Fetch and update destination pools based on host details
const getRemoteDestinationPools = async () => {
    // destPools.value = [];
    destPools.value = await getPoolData(destHost.value, destPort.value, destUser.value);
    console.log('Remote destPools:', destPools.value);
}


const getRemoteDestinationDatasets = async () => {
    destDatasets.value = await getDatasetData(destPool.value, destHost.value, destPort.value, destUser.value);
    console.log('Remote destDataset:', destDatasets.value);
}


const getLocalDestinationPools = async () => {
    destPools.value = await getPoolData();
    console.log('Local destPools:', destPools.value);
}

const getLocalDestinationDatasets = async () => {
    destDatasets.value = await getDatasetData(destPool.value);
    console.log('Local destDatasets:', destDatasets.value);
}

const getLocalSourceDatasets = async () => {
    sourceDatasets.value = await getDatasetData(sourcePool.value);
    console.log('Local sourceDatasets:', sourceDatasets.value);
}

// Watch the destHost for changes
watch(destHost, handleDestHostChange);
watch(destPool, handleDestPoolChange);
watch(sourcePool, handleSourcePoolChange);


async function initializeData() {
    sourcePools.value = await getPoolData();
    console.log('sourcePools:', sourcePools.value);
    // sourceDatasets.value = await getDatasetData(sourcePools.value[0])
    // console.log('sourceDatasets in sourcePool[0]:', sourceDatasets.value);
    // await getLocalDestinationPools();
}

async function confirmTest(destHost, destUser) {
    testingSSH.value = true;
    resultMsg.value = "";

    const sshTarget = destUser + '@' + destHost;
    result.value = await testSSH(sshTarget);

    if (result.value) {
        resultMsg.value = 'Connection Successful!';
    } else {
        resultMsg.value = `Connection Failed: Could not resolve hostname "${destHost}": Name or service not known.`;
    }
    testingSSH.value = false;
}

onMounted(async () => {
    await initializeData();
});

</script>