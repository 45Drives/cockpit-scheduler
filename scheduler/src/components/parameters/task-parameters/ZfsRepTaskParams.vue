<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                :fillColor="'fill-gray-500'" />
        </div>
    </div>
    <div v-else class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <!-- TOP LEFT -->
        <div name="source-data"
            class="border border-default rounded-md p-2 col-span-1 row-start-1 row-span-1 bg-accent">
            <div class="flex flex-row justify-between items-center text-center">
                <label class="-mt-1 block text-base leading-6 text-default">Source Location</label>
                <div class="mt-1 flex flex-col items-center text-center">
                    <label class="block text-xs text-default">Custom</label>
                    <input type="checkbox" v-model="useCustomSource" class="h-4 w-4 rounded" />
                </div>
            </div>
            <div name="source-pool">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                    <ExclamationCircleIcon v-if="sourcePoolErrorTag || customDestPoolErrorTag"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>
                <div v-if="useCustomSource">
                    <input type="text" v-model="sourcePool" :class="[
                        'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                        customSrcPoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" placeholder="Specify Pool" />
                </div>
                <div v-else>
                    <select v-model="sourcePool" :class="[
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                        sourcePoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]">
                        <option value="">Select a Pool</option>
                        <option v-if="!loadingSourcePools" v-for="pool in sourcePools" :value="pool">{{ pool }}</option>
                        <option v-if="loadingSourcePools">Loading...</option>
                    </select>
                </div>
            </div>
            <div name="source-dataset">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Dataset</label>
                    <ExclamationCircleIcon v-if="sourceDatasetErrorTag || customSrcDatasetErrorTag"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>
                <div v-if="useCustomSource">
                    <div v-if="useCustomSource">
                        <input type="text" v-model="sourceDataset" :class="[
                            'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                            customSrcDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]" placeholder="Specify Dataset" />
                    </div>
                </div>
                <div v-else>
                    <select v-model="sourceDataset" :class="[
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                        sourceDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]">
                        <option value="">Select a Dataset</option>
                        <option v-if="!loadingSourceDatasets" v-for="dataset in sourceDatasets" :value="dataset">{{
                            dataset }}</option>
                        <option v-if="loadingSourceDatasets">Loading...</option>
                    </select>
                </div>
            </div>
            <div name="source-snapshot-retention" class="">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default whitespace-nowrap">
                        Source Retention Policy
                        <InfoTile class="ml-1"
                            :title="`How long to keep source snapshots for. Leave at 0 to keep ALL snapshots.\nWARNING: Disabling an automated task's schedule for a period of time longer than the retention interval and re-enabling the schedule may result in a purge of snapshots.`" />
                    </label>
                </div>
                <div class="flex flex-row gap-2 w-full items-center justify-between">
                    <input type="number" min="0" v-model="srcRetentionTime"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="" />
                    <select v-model="srcRetentionUnit"
                        class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option value="">Select an Interval</option>
                        <option v-for="option in retentionUnitOptions" :key="option" :value="option">
                            {{ option }}
                        </option>
                    </select>
                </div>
            </div>
        </div>

        <!-- BOTTOM LEFT -->
        <div name="destination-data"
            class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent">
            <div class="flex flex-row justify-between items-center">
                <label class="-mt-1 block text-base leading-6 text-default">Target Location</label>
                <!-- <div class="mt-1 flex flex-col items-center text-center">
                    <label class="block text-xs text-default">Custom</label>
                    <input type="checkbox" v-model="useCustomTarget" class="h-4 w-4 rounded" />
                </div> -->
                <div class="mt-1 flex items-center gap-4">
                    <label class="block text-xs text-default">Existing Dataset</label>
                    <input type="checkbox" v-model="useExistingDest" class="h-4 w-4 rounded" />
                </div>
            </div>
            <div name="destination-pool">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                    <ExclamationCircleIcon v-if="destPoolErrorTag || customDestPoolErrorTag"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>
                <!-- <div v-if="useCustomTarget">
                    <input type="text" v-model="destPool" :class="[
                        'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                        customDestPoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" placeholder="Specify Target Pool" />
                </div>
                <div v-else> -->
                <select v-model="destPool" :class="[
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                        destPoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]">
                    <option value="">Select a Pool</option>
                    <option v-if="!loadingDestPools" v-for="pool in destPools" :value="pool">{{ pool }}</option>
                    <option v-if="loadingDestPools">Loading...</option>
                </select>
                <!-- </div> -->
            </div>
            <div name="destination-dataset">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Dataset</label>
                    <ExclamationCircleIcon v-if="destDatasetErrorTag || customDestDatasetErrorTag"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>

                <!-- EXISTING DATASET: use a SELECT -->
                <div v-if="useExistingDest">
                    <select v-model="destDataset" :class="[
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                        destDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" :disabled="!destPool">
                        <option value="">{{ destPool ? 'Select a Dataset' : 'Select a Pool first' }}</option>
                        <option v-if="!loadingDestDatasets" v-for="dataset in destDatasets" :key="dataset"
                            :value="dataset">
                            {{ dataset }}
                        </option>
                        <option v-if="loadingDestDatasets">Loading...</option>
                    </select>
                </div>

                <!-- NEW DATASET: use a TEXT INPUT (Create flag enabled locally) -->
                <div v-else>
                    <div class="flex flex-row justify-between items-center w-full flex-grow">
                        <input type="text" v-model="destDataset" :class="[
                            'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                            customDestDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]" placeholder="Specify new dataset path to create on first run" />
                        <div v-if="!destHost" class="m-1 flex flex-col items-center text-center flex-shrink">
                            <label class="block text-xs text-default">Create</label>
                            <input type="checkbox" v-model="makeNewDestDataset" class="h-4 w-4 rounded" />
                        </div>
                    </div>
                </div>
            </div>

            <div name="destination-snapshot-retention" class="">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default whitespace-nowrap">
                        Destination Retention Policy
                        <InfoTile class="ml-1"
                            :title="`How long to keep destination snapshots for. Leave at 0 to keep ALL snapshots.\nWARNING: Disabling an automated task's schedule for a period of time longer than the retention interval and re-enabling the schedule may result in a purge of snapshots.`" />
                    </label>
                </div>
                <div class="flex flex-row gap-2 w-full items-center justify-between">
                    <input type="number" min="0" v-model="destRetentionTime"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="" />
                    <select v-model="destRetentionUnit"
                        class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option value="">Select an Interval</option>
                        <option v-for="option in retentionUnitOptions" :key="option" :value="option">
                            {{ option }}
                        </option>
                    </select>
                </div>
            </div>
            <div v-if="useExistingDest" name="migration-overwrite" class="mt-2 border-t border-default pt-2">
                <div class="flex items-center justify-between">
                    <label class="block text-sm leading-6 text-default">
                        Allow overwrite if no common base or destination is ahead
                    </label>
                    <input type="checkbox" v-model="allowOverwrite" class="h-4 w-4 rounded" />
                </div>
                <p class="mt-1 text-xs text-default/70">
                    If destination has diverged from the source, enabling this permits rollback with
                    <code>zfs receive -F</code>. Leave off to refuse destructive overwrite.
                </p>
            </div>
        </div>

        <!-- TOP RIGHT -->
        <div name="destination-ssh-data" class="border border-default rounded-md p-2 col-span-1 bg-accent">
            <div class="grid grid-cols-2">
                <label class="mt-1 col-span-1 block text-base leading-6 text-default">Select Transfer Method</label>
                <select v-model="transferMethod"
                    class="text-default bg-default mt-0 block w-full input-textlike sm:text-sm sm:leading-6"
                    id="method">
                    <option value="ssh">SSH</option>
                    <option value="netcat">Netcat</option>
                </select>

            </div>
            <div class="grid grid-cols-2 mt-2">
                <label class="mt-1 col-span-1 block text-base leading-6 text-default">Remote Target</label>
                <div class="col-span-1 items-end text-end justify-end">
                    <button disabled v-if="testingNetcat || testingSSH "
                        class="mt-0.5 btn btn-secondary object-right justify-end h-fit">
                        <svg aria-hidden="true" role="status"
                            class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101"
                            fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path
                                d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                                fill="currentColor" />
                            <path
                                d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                                fill="text-success" />
                        </svg>
                        Testing...
                    </button>
                    <button v-else-if="transferMethod === 'ssh'" @click="confirmSSHTest(destHost, destUser)"
                        class="mt-0.5 btn btn-secondary object-right justify-end h-fit">Test SSH</button>
                    <button v-else-if="transferMethod === 'netcat'" @click="confirmNetcatTest(destHost, destPort)"
                        class="mt-0.5 btn btn-secondary object-right justify-end h-fit">Test Netcat</button>
                </div>
            </div>
            <div name="destination-host" class="mt-1">
                <div class="flex flex-row justify-between items-center">
                    <label class="block text-sm leading-6 text-default">Host</label>
                    <ExclamationCircleIcon v-if="destHostErrorTag" class="mt-1 w-5 h-5 text-danger" />
                </div>
                <input type="text" v-model="destHost" @input="debouncedDestHostChange($event.target)" :class="[
                    'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                    destHostErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]" placeholder="Leave blank for local replication." />
            </div>
            <div name="destination-user" class="mt-1">
                <label class="block text-sm leading-6 text-default">User</label>
                <input v-if="destHost === ''" disabled type="text" v-model="destUser"
                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                    placeholder="'root' is default" />
                <input v-else type="text" v-model="destUser"
                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                    placeholder="'root' is default" />
            </div>
            <div name="destination-port" class="mt-1">
                <div class="flex flex-row justify-between items-center"><label
                        class="block text-sm leading-6 text-default">Port</label>
                    <ExclamationCircleIcon v-if="netCatPortError" class="mt-1 w-5 h-5 text-danger" />
                </div>
                <input v-if="destHost === ''" disabled type="number"
                    class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6"
                    v-model="destPort" min="0" max="65535" placeholder="22 is default" />
                <input v-else type="number" v-model="destPort" :class="[netCatPortError ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '',
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6'
                    ]" max="65535"
                    :placeholder="transferMethod === 'netcat' ? 'Enter port (not 22 for netcat)' : '22 is default' "
                    @input="validatePort" />
            </div>
        </div>

        <!-- BOTTOM RIGHT -->
        <div name="send-options"
            class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent">
            <label class="mt-1 block text-base leading-6 text-default">Send Options</label>
            <div class="grid grid-cols-2 mt-1">
                <div name="send-opt-raw" class="flex flex-row items-center gap-2 mt-1 col-span-1">
                    <label class="block text-sm leading-6 text-default">Send Raw</label>
                    <input type="checkbox" v-model="sendRaw" @change="handleCheckboxChange('sendRaw')"
                        class=" h-4 w-4 rounded" />
                </div>
                <div name="send-opt-compressed" class="flex flex-row items-center gap-2 mt-1 col-span-1">
                    <label class="block text-sm leading-6 text-default">Send Compressed</label>
                    <input type="checkbox" v-model="sendCompressed" @change="handleCheckboxChange('sendCompressed')"
                        class=" h-4 w-4 rounded" />
                </div>
            </div>
            <div name="send-opt-recursive" class="flex flex-row items-center gap-2 mt-2">
                <label class="block text-sm leading-6 text-default">Send Recursive</label>
                <input type="checkbox" v-model="sendRecursive" class="h-4 w-4 rounded" />
            </div>
            <div name="send-opt-custom-name mt-2">
                <div name="custom-snapshot-name-toggle" class=" flex flex-row items-center justify-between">
                    <div class="flex flex-row items-center gap-2 mt-2">
                        <label class="block text-sm leading-6 text-default">Use Custom Snapshot Name?</label>
                        <input type="checkbox" v-model="useCustomName" class=" h-4 w-4 rounded" />
                    </div>
                    <ExclamationCircleIcon v-if="customNameErrorTag" class="mt-2 w-5 h-5 text-danger" />
                </div>
                <div name="custom-snapshot-name-field" class="mt-1">
                    <input v-if="useCustomName" type="text" v-model="customName" :class="[
                        'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                        customNameErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" placeholder="Name is TaskName + CustomName + Timestamp" />
                    <input v-else disabled type="text" v-model="customName"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="Name is TaskName + Timestamp" />
                </div>
            </div>
            <div class="grid grid-cols-2 mt-2">
                <div name="send-opt-mbuffer" class="col-span-1">
                    <label class="block text-sm leading-6 text-default">mBuffer Size (Remote)</label>
                    <input v-if="destHost === ''" disabled type="number" v-model="mbufferSize" min="1"
                        class="mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="1" />
                    <input v-else type="number" v-model="mbufferSize" min="1"
                        class="mt-0.5 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="1" />
                </div>
                <div name="send-opt-mbuffer" class="col-span-1">
                    <div name="send-opt-mbuffer-unit">
                        <label class="block text-sm leading-6 text-default">mBuffer Unit (Remote)</label>
                        <select v-if="destHost === ''" disabled v-model="mbufferUnit"
                            class="text-default bg-default mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6">
                            <option value="b">b</option>
                            <option value="k">k</option>
                            <option value="M">M</option>
                            <option value="G">G</option>
                        </select>
                        <select v-else v-model="mbufferUnit"
                            class="text-default bg-default mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6">
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
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, ZfsDatasetParameter, IntParameter, StringParameter, BoolParameter, SnapshotRetentionParameter } from '../../../models/Parameters';
import { getPoolData, getDatasetData, testSSH, testNetcat, mostRecentCommonSnapshot, listSnapshots, ZfsSnap, destAheadOfCommon } from '../../../composables/utility';
import { pushNotification, Notification } from '@45drives/houston-common-ui';

interface ZfsRepTaskParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
}

const props = defineProps<ZfsRepTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const initialParameters: any = ref({});

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

const allowOverwrite = ref(false);

const sendRaw = ref(false);
const sendCompressed = ref(false);
const sendRecursive = ref(false);
const mbufferSize = ref(1);
const mbufferUnit = ref('G');
const useCustomName = ref(false);
const customName = ref('');
const customNameErrorTag = ref(false);

const srcRetentionTime = ref(0);
const srcRetentionUnit = ref('');
const destRetentionTime = ref(0);
const destRetentionUnit = ref('');
const retentionUnitOptions = ref(['minutes', 'hours', 'days', 'weeks', 'months', 'years'])

const useCustomTarget = ref(true);
const useCustomSource = ref(false);
const customSrcPoolErrorTag = ref(false);
const customSrcDatasetErrorTag = ref(false);
const customDestPoolErrorTag = ref(false);
const customDestDatasetErrorTag = ref(false);

const makeNewDestDataset = ref(true);
const useExistingDest = ref(false);

const testingSSH = ref(false);
const sshTestResult = ref(false);

const testingNetcat = ref(false);
const netCatTestResult = ref(false);

const transferMethod = ref('ssh')
const netCatPortError = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

watch(useExistingDest, async (on) => {
    makeNewDestDataset.value = !on;        // new dataset => Create
    if (on) {
        // ensure dataset list is fresh
        if (destPool.value) {
            if (destHost.value) await getRemoteDestinationDatasets();
            else await getLocalDestinationDatasets();
        }
        // run preflight checks (common snap / divergence)
        void checkDestDatasetContents();
    } else {
        allowOverwrite.value = false;
        destDatasetErrorTag.value = false;
    }
});

watch([useExistingDest, destDatasets], () => {
    if (useExistingDest.value && destDataset.value && !doesItExist(destDataset.value, destDatasets.value)) {
        destDataset.value = '';
    }
});


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
        const snapshotRetentionParams = params.find(p => p.key === 'snapshotRetention')!.children;
        transferMethod.value = sendOptionsParams.find(p => p.key === 'transferMethod')!.value;
        if(transferMethod.value == 'local' || transferMethod.value == ''){
            transferMethod.value = 'ssh'
        }
        const allowOverwriteParam = sendOptionsParams.find(p => p.key === 'allowOverwrite');
        allowOverwrite.value = allowOverwriteParam ? !!allowOverwriteParam.value : false;

        // Check for source retention
        const sourceRetention = snapshotRetentionParams.find(c => c.key === 'source');
        if (sourceRetention) {
            srcRetentionTime.value = sourceRetention.children.find(c => c.key === 'retentionTime')?.value || 0;
            srcRetentionUnit.value = sourceRetention.children.find(c => c.key === 'retentionUnit')?.value || '';
        }

        // Check for destination retention
        const destinationRetention = snapshotRetentionParams.find(c => c.key === 'destination');
        if (destinationRetention) {
            destRetentionTime.value = destinationRetention.children.find(c => c.key === 'retentionTime')?.value || 0;
            destRetentionUnit.value = destinationRetention.children.find(c => c.key === 'retentionUnit')?.value || '';
        }

        initialParameters.value = JSON.parse(JSON.stringify({
            sourcePool: sourcePool.value,
            sourceDataset: sourceDataset.value,
            useCustomSource: useCustomSource.value,
            destHost: destHost.value,
            destPort: destPort.value,
            destUser: destUser.value,
            destPool: destPool.value,
            destDataset: destDataset.value,
            useCustomTarget: useCustomTarget.value,
            sendCompressed: sendCompressed.value,
            sendRaw: sendRaw.value,
            sendRecursive: sendRecursive.value,
            mbufferSize: mbufferSize.value,
            mbufferUnit: mbufferUnit.value,
            useCustomName: useCustomName.value,
            customName: customName.value,
            srcRetentionTime: srcRetentionTime.value,
            srcRetentionUnit: srcRetentionUnit.value,
            destRetentionTime: destRetentionTime.value,
            destRetentionUnit: destRetentionUnit.value,
            transferMethod: transferMethod.value,
            allowOverwrite: allowOverwrite.value,
        }));

        loading.value = false;
    } else {
        //if no props.task, new task configuration (default values)
        await getSourcePools();
        await getLocalDestinationPools();
    }
}

function hasChanges() {
    const currentParams = {
        sourcePool: sourcePool.value,
        sourceDataset: sourceDataset.value,
        useCustomSource: useCustomSource.value,
        destHost: destHost.value,
        destPort: destPort.value,
        destUser: destUser.value,
        destPool: destPool.value,
        destDataset: destDataset.value,
        useCustomTarget: useCustomTarget.value,
        sendCompressed: sendCompressed.value,
        sendRaw: sendRaw.value,
        sendRecursive: sendRecursive.value,
        mbufferSize: mbufferSize.value,
        mbufferUnit: mbufferUnit.value,
        useCustomName: useCustomName.value,
        customName: customName.value,
        srcRetentionTime: srcRetentionTime.value,
        srcRetentionUnit: srcRetentionUnit.value,
        destRetentionTime: destRetentionTime.value,
        destRetentionUnit: destRetentionUnit.value,
        allowOverwrite: allowOverwrite.value,
    };

    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}

function hasDestDatasetChanged() {
    // For new tasks, treat any non-empty destDataset as "changed"
    if (!('destDataset' in initialParameters.value)) {
        return !!destDataset.value;
    }
    return destDataset.value !== initialParameters.value.destDataset;
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
  //  console.log("Handling destination host change:", newVal);
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
  //  console.log('sourcePools:', sourcePools.value);
}

const getSourceDatasets = async () => {
    loadingSourceDatasets.value = true;
    sourceDatasets.value = await getDatasetData(sourcePool.value);
    loadingSourceDatasets.value = false;
  //  console.log('sourceDatasets:', sourceDatasets.value);
}

const getLocalDestinationPools = async () => {
    loadingDestPools.value = true;
    destPools.value = await getPoolData();
    loadingDestPools.value = false;
  //  console.log('Local destPools:', destPools.value);
}

const getLocalDestinationDatasets = async () => {
    loadingDestDatasets.value = true;
    destDatasets.value = await getDatasetData(destPool.value);
    loadingDestDatasets.value = false;
  //  console.log('Local destDatasets:', destDatasets.value);
}

const getRemoteDestinationPools = async () => {
    loadingDestPools.value = true;
    if(transferMethod.value=='netcat'){
        destPools.value = await getPoolData(destHost.value, "22", destUser.value);
    }else{
        destPools.value = await getPoolData(destHost.value, destPort.value, destUser.value);
    }
    loadingDestPools.value = false;
  //  console.log('Remote destPools:', destPools.value);

}


const getRemoteDestinationDatasets = async () => {
    loadingDestDatasets.value = true;
    if (transferMethod.value=='netcat') {
        destDatasets.value = await getDatasetData(destPool.value, destHost.value, "22", destUser.value);
    } else {
        destDatasets.value = await getDatasetData(destPool.value, destHost.value, destPort.value, destUser.value);
    }
    loadingDestDatasets.value = false;
  //  console.log('Remote destDataset:', destDatasets.value);
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

function validatePort() {
    if (destPort.value == 22 && transferMethod.value == 'netcat' && destHost.value != '') {
        errorList.value.push("Port 22 is not allowed for Netcat. Please choose a different port.");
        netCatPortError.value = true;
    } else {
        netCatPortError.value = false;
    }
}


watch(destHost, (newValue) => {
    if (newValue === '') {
        validatePort(); // Call validatePort() when destHost is empty
    } 
});

watch(destPort, validatePort);

watch(transferMethod, (newValue) => {
    if (newValue === 'netcat' && destPort.value === 22) {
        destPort.value = 31337;
    }
});



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
    // if (!hasDestDatasetChanged()) return;

    // Common checks
    if (destPool.value === '') {
        errorList.value.push("Destination pool is needed.");
        destPoolErrorTag.value = true;
    } else if (!doesItExist(destPool.value, destPools.value)) {
        errorList.value.push("Destination pool does not exist.");
        customDestPoolErrorTag.value = true;
    }

    // EXISTING DATASET: must pick one that exists in the list
    if (useExistingDest.value) {
        if (destDataset.value === '') {
            errorList.value.push("Destination dataset is needed.");
            destDatasetErrorTag.value = true;
            return;
        }
        if (!doesItExist(destDataset.value, destDatasets.value)) {
            errorList.value.push("Selected destination dataset does not exist in this pool.");
            destDatasetErrorTag.value = true;
            return;
        }
        // Snapshot/common-base checks happen in checkDestDatasetContents()
        return;
    }

    // NEW DATASET: validate name + make sure it doesn't already exist
    if (!isValidDatasetName(destDataset.value)) {
        errorList.value.push("Destination dataset name is invalid.");
        customDestDatasetErrorTag.value = true;
        return;
    }
    if (doesItExist(destDataset.value, destDatasets.value)) {
        errorList.value.push("That dataset already exists. Choose 'Existing Dataset' or use a new path.");
        customDestDatasetErrorTag.value = true;
        return;
    }
}

async function checkDestDatasetContents() {
    // Only matters when using existing
    if (!useExistingDest.value) return;
    // if (!hasDestDatasetChanged()) return;

    try {
        const srcSnaps = await listSnapshots(sourceDataset.value);
        let dstSnaps: ZfsSnap[] = [];

        if (destHost.value) {
            const portToUse = transferMethod.value === "netcat" ? "22" : String(destPort.value);
            dstSnaps = await listSnapshots(destDataset.value, destUser.value, destHost.value, portToUse);
        } else {
            dstSnaps = await listSnapshots(destDataset.value);
        }

        // Empty destination is always fine
        if (!dstSnaps.length) {
            destDatasetErrorTag.value = false;
            return;
        }

        const common = mostRecentCommonSnapshot(srcSnaps, dstSnaps);

        if (!common) {
            // No common base
            if (allowOverwrite.value) {
                destDatasetErrorTag.value = false; // proceed with -F
                return;
            }
            errorList.value.push("No common snapshot found. Enable 'Allow overwrite' or choose an empty/new destination.");
            destDatasetErrorTag.value = true;
            return;
        }

        // Has common, but is dest ahead?
        const diverged = destAheadOfCommon(srcSnaps, dstSnaps, common);
        if (diverged && !allowOverwrite.value) {
            errorList.value.push("Destination has newer snapshots than the common base. Enable 'Allow overwrite' to roll back, or pick a new destination.");
            destDatasetErrorTag.value = true;
            return;
        }

        // Good to go
        destDatasetErrorTag.value = false;

    } catch (err) {
        console.error("checkDestDatasetContents:", err);
        errorList.value.push("Failed to verify destination snapshots.");
        destDatasetErrorTag.value = true;
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
    netCatPortError.value = false;
    errorList.value = [];
}

async function validateParams() {
    // clearErrorTags();
    validateSource();
    validateHost();
    validateDestination();
    validatePort();
    if (useExistingDest.value) await checkDestDatasetContents();
    validateCustomName();

    if (errorList.value.length == 0) {
        setParams();
    }
}

function setParams() {
    if (transferMethod.value == 'ssh' && destHost.value == ''){
        transferMethod.value = "local"
    }
    else if(transferMethod.value == "netcat") {
        transferMethod.value = "netcat"

    }
    const newParams = new ParameterNode("ZFS Replication Task Config", "zfsRepConfig")
        .addChild(new ZfsDatasetParameter('Source Dataset', 'sourceDataset', '', 0, '', sourcePool.value, sourceDataset.value))
        .addChild(new ZfsDatasetParameter('Destination Dataset', 'destDataset', destHost.value, destPort.value, destUser.value, destPool.value, destDataset.value))
        .addChild(new ParameterNode('Send Options', 'sendOptions')
            .addChild(new BoolParameter('Compressed', 'compressed_flag', sendCompressed.value))
            .addChild(new BoolParameter('Raw', 'raw_flag', sendRaw.value))
            .addChild(new BoolParameter('Recursive', 'recursive_flag', sendRecursive.value))
            .addChild(new IntParameter('MBuffer Size', 'mbufferSize', mbufferSize.value))
            .addChild(new StringParameter('MBuffer Unit', 'mbufferUnit', mbufferUnit.value))
            .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', useCustomName.value))
            .addChild(new StringParameter('Custom Name', 'customName', customName.value))
            .addChild(new StringParameter('Transfer Method', 'transferMethod', transferMethod.value))
            .addChild(new BoolParameter('Allow Overwrite', 'allowOverwrite', allowOverwrite.value))
            .addChild(new BoolParameter('Use Existing Destination', 'useExistingDest', useExistingDest.value))

        )
        .addChild(new ParameterNode('Snapshot Retention', 'snapshotRetention')
            .addChild(new SnapshotRetentionParameter('Source','source',srcRetentionTime.value,srcRetentionUnit.value))
            .addChild(new SnapshotRetentionParameter('Destination', 'destination', destRetentionTime.value, destRetentionUnit.value))

        );
    parameters.value = newParams;
  //  console.log('newParams:', newParams);
}

async function confirmSSHTest(destHost, destUser) {
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

async function confirmNetcatTest(destHost2, destPort2) {
    testingNetcat.value = true;
    const netcatHost = destHost2;
    const netcatdestPort = destPort2;

    netCatTestResult.value = await testNetcat(destUser.value, netcatHost, netcatdestPort);

    if (netCatTestResult.value) {
        pushNotification(new Notification(
            "Connection Successful!",
            `Netcat connection established. This host can be used for remote transfers.`,
            "success",
            8000
        ));
    } else {
        pushNotification(new Notification(
            "Connection Failed",
            `Netcat test failed. Ensure Netcat is installed and the specified port (${destPort.value}) is open on the receiving host.`,
            "error",
            8000
        ));
    }
    testingNetcat.value = false;
}


watch(destPool, handleDestPoolChange);
watch(sourcePool, handleSourcePoolChange);

onMounted(async () => {
    await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});
</script>
