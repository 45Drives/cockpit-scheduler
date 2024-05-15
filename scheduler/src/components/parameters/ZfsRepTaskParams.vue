<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-40'" :height="'h-40'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'"/>
        </div>
    </div>
    <div v-if="!loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <!-- TOP LEFT -->
        <div name="source-data" class="border border-default rounded-md p-2 col-span-1 row-start-1 row-span-1 bg-accent">
            <div class="flex flex-row justify-between items-center text-center">
                <label class="mt-1 block text-base leading-6 text-default">Source Location</label>
                <div class="mt-1 flex flex-col items-center text-center">
                    <label class="block text-xs text-default">Custom</label>
                    <input type="checkbox" v-model="useCustomSource" class="h-4 w-4 rounded"/>
                </div>
            </div>   
            <div name="source-pool">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                    <ExclamationCircleIcon v-if="sourcePoolErrorTag || customDestPoolErrorTag" class="mt-1 w-5 h-5 text-danger"/>
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
                    <input v-if="!customSrcPoolErrorTag" type="text" v-model="sourcePool" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Source Pool"/> 
                    <input v-if="customSrcPoolErrorTag" type="text" v-model="sourcePool" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Source Pool"/> 
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
                    <input v-if="!customSrcDatasetErrorTag" type="text" v-model="sourceDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Source Dataset"/> 
                    <input v-if="customSrcDatasetErrorTag" type="text" v-model="sourceDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Source Dataset"/> 
                    <!-- <input v-if="!customSrcDatasetErrorTag" type="text" v-model="computedSourceDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Source Dataset"/> 
                    <input v-if="customSrcDatasetErrorTag" type="text" v-model="computedSourceDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Source Dataset"/>  -->
                </div>
            </div>
            <div name="source-snapshot-retention">
                <label class="mt-1 block text-sm leading-6 text-default">Snapshots to Keep (Source)</label>
                <input type="number" min="0" v-model="snapsToKeepSrc" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder=""/> 
            </div>
        </div>

        <!-- BOTTOM LEFT -->
        <div name="destination-data" class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent">
            <div class="flex flex-row justify-between items-center">
                <label class="mt-1 block text-base leading-6 text-default">Target Location</label>
                <div class="mt-1 flex flex-col items-center text-center">
                    <label class="block text-xs text-default">Custom</label>
                    <input type="checkbox" v-model="useCustomTarget" class="h-4 w-4 rounded"/>
                </div>
            </div>
            <div name="destination-pool">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                    <ExclamationCircleIcon v-if="destPoolErrorTag || customDestPoolErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <div v-if="!useCustomTarget">
                    <select v-if="!destPoolErrorTag" v-model="destPool" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option value="">Select a Pool</option>
                        <option v-if="!loadingDestPools" v-for="pool in destPools" :value="pool">{{ pool }}</option>
                        <option v-if="loadingDestPools">Loading...</option>
                    </select>
                    <select v-if="destPoolErrorTag" v-model="destPool" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6 outline outline-1 outline-rose-500 dark:outline-rose-700">
                        <option value="">Select a Pool</option>
                        <option v-if="!loadingDestPools" v-for="pool in destPools" :value="pool">{{ pool }}</option>
                    </select>
                </div>
                <div v-if="useCustomTarget">
                    <input v-if="!customDestPoolErrorTag" type="text" v-model="destPool" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Target Pool"/> 
                    <input v-if="customDestPoolErrorTag" type="text" v-model="destPool" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Target Pool"/> 
                </div>
            </div>
            <div name="destination-dataset">
                <!--    <div class="flex flex-row justify-between items-center">
                            <label class="mt-1 block text-base leading-6 text-default">Target Location</label>
                            <div class="mt-1 flex flex-col items-center text-center">
                                <label class="block text-xs text-default">Custom</label>
                                <input type="checkbox" v-model="useCustomTarget" class="h-4 w-4 rounded"/>
                            </div>
                        </div> -->
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Dataset</label>
                    <ExclamationCircleIcon v-if="destDatasetErrorTag || customDestDatasetErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <div v-if="!useCustomTarget">
                    <select v-if="!destDatasetErrorTag" v-model="destDataset" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option value="">Select a Dataset</option>
                        <option v-if="!loadingDestDatasets" v-for="dataset in destDatasets" :value="dataset">{{ dataset }}</option>
                        <option v-if="loadingDestDatasets">Loading...</option>
                    </select>
                    <select v-if="destDatasetErrorTag" v-model="destDataset" class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6 outline outline-1 outline-rose-500 dark:outline-rose-700">
                        <option value="">Select a Dataset</option>
                        <option v-if="!loadingDestDatasets" v-for="dataset in destDatasets" :value="dataset">{{ dataset }}</option>
                    </select>
                </div>
                <div v-if="useCustomTarget">
                    <div class="flex flex-row justify-between items-center w-full flex-grow">
                        <input v-if="!customDestDatasetErrorTag" type="text" v-model="destDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Target Dataset"/>
                        <input v-if="customDestDatasetErrorTag" type="text" v-model="destDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Target Dataset"/> 
                        <!-- <input v-if="!customDestDatasetErrorTag" type="text" v-model="computedDestDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Target Dataset"/>
                        <input v-if="customDestDatasetErrorTag" type="text" v-model="computedDestDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Target Dataset"/>  -->
                        <div v-if="useCustomTarget" class="-mt-3 m-1 flex flex-col items-center text-center flex-shrink">
                            <label class="block text-xs text-default">Create</label>
                            <input type="checkbox" v-model="makeNewDestDataset" class="h-4 w-4 rounded"/>
                        </div>
                    </div>
                    <!-- <input v-if="!customDestDatasetErrorTag" type="text" v-model="destDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Target Dataset"/> -->
                    <!-- <input v-if="customDestDatasetErrorTag" type="text" v-model="destDataset" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Target Dataset"/>  -->
                </div>
               
            </div>
            <div name="destination-snapshot-retention">
                <label class="mt-1 block text-sm leading-6 text-default">Snapshots to Keep (Destination)</label>
                <input type="number" min="0" v-model="snapsToKeepDest" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder=""/> 
            </div>
        </div>

        <!-- TOP RIGHT -->
        <div name="destination-ssh-data" class="border border-default rounded-md p-2 col-span-1 bg-accent">
            <div class="grid grid-cols-2">
                <label class="mt-1 col-span-1 block text-base leading-6 text-default">Remote Target</label>
                <div class="col-span-1 items-end text-end justify-end">
                    <button v-if="!testingSSH" @click="confirmTest(destHost, destUser)" class="mt-0.5 btn btn-secondary object-right justify-end h-fit">Test SSH</button>
                    <button disabled v-if="testingSSH" class="mt-0.5 btn btn-secondary object-right justify-end h-fit">
                            <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                                <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                            </svg>
                            Testing...
                    </button>
                </div> 
            </div>
            <div name="destination-host" class="mt-1">
                <div class="flex flex-row justify-between items-center">
                    <label class="block text-sm leading-6 text-default">Host</label>
                    <ExclamationCircleIcon v-if="destHostErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <input v-if="!destHostErrorTag" type="text" v-model="destHost" @input="debouncedDestHostChange($event.target)" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Leave blank for local replication."/> 
                <input v-if="destHostErrorTag" type="text" v-model="destHost" @input="debouncedDestHostChange($event.target)" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Leave blank for local replication."/> 
            </div>
            <div name="destination-user" class="mt-1">
                <label class="block text-sm leading-6 text-default">User</label>
                <input v-if="destHost !== ''" type="text" v-model="destUser" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="'root' is default"/> 
                <input v-if="destHost === ''" disabled type="text" v-model="destUser" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="'root' is default"/> 
            </div>
            <div name="destination-port" class="mt-1">
                <label class="block text-sm leading-6 text-default">Port</label>
                <input v-if="destHost !== ''" type="number" v-model="destPort" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" min="0" max="65535" placeholder="22 is default"/> 
                <input v-if="destHost === ''" disabled type="number" v-model="destPort" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" min="0" max="65535" placeholder="22 is default"/>
            </div>
        </div>
        
        <!-- BOTTOM RIGHT -->
        <div name="send-options" class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent">
            <label class="mt-1 block text-base leading-6 text-default">Send Options</label>
            <div class="grid grid-cols-2 mt-1">
                <div name="send-opt-raw" class="flex flex-row items-center gap-2 mt-1 col-span-1">
                    <label class="block text-sm leading-6 text-default">Send Raw</label>
                    <input type="checkbox" v-model="sendRaw" @change="handleCheckboxChange('sendRaw')" class=" h-4 w-4 rounded"/>
                </div>
                <div name="send-opt-compressed" class="flex flex-row items-center gap-2 mt-1 col-span-1">
                    <label class="block text-sm leading-6 text-default">Send Compressed</label>
                    <input type="checkbox" v-model="sendCompressed" @change="handleCheckboxChange('sendCompressed')" class=" h-4 w-4 rounded"/>
                </div>
            </div>
            <div name="send-opt-recursive" class="flex flex-row items-center gap-2 mt-2">
                <label class="block text-sm leading-6 text-default">Send Recursive</label>
                <input type="checkbox" v-model="sendRecursive" class="h-4 w-4 rounded"/>
            </div>
            <div name="send-opt-custom-name mt-2">
                <div name="custom-snapshot-name-toggle" class=" flex flex-row items-center justify-between">
                    <div  class="flex flex-row items-center gap-2 mt-2">
                        <label class="block text-sm leading-6 text-default">Use Custom Snapshot Name?</label>
                        <input type="checkbox" v-model="useCustomName" class=" h-4 w-4 rounded"/>
                    </div>
                    <ExclamationCircleIcon v-if="customNameErrorTag" class="mt-2 w-5 h-5 text-danger"/>
                </div>
                <div name="custom-snapshot-name-field" class="mt-1">
                    <input v-if="useCustomName && !customNameErrorTag" type="text" v-model="customName" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Name is CustomName + Timestamp"/>
                    <input v-if="useCustomName && customNameErrorTag" type="text" v-model="customName" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Name is CustomName + Timestamp"/>
                    <input v-if="!useCustomName" disabled type="text" v-model="customName" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Name is Timestamp"/>
                </div>
            </div>
            <div class="grid grid-cols-2 mt-2">
                <div name="send-opt-mbuffer" class="col-span-1">
                    <label class="block text-sm leading-6 text-default">mBuffer Size (Remote)</label>
                    <input v-if="destHost !== ''" type="number" v-model="mbufferSize" min="1" class="mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="1"/>
                    <input v-if="destHost === ''" disabled type="number" v-model="mbufferSize" min="1" class="mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="1"/>
                </div>
                  <div name="send-opt-mbuffer" class="col-span-1">
                    <div name="send-opt-mbuffer-unit">
                        <label class="block text-sm leading-6 text-default">mBuffer Unit (Remote)</label>
                        <select v-if="destHost !== ''" v-model="mbufferUnit" class="text-default bg-default mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6">
                                <option value="b">b</option>
                                <option value="k">k</option>
                                <option value="M">M</option>
                                <option value="G">G</option>
                        </select>
                        <select v-if="destHost === ''" disabled v-model="mbufferUnit" class="text-default bg-default mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6">
                                <option value="b">b</option>
                                <option value="k">k</option>
                                <option value="M">M</option>
                                <option value="G">G</option>
                        </select>
                    </div>
                </div>
            </div>
            
        </div>
    
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, watch, inject } from 'vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../common/CustomLoadingSpinner.vue';
import { ParameterNode, ZfsDatasetParameter, IntParameter, StringParameter, BoolParameter } from '../../models/Classes';
import { getPoolData, getDatasetData, testSSH } from '../../composables/utility';
import { pushNotification, Notification } from 'houston-common-ui';

interface ZfsRepTaskParamsProps {
   parameterSchema: ParameterNodeType;
   task?: TaskInstanceType;
}

const props = defineProps<ZfsRepTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;

const sourcePools = ref<string[]>([]);
const sourceDatasets = ref<string[]>([]);
const loadingSourcePools = ref(false);
const loadingSourceDatasets = ref(false);

const destPools = ref<string[]>([]);
const destDatasets = ref<string[]>([]);
const loadingDestPools = ref(false);
const loadingDestDatasets = ref(false);

const sourcePool = ref('');
const sourcePoolErrorTag = ref(false);
const sourceDataset = ref('');
const sourceDatasetErrorTag = ref(false);

const destPool = ref('');
const destPoolErrorTag = ref(false);
const destDataset = ref('');
const destDatasetErrorTag = ref(false);

const destHost = ref('');
const destHostErrorTag = ref(false);
const destPort = ref(22);
const destUser = ref('root');

const sendRaw = ref(false);
const sendCompressed = ref(false);
const sendRecursive = ref(false);
const mbufferSize = ref(1);
const mbufferUnit = ref('G');
const useCustomName = ref(false);
const customName = ref('');
const customNameErrorTag = ref(false);
const snapsToKeepSrc = ref(5);
const snapsToKeepDest = ref(5);

const useCustomTarget = ref(false);
const useCustomSource = ref(false);
const customSrcPoolErrorTag = ref(false);
const customSrcDatasetErrorTag = ref(false);
const customDestPoolErrorTag = ref(false);
const customDestDatasetErrorTag = ref(false);

const makeNewDestDataset = ref(false);

const testingSSH = ref(false);
const sshTestResult = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

async function initializeData() {
    // if props.task, then edit mode active (retrieve data)
    if (props.task) {
        loading.value = true;
        await getSourcePools();
        const isRemoteAccessible = ref(false);
        const params = props.task.parameters.children;

        const sourceDatasetParams = params.find(p => p.key === 'sourceDataset')!.children;
        sourcePool.value = sourceDatasetParams.find(p => p.key === 'pool')!.value;
        await getSourceDatasets();
        sourceDataset.value = sourceDatasetParams.find(p => p.key === 'dataset')!.value;
        if (!doesItExist(sourcePool.value, sourcePools.value) || !doesItExist(sourceDataset.value, sourceDatasets.value)) {
            useCustomSource.value = true;
        }
        const destDatasetParams = params.find(p => p.key === 'destDataset')!.children;
        destHost.value = destDatasetParams.find(p => p.key === 'host')!.value;
        destPort.value = destDatasetParams.find(p => p.key === 'port')!.value;
        destUser.value = destDatasetParams.find(p => p.key === 'user')!.value;
        if (destHost.value !== '') {
            const sshTarget = destUser.value + '@' + destHost.value;
            isRemoteAccessible.value = await testSSH(sshTarget);
            if (isRemoteAccessible.value) {
                pushNotification(new Notification('SSH Connection Available', `Passwordless SSH connection established. This host can be used for replication (Assuming ZFS exists on target).`, 'success', 8000))
                await getRemoteDestinationPools();
                destPool.value = destDatasetParams.find(p => p.key === 'pool')!.value;
                await getRemoteDestinationDatasets();
                destDataset.value = destDatasetParams.find(p => p.key === 'dataset')!.value;
            } else {
                pushNotification(new Notification('SSH Connection Failed', `Passwordless SSH connection refused with this user/host/port. Please confirm SSH configuration or choose a new target.`, 'error', 8000));
                await getLocalDestinationPools();
                destPool.value = '';
                await getLocalDestinationDatasets();
                destDataset.value = '';
            }
        } else {
            await getLocalDestinationPools();
            destPool.value = destDatasetParams.find(p => p.key === 'pool')!.value;
            await getLocalDestinationDatasets();
            destDataset.value = destDatasetParams.find(p => p.key === 'dataset')!.value;
        }
        if (!doesItExist(destPool.value, destPools.value) || !doesItExist(destDataset.value, destDatasets.value)) {
            useCustomTarget.value = true;
        }
        const sendOptionsParams = params.find(p => p.key === 'sendOptions')!.children;
        sendCompressed.value = sendOptionsParams.find(p => p.key === 'compressed_flag')!.value;
        sendRaw.value = sendOptionsParams.find(p => p.key === 'raw_flag')!.value;
        sendRecursive.value = sendOptionsParams.find(p => p.key === 'recursive_flag')!.value;
        mbufferSize.value = sendOptionsParams.find(p => p.key === 'mbufferSize')!.value;
        mbufferUnit.value = sendOptionsParams.find(p => p.key === 'mbufferUnit')!.value;
        useCustomName.value = sendOptionsParams.find(p => p.key === 'customName_flag')!.value;
        customName.value = sendOptionsParams.find(p => p.key === 'customName')!.value;

        const snapshotRetentionParams = params.find(p => p.key === 'snapRetention')!.children;
        snapsToKeepSrc.value = snapshotRetentionParams.find(p => p.key === 'source')!.value;
        snapsToKeepDest.value = snapshotRetentionParams.find(p => p.key === 'destination')!.value;

        loading.value = false;
    } else {
        //if no props.task, new task configuration (default values)
        await getSourcePools();
        await getLocalDestinationPools();
    }
}

function handleCheckboxChange(checkbox) {
    // Ensure only one checkbox (raw, compressed) is selected at a time
    if (checkbox === 'sendCompressed' && sendCompressed.value) {
        sendRaw.value = false;
    } else if (checkbox === 'sendRaw' && sendRaw.value) {
        sendCompressed.value = false;
    }
}

const handleDestHostChange = async (newVal) => {
    console.log("Handling destination host change:", newVal);
    if (newVal !== "") {
        await getRemoteDestinationPools();
    } else {
        await getLocalDestinationPools();
    }
}

function debounce(func, delay) {
    let timerId;
    return function (newVal) {
        if (timerId) clearTimeout(timerId);
        timerId = setTimeout(() => func(newVal), delay);
    };
}

const debouncedDestHostChange = debounce(handleDestHostChange, 500);

const handleSourcePoolChange = async (newVal) => {
    if (newVal) {
        await getSourceDatasets();
    }
}

const handleDestPoolChange = async (newVal) => {
    if (destHost.value != '') {
        if (newVal) {
            await getRemoteDestinationDatasets();
        }
    } else {
        if (newVal) {
            await getLocalDestinationDatasets();
        }
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

const getLocalDestinationPools = async () => {
    loadingDestPools.value = true;
    destPools.value = await getPoolData();
    loadingDestPools.value = false;
    console.log('Local destPools:', destPools.value);
}

const getLocalDestinationDatasets = async () => {
    loadingDestDatasets.value = true;
    destDatasets.value = await getDatasetData(destPool.value);
    loadingDestDatasets.value = false;
    console.log('Local destDatasets:', destDatasets.value);
}

const getRemoteDestinationPools = async () => {
    loadingDestPools.value = true;
    destPools.value = await getPoolData(destHost.value, destPort.value, destUser.value);
    loadingDestPools.value = false;
    console.log('Remote destPools:', destPools.value);
}


const getRemoteDestinationDatasets = async () => {
    loadingDestDatasets.value = true;
    destDatasets.value = await getDatasetData(destPool.value, destHost.value, destPort.value, destUser.value);
    loadingDestDatasets.value = false;
    console.log('Remote destDataset:', destDatasets.value);
}


function validateHost() {
    if (destHost.value !== "") {
        // Check overall length constraints
        if (destHost.value.length < 1 || destHost.value.length > 253) {
            errorList.value.push("Hostname must be between 1 and 253 characters in length.");
            destHostErrorTag.value = true;
        }

        // Regular expression to validate the hostname structure and characters
        const hostRegex = /^(?!-)(?:(?:[a-zA-Z0-9]-*)*[a-zA-Z0-9]\.?)+$/;
        if (!hostRegex.test(destHost.value)) {
            errorList.value.push("Hostname must only contain ASCII letters (a-z, case-insensitive), digits (0-9), and hyphens ('-'), with no trailing dot.");
            destHostErrorTag.value = true;
        }

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
            errorList.value.push("Source pool is invalid.");
            customSrcPoolErrorTag.value = true;
        }
        if (!isValidDatasetName(sourceDataset.value)) {
            errorList.value.push("Source dataset is invalid.");
            customSrcDatasetErrorTag.value = true;
        }
        if (!doesItExist(sourcePool.value, sourcePools.value)) {
            errorList.value.push("Source pool does not exist.");
            customSrcPoolErrorTag.value = true;
        }
        if (!doesItExist(sourceDataset.value, sourceDatasets.value)) {
            errorList.value.push("Source dataset does not exist.");
            customSrcDatasetErrorTag.value = true;
        }
    } else {
        if (sourcePool.value === '') {
            errorList.value.push("Source pool is needed.");
            sourcePoolErrorTag.value = true;
        } else {
            if (!doesItExist(sourcePool.value, sourcePools.value)) {
                errorList.value.push("Source pool does not exist.");
                customSrcPoolErrorTag.value = true;
            }
        }
        if (sourceDataset.value === '') {
            errorList.value.push("Source dataset is needed.");
            sourceDatasetErrorTag.value = true;
        } else {
            if (!doesItExist(sourceDataset.value, sourceDatasets.value)) {
                errorList.value.push("Source dataset does not exist.");
                customSrcDatasetErrorTag.value = true;
            }
        }
        
    }
}

function validateDestination() {
    if (useCustomTarget.value) {
        if (!isValidPoolName(destPool.value)) {
            errorList.value.push("Destination pool is invalid.");
            customDestPoolErrorTag.value = true;
        }
        if (!isValidDatasetName(destDataset.value)) {
            errorList.value.push("Destination dataset is invalid.");
            customDestDatasetErrorTag.value = true;
        }
        if (!doesItExist(destPool.value, destPools.value)) {
            errorList.value.push("Destination pool does not exist.");
            customDestPoolErrorTag.value = true;
        }
        if (!makeNewDestDataset.value) {
            if (!doesItExist(destDataset.value, destDatasets.value)) {
                errorList.value.push("Destination dataset does not exist.");
                customDestDatasetErrorTag.value = true;
            }
        }

    } else {
        if (destPool.value === '') {
            errorList.value.push("Destination pool is needed.");
            destPoolErrorTag.value = true;
        } else {
            if (!doesItExist(destPool.value, destPools.value)) {
                errorList.value.push("Destination pool does not exist.");
                customDestPoolErrorTag.value = true;
            }
        }
        if (destDataset.value === '') {
            errorList.value.push("Destination dataset is needed.");
            destDatasetErrorTag.value = true;
        } else {
            if (!doesItExist(destDataset.value, destDatasets.value)) {
                errorList.value.push("Destination dataset does not exist.");
                customDestDatasetErrorTag.value = true;
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
    destHostErrorTag.value = false;
    customNameErrorTag.value = false;
    sourcePoolErrorTag.value = false;
    sourceDatasetErrorTag.value = false;
    destPoolErrorTag.value = false;
    destDatasetErrorTag.value = false;
    customSrcPoolErrorTag.value = false;
    customSrcDatasetErrorTag.value = false;
    customDestPoolErrorTag.value = false;
    customDestDatasetErrorTag.value = false;
    errorList.value = [];
}

function validateParams() {
    // clearErrorTags();
    validateSource();
    validateHost();
    validateDestination();
    validateCustomName();

    if (errorList.value.length == 0) {
        setParams();
    }

}

function setParams() {
    const newParams = new ParameterNode("ZFS Replication Task Config", "zfsRepConfig")
        .addChild(new ZfsDatasetParameter('Source Dataset', 'sourceDataset', '', 0, '', sourcePool.value, sourceDataset.value))
            .addChild(new ZfsDatasetParameter('Destination Dataset', 'destDataset', '', 22, '', destPool.value, destDataset.value))
            .addChild(new ParameterNode('Send Options', 'sendOptions')
                .addChild(new BoolParameter('Compressed', 'compressed_flag', sendCompressed.value))
                .addChild(new BoolParameter('Raw', 'raw_flag', sendRaw.value))
                .addChild(new BoolParameter('Recursive', 'recursive_flag', sendRecursive.value))
                .addChild(new IntParameter('MBuffer Size', 'mbufferSize', mbufferSize.value))
                .addChild(new StringParameter('MBuffer Unit', 'mbufferUnit', mbufferUnit.value))
                .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', useCustomName.value))
                .addChild(new StringParameter('Custom Name', 'customName', customName.value))
            )
            .addChild(new ParameterNode('Snapshot Retention', 'snapRetention')
                .addChild(new IntParameter('Source', 'source', snapsToKeepSrc.value))
                .addChild(new IntParameter('Destination', 'destination', snapsToKeepDest.value)
            )
        );

        parameters.value = newParams;
        console.log('newParams:', newParams);
}

async function confirmTest(destHost, destUser) {
    testingSSH.value = true;

    const sshTarget = destUser + '@' + destHost;
    sshTestResult.value = await testSSH(sshTarget);

    if (sshTestResult.value) {
        pushNotification(new Notification('Connection Successful!', `Passwordless SSH connection established. This host can be used for replication (Assuming ZFS exists on target).`, 'success', 8000));
    } else {
        pushNotification(new Notification('Connection Failed', `Could not resolve hostname "${destHost}": \nName or service not known.\nMake sure passwordless SSH connection has been configured for target system.`, 'error', 8000));
    }
    testingSSH.value = false;
}

watch(destPool, handleDestPoolChange);
watch(sourcePool, handleSourcePoolChange);

onMounted(async () => {
    await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
});
</script>