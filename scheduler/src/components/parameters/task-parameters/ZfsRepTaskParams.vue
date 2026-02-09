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
                <label class="-mt-1 block text-base leading-6 text-default">{{ sourceCardLabel }}</label>
                <div class="mt-1 flex flex-col items-center text-center">
                    <label class="block text-xs text-default">Custom</label>
                    <input type="checkbox" v-model="useCustomSource" class="h-4 w-4 rounded" />
                </div>
            </div>

            <div name="source-pool">
                <div class="flex flex-row justify-between items-center">
                    <div class="flex items-center gap-2">
                        <label class="mt-1 block text-sm leading-6 text-default">Pool</label>

                        <button v-if="showSourcePoolRefresh" type="button"
                            class="mt-1 inline-flex items-center justify-center rounded p-1 text-muted hover:text-default disabled:opacity-50"
                            :disabled="remoteHostMissing || loadingSourcePools" @click="refreshSourcePoolData"
                            title="Refresh remote pools" aria-label="Refresh remote pools">
                            <ArrowPathIcon class="h-4 w-4" :class="loadingSourcePools ? 'animate-spin' : ''" />
                        </button>
                    </div>

                    <ExclamationCircleIcon v-if="sourcePoolErrorTag || customDestPoolErrorTag"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>

                <div v-if="useCustomSource">
                    <input type="text" v-model="sourcePool" :disabled="sourcePoolDisabled" :class="[
                        'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                        customSrcPoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" :placeholder="sourcePoolPlaceholder" />
                </div>

                <div v-else>
                    <select v-model="sourcePool" :disabled="sourcePoolDisabled" :class="[
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                        sourcePoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]">
                        <option value="">{{ sourcePoolPlaceholder }}</option>
                        <option v-if="!loadingSourcePools" v-for="pool in sourcePools" :key="pool" :value="pool">
                            {{ pool }}
                        </option>
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
                    <input type="text" v-model="sourceDataset" :disabled="!sourcePool || sourcePoolDisabled" :class="[
                        'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                        customSrcDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" :placeholder="sourcePool ? 'Specify Dataset' : 'Select a Pool first'" />
                </div>

                <div v-else>
                    <select v-model="sourceDataset" :disabled="!sourcePool || sourcePoolDisabled" :class="[
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                        sourceDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]">
                        <option value="">{{ sourcePool ? 'Select a Dataset' : 'Select a Pool first' }}</option>
                        <option v-if="!loadingSourceDatasets" v-for="dataset in sourceDatasets" :key="dataset"
                            :value="dataset">
                            {{ dataset }}
                        </option>
                        <option v-if="loadingSourceDatasets">Loading...</option>
                    </select>
                </div>
            </div>

            <div name="source-snapshot-retention">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default whitespace-nowrap">
                        {{ retentionSourceLabel }}
                        <InfoTile class="ml-1"
                            :title="`How long to keep source snapshots for. Leave at 0 to keep ALL snapshots.\nWARNING: Disabling an automated task's schedule for a period of time longer than the retention interval and re-enabling the schedule may result in a purge of snapshots.`" />
                    </label>
                </div>
                <div class="flex flex-row gap-2 w-full items-center justify-between">
                    <input type="number" min="0" v-model="srcRetentionTime"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" />
                    <select v-model="srcRetentionUnit"
                        class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option value="">Select an Interval</option>
                        <option v-for="option in retentionUnitOptions" :key="option" :value="option">
                            {{ option }}
                        </option>
                    </select>
                </div>
            </div>

            <div name="direction" class="col-span-1">
                <div class="w-full mt-2 flex flex-row justify-between items-center text-center space-x-2 text-default">
                    <label v-if="directionSwitched" class="block text-sm leading-6 text-default">
                        Direction - Pull (From Remote)
                    </label>
                    <label v-else class="block text-sm leading-6 text-default">
                        Direction - Push
                    </label>
                    <Switch v-model="directionSwitched"
                        :class="[directionSwitched ? 'bg-secondary' : 'bg-well', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-slate-600 focus:ring-offset-2']">
                        <span class="sr-only">Use setting</span>
                        <span aria-hidden="true"
                            :class="[directionSwitched ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-default shadow ring-0 transition duration-200 ease-in-out']" />
                    </Switch>
                </div>

                <div class="w-full mt-1.5 justify-center items-center">
                    <div @click="directionSwitched = !directionSwitched"
                        class="flex flex-row justify-around text-center items-center space-x-1 bg-plugin-header rounded-lg p-2">
                        <span class="text-default">{{ sourceCardLabel }}</span>
                        <div class="relative flex items-center justify-around">
                            <span
                                :class="[directionSwitched ? 'rotate-180' : '', 'flex items-center transition-transform duration-200']">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted" />
                            </span>
                            <span
                                :class="[directionSwitched ? 'rotate-180' : '', 'flex items-center transition-transform duration-200']">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted" />
                            </span>
                            <span
                                :class="[directionSwitched ? 'rotate-180' : '', 'flex items-center transition-transform duration-200']">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted" />
                            </span>
                        </div>
                        <span class="text-default">{{ targetCardLabel }}</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- BOTTOM LEFT -->
        <div name="destination-data"
            class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent">
            <div class="flex flex-row justify-between items-center">
                <label class="-mt-1 block text-base leading-6 text-default">{{ targetCardLabel }}</label>
                <div class="mt-1 flex items-center gap-4">
                    <label class="block text-xs text-default">Existing Dataset</label>
                    <input type="checkbox" v-model="useExistingDest" class="h-4 w-4 rounded" />
                </div>
            </div>

            <div name="destination-pool">
                <div class="flex flex-row justify-between items-center">
                    <div class="flex items-center gap-2">
                        <label class="mt-1 block text-sm leading-6 text-default">Pool</label>

                        <button v-if="showDestPoolRefresh" type="button"
                            class="mt-1 inline-flex items-center justify-center rounded p-1 text-muted hover:text-default disabled:opacity-50"
                            :disabled="remoteHostMissing || loadingDestPools" @click="refreshDestPoolData"
                            title="Refresh remote pools" aria-label="Refresh remote pools">
                            <ArrowPathIcon class="h-4 w-4" :class="loadingDestPools ? 'animate-spin' : ''" />
                        </button>
                    </div>

                    <ExclamationCircleIcon v-if="destPoolErrorTag || customDestPoolErrorTag"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>

                <select v-model="destPool" :disabled="destPoolDisabled" :class="[
                    'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                    destPoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]">
                    <option value="">{{ destPoolPlaceholder }}</option>
                    <option v-if="!loadingDestPools" v-for="pool in destPools" :key="pool" :value="pool">
                        {{ pool }}
                    </option>
                    <option v-if="loadingDestPools">Loading...</option>
                </select>
            </div>

            <div name="destination-dataset">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Dataset</label>
                    <ExclamationCircleIcon v-if="destDatasetErrorTag || customDestDatasetErrorTag"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>

                <div v-if="useExistingDest">
                    <select v-model="destDataset" :class="[
                        'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                        destDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" :disabled="!destPool || destPoolDisabled">
                        <option value="">{{ destPool ? 'Select a Dataset' : 'Select a Pool first' }}</option>
                        <option v-if="!loadingDestDatasets" v-for="dataset in destDatasets" :key="dataset"
                            :value="dataset">
                            {{ dataset }}
                        </option>
                        <option v-if="loadingDestDatasets">Loading...</option>
                    </select>
                </div>

                <div v-else>
                    <div class="flex flex-row justify-between items-center w-full flex-grow">
                        <input type="text" v-model="destDataset" :class="[
                            'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                            customDestDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]" placeholder="Specify new dataset path to create on first run" />

                        <div v-if="showCreateTargetDataset"
                            class="m-1 flex flex-col items-center text-center flex-shrink">
                            <label class="block text-xs text-default">Create</label>
                            <input type="checkbox" v-model="makeNewDestDataset" class="h-4 w-4 rounded" />
                        </div>
                    </div>
                </div>
            </div>

            <div name="destination-snapshot-retention">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default whitespace-nowrap">
                        {{ retentionDestLabel }}
                        <InfoTile class="ml-1"
                            :title="`How long to keep destination snapshots for. Leave at 0 to keep ALL snapshots.\nWARNING: Disabling an automated task's schedule for a period of time longer than the retention interval and re-enabling the schedule may result in a purge of snapshots.`" />
                    </label>
                </div>
                <div class="flex flex-row gap-2 w-full items-center justify-between">
                    <input type="number" min="0" v-model="destRetentionTime"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" />
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
                <div class="flex items-center justify-between mt-2">
                    <label class="text-sm leading-6 text-default flex items-center">
                        On resume failure, clear token and continue
                        <InfoTile class="ml-1"
                            :title="`If a resume token exists but the destination changed, this will discard the token and proceed with normal replication. This can trigger a rollback on the destination when overwrite is enabled, which may discard newer snapshots or changes.`" />
                    </label>
                    <input type="checkbox" v-model="resumeFailAllowOverwrite" class="h-4 w-4 rounded" />
                </div>
                <p class="mt-1 text-xs text-default/70">
                    If a resume token exists but the destination was modified, clear the token and
                    continue with normal replication. If overwrite is allowed, the task may roll back with
                    <code>zfs receive -F</code>.
                </p>
            </div>
        </div>

        <!-- TOP RIGHT -->
        <div name="destination-ssh-data" class="border border-default rounded-md p-2 col-span-1 bg-accent">
            <div class="grid grid-cols-2">
                <label class="mt-1 col-span-1 block text-base leading-6 text-default">Select Transfer Method</label>
                <select v-model="transferMethod" :disabled="!hasRemoteEndpoint"
                    class="text-default bg-default mt-0 block w-full input-textlike sm:text-sm sm:leading-6"
                    id="method">
                    <option value="ssh">SSH</option>
                    <option value="netcat" :disabled="isPull">Netcat</option>
                </select>
            </div>

            <div class="grid grid-cols-2 mt-2">
                <label class="mt-1 col-span-1 block text-base leading-6 text-default">{{ remoteEndpointLabel }}</label>
                <div class="col-span-1 items-end text-end justify-end">
                    <button disabled v-if="testingNetcat || testingSSH"
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
                ]" :placeholder="hostPlaceholder" />
            </div>

            <div name="destination-user" class="mt-1">
                <label class="block text-sm leading-6 text-default">User</label>
                <input :disabled="remoteFieldsDisabled" type="text" v-model="destUser"
                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                    placeholder="'root' is default" />
            </div>

            <div name="destination-port" class="mt-1">
                <div class="flex flex-row justify-between items-center">
                    <label class="block text-sm leading-6 text-default">Port</label>
                    <ExclamationCircleIcon v-if="netCatPortError" class="mt-1 w-5 h-5 text-danger" />
                </div>

                <input :disabled="remoteFieldsDisabled" type="number" v-model="destPort" :class="[
                    netCatPortError ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '',
                    'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6'
                ]" min="0" max="65535"
                    :placeholder="transferMethod === 'netcat' ? 'Enter port (not 22 for netcat)' : '22 is default'"
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
                    <input :disabled="remoteFieldsDisabled" type="number" v-model="mbufferSize" min="1"
                        class="mt-0.5 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="1" />
                </div>
                <div name="send-opt-mbuffer" class="col-span-1">
                    <div name="send-opt-mbuffer-unit">
                        <label class="block text-sm leading-6 text-default">mBuffer Unit (Remote)</label>
                        <select :disabled="remoteFieldsDisabled" v-model="mbufferUnit"
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
import { ref, Ref, onMounted, watch, inject, computed } from 'vue';
import { ExclamationCircleIcon, ChevronDoubleRightIcon, ArrowPathIcon } from '@heroicons/vue/24/outline';
import { Switch } from '@headlessui/vue';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import {
    ParameterNode,
    ZfsDatasetParameter,
    IntParameter,
    StringParameter,
    BoolParameter,
    SnapshotRetentionParameter,
    SelectionOption,
    SelectionParameter
} from '../../../models/Parameters';
import {
    getPoolData,
    getDatasetData,
    testSSH,
    testNetcat,
    mostRecentCommonSnapshot,
    listSnapshots,
    ZfsSnap,
    destAheadOfCommon
} from '../../../composables/utility';
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

const directionSwitched = ref(false);
const allowOverwrite = ref(false);
const resumeFailAllowOverwrite = ref(false);
const remoteHostMissing = computed(() => destHost.value.trim() === '');

const sourcePoolDisabled = computed(() => sourceIsRemote.value && remoteHostMissing.value);

const destPoolDisabled = computed(() => targetIsRemote.value && remoteHostMissing.value);

const sourcePoolPlaceholder = computed(() =>
    sourceIsRemote.value
        ? (remoteHostMissing.value ? 'Enter a Host first' : 'Select a Pool')
        : 'Select a Pool'
);

const destPoolPlaceholder = computed(() =>
    targetIsRemote.value
        ? (remoteHostMissing.value ? 'Enter a Host first' : 'Select a Pool')
        : 'Select a Pool'
);
const hasRemoteEndpoint = computed(() => isPull.value || destHost.value.trim() !== '');

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
const retentionUnitOptions = ref(['minutes', 'hours', 'days', 'weeks', 'months', 'years']);

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

const transferMethod = ref('ssh');
const netCatPortError = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

/* ---------------- Direction-aware labels + behavior ---------------- */

const isPull = computed(() => directionSwitched.value);

const remoteEndpointLabel = computed(() => (isPull.value ? 'Remote Source' : 'Remote Target'));
const sourceCardLabel = computed(() => (isPull.value ? 'Remote Source Location' : 'Source Location'));
const targetCardLabel = computed(() => (isPull.value ? 'Local Target Location' : 'Target Location'));

const retentionSourceLabel = computed(() =>
    isPull.value ? 'Remote Source Retention Policy' : 'Source Retention Policy'
);
const retentionDestLabel = computed(() =>
    isPull.value ? 'Local Target Retention Policy' : 'Destination Retention Policy'
);

const hostPlaceholder = computed(() =>
    isPull.value ? 'Required for pull replication.' : 'Leave blank for local replication.'
);

// Remote endpoint is always destHost/user/port.
// In pull: source side is remote.
// In push: target side is remote iff destHost provided.
const sourceIsRemote = computed(() => isPull.value);
const targetIsRemote = computed(() => !isPull.value && destHost.value !== '');
const targetIsLocal = computed(() => isPull.value || destHost.value === '');

const showCreateTargetDataset = computed(() => !useExistingDest.value && targetIsLocal.value);

// Disable remote fields only when they are irrelevant (push + local)
const remoteFieldsDisabled = computed(() => !isPull.value && destHost.value === '');

const showSourcePoolRefresh = computed(() => sourceIsRemote.value && !useCustomSource.value);
const showDestPoolRefresh = computed(() => targetIsRemote.value); // dest pool is always a select in your UI

async function refreshSourcePoolData() {
    if (remoteHostMissing.value) return;

    await getSourcePools();

    // If a pool is selected, refresh datasets too (optional but usually desired)
    if (sourcePool.value) {
        await getSourceDatasets();
    }
}

async function refreshDestPoolData() {
    if (remoteHostMissing.value) return;

    await getTargetPools();

    // If a pool is selected, refresh datasets too (optional)
    if (destPool.value) {
        await getTargetDatasets();
    }
}

/* ---------------- Existing watchers (adjusted) ---------------- */

watch(useExistingDest, async (on) => {
    makeNewDestDataset.value = !on;
    if (on) {
        if (destPool.value) await getTargetDatasets();
        void checkDestDatasetContents();
    } else {
        allowOverwrite.value = false;
        resumeFailAllowOverwrite.value = false;
        destDatasetErrorTag.value = false;
    }
});

watch([useExistingDest, destDatasets], () => {
    if (useExistingDest.value && destDataset.value && !doesItExist(destDataset.value, destDatasets.value)) {
        destDataset.value = '';
    }
});

watch(sourcePool, (v) => {
    if (!v) sourceDataset.value = '';
});

watch(destHost, (v) => {
    if (v.trim() !== '') return;

    if (isPull.value) {
        sourcePool.value = '';
        sourceDataset.value = '';
    } else {
        destPool.value = '';
        destDataset.value = '';
    }
});


// If direction flips, refresh lists from the correct endpoints and clear selections
watch(directionSwitched, async () => {
    clearErrorTags();
    sourcePool.value = '';
    sourceDataset.value = '';
    destPool.value = '';
    destDataset.value = '';
    await getSourcePools();
    await getTargetPools();
});

watch(isPull, (on) => {
    if (on) {
        if (transferMethod.value === 'netcat') {
            transferMethod.value = 'ssh';
        }
        pushNotification(
            new Notification(
                'Netcat Disabled',
                'Netcat is not available in Pull mode. Pull replication uses SSH only.',
                'info',
                6000
            )
        );
    }
});

watch(transferMethod, (newValue) => {
    if (isPull.value && newValue === 'netcat') {
        transferMethod.value = 'ssh';
        pushNotification(
            new Notification(
                'Netcat Disabled',
                'Netcat is not available in Pull mode. Pull replication uses SSH only.',
                'info',
                6000
            )
        );
        return;
    }

    if (newValue === 'netcat' && destPort.value === 22) {
        destPort.value = 31337;
    }
});


/* ---------------- Initialization ---------------- */

async function initializeData() {
    if (props.task) {
        loading.value = true;

        const params = props.task.parameters.children;

        const transferDirection = params.find(p => p.key === 'direction')?.value;
        directionSwitched.value = transferDirection === 'pull';

        const destDatasetParams = params.find(p => p.key === 'destDataset')!.children;
        destHost.value = destDatasetParams.find(p => p.key === 'host')!.value;
        destPort.value = destDatasetParams.find(p => p.key === 'port')!.value;
        destUser.value = destDatasetParams.find(p => p.key === 'user')!.value;

        const sendOptionsParams = params.find(p => p.key === 'sendOptions')!.children;
        transferMethod.value = sendOptionsParams.find(p => p.key === 'transferMethod')!.value || 'ssh';
        if (transferMethod.value === 'local') transferMethod.value = 'ssh';

        const allowOverwriteParam = sendOptionsParams.find(p => p.key === 'allowOverwrite');
        allowOverwrite.value = allowOverwriteParam ? !!allowOverwriteParam.value : false;
        const resumeFailAllowOverwriteParam = sendOptionsParams.find(p => p.key === 'resumeFailAllowOverwrite');
        resumeFailAllowOverwrite.value = resumeFailAllowOverwriteParam ? !!resumeFailAllowOverwriteParam.value : false;

        const useExistingDestParam = sendOptionsParams.find(p => p.key === 'useExistingDest');
        useExistingDest.value = useExistingDestParam ? !!useExistingDestParam.value : false;

        sendCompressed.value = sendOptionsParams.find(p => p.key === 'compressed_flag')!.value;
        sendRaw.value = sendOptionsParams.find(p => p.key === 'raw_flag')!.value;
        sendRecursive.value = sendOptionsParams.find(p => p.key === 'recursive_flag')!.value;
        mbufferSize.value = sendOptionsParams.find(p => p.key === 'mbufferSize')!.value;
        mbufferUnit.value = sendOptionsParams.find(p => p.key === 'mbufferUnit')!.value;
        useCustomName.value = sendOptionsParams.find(p => p.key === 'customName_flag')!.value;
        customName.value = sendOptionsParams.find(p => p.key === 'customName')!.value;

        const snapshotRetentionParams = params.find(p => p.key === 'snapshotRetention')!.children;
        const sourceRetention = snapshotRetentionParams.find(c => c.key === 'source');
        if (sourceRetention) {
            srcRetentionTime.value = sourceRetention.children.find(c => c.key === 'retentionTime')?.value || 0;
            srcRetentionUnit.value = sourceRetention.children.find(c => c.key === 'retentionUnit')?.value || '';
        }
        const destinationRetention = snapshotRetentionParams.find(c => c.key === 'destination');
        if (destinationRetention) {
            destRetentionTime.value = destinationRetention.children.find(c => c.key === 'retentionTime')?.value || 0;
            destRetentionUnit.value = destinationRetention.children.find(c => c.key === 'retentionUnit')?.value || '';
        }

        // Optional connectivity check if remote endpoint exists
        if (destHost.value) {
            const sshTarget = `${destUser.value}@${destHost.value}`;
            const ok = await testSSH(sshTarget);
            if (ok) {
                pushNotification(new Notification(
                    'SSH Connection Available',
                    'Passwordless SSH connection established. This host can be used for replication (Assuming ZFS exists on target).',
                    'success',
                    6000
                ));
            } else {
                pushNotification(new Notification(
                    'SSH Connection Failed',
                    'Passwordless SSH connection refused with this user/host/port. Please confirm SSH configuration or choose a new target.',
                    'error',
                    6000
                ));
            }
        }

        // Load lists from correct endpoints for current direction
        await getSourcePools();
        await getTargetPools();

        const sourceDatasetParams = params.find(p => p.key === 'sourceDataset')!.children;
        sourcePool.value = sourceDatasetParams.find(p => p.key === 'pool')!.value;
        await getSourceDatasets();
        sourceDataset.value = sourceDatasetParams.find(p => p.key === 'dataset')!.value;

        destPool.value = destDatasetParams.find(p => p.key === 'pool')!.value;
        await getTargetDatasets();
        destDataset.value = destDatasetParams.find(p => p.key === 'dataset')!.value;

        if (!doesItExist(sourcePool.value, sourcePools.value) || !doesItExist(sourceDataset.value, sourceDatasets.value)) {
            useCustomSource.value = true;
        }
        if (!doesItExist(destPool.value, destPools.value) || !doesItExist(destDataset.value, destDatasets.value)) {
            useCustomTarget.value = true;
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
            directionSwitched: directionSwitched.value,
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
            resumeFailAllowOverwrite: resumeFailAllowOverwrite.value,
            useExistingDest: useExistingDest.value,
        }));

        loading.value = false;
    } else {
        await getSourcePools();
        await getTargetPools();
    }
}

/* ---------------- Change detection ---------------- */

function hasChanges() {
    const currentParams = {
        sourcePool: sourcePool.value,
        sourceDataset: sourceDataset.value,
        useCustomSource: useCustomSource.value,
        directionSwitched: directionSwitched.value,
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
        resumeFailAllowOverwrite: resumeFailAllowOverwrite.value,
        useExistingDest: useExistingDest.value,
    };
    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}

/* ---------------- UI logic ---------------- */

function handleCheckboxChange(checkbox: string) {
    if (checkbox === 'sendCompressed' && sendCompressed.value) {
        sendRaw.value = false;
    } else if (checkbox === 'sendRaw' && sendRaw.value) {
        sendCompressed.value = false;
    }
}

function debounce(func: any, delay: number) {
    let timerId: any;
    return function (...args: any[]) {
        if (timerId) clearTimeout(timerId);
        timerId = setTimeout(() => func(...args), delay);
    };
}

const handleDestHostChange = async () => {
    await getSourcePools();
    await getTargetPools();
    sourcePool.value = '';
    sourceDataset.value = '';
    destPool.value = '';
    destDataset.value = '';
};

const debouncedDestHostChange = debounce(handleDestHostChange, 500);

/* ---------------- Direction-aware list loading ---------------- */

const getSourcePools = async () => {
    loadingSourcePools.value = true;
    try {
        if (sourceIsRemote.value) {
            if (!destHost.value) {
                sourcePools.value = [];
                return;
            }
            const portToUse = transferMethod.value === 'netcat' ? '22' : String(destPort.value);
            sourcePools.value = await getPoolData(destHost.value, portToUse, destUser.value);
        } else {
            sourcePools.value = await getPoolData();
        }
    } finally {
        loadingSourcePools.value = false;
    }
};

const getSourceDatasets = async () => {
    loadingSourceDatasets.value = true;
    try {
        if (sourceIsRemote.value) {
            if (!destHost.value) {
                sourceDatasets.value = [];
                return;
            }
            const portToUse = transferMethod.value === 'netcat' ? '22' : String(destPort.value);
            sourceDatasets.value = await getDatasetData(sourcePool.value, destHost.value, portToUse, destUser.value);
        } else {
            sourceDatasets.value = await getDatasetData(sourcePool.value);
        }
    } finally {
        loadingSourceDatasets.value = false;
    }
};

const getTargetPools = async () => {
    loadingDestPools.value = true;
    try {
        if (targetIsRemote.value) {
            const portToUse = transferMethod.value === 'netcat' ? '22' : String(destPort.value);
            destPools.value = await getPoolData(destHost.value, portToUse, destUser.value);
        } else {
            destPools.value = await getPoolData();
        }
    } finally {
        loadingDestPools.value = false;
    }
};

const getTargetDatasets = async () => {
    loadingDestDatasets.value = true;
    try {
        if (targetIsRemote.value) {
            const portToUse = transferMethod.value === 'netcat' ? '22' : String(destPort.value);
            destDatasets.value = await getDatasetData(destPool.value, destHost.value, portToUse, destUser.value);
        } else {
            destDatasets.value = await getDatasetData(destPool.value);
        }
    } finally {
        loadingDestDatasets.value = false;
    }
};

const handleSourcePoolChange = async (newVal: string) => {
    if (newVal) await getSourceDatasets();
};

const handleDestPoolChange = async (newVal: string) => {
    if (newVal) await getTargetDatasets();
};

watch(sourcePool, handleSourcePoolChange);
watch(destPool, handleDestPoolChange);

// If transfer method changes, remote queries may need different control-plane port assumptions
watch(transferMethod, async (newValue) => {
    if (newValue === 'netcat' && destPort.value === 22) {
        destPort.value = 31337;
    }
    await getSourcePools();
    await getTargetPools();
});

/* ---------------- Validation ---------------- */

function validateHost() {
    if (isPull.value && destHost.value === "") {
        errorList.value.push("Host is required for pull replication.");
        destHostErrorTag.value = true;
        return;
    }

    if (destHost.value !== "") {
        if (destHost.value.length < 1 || destHost.value.length > 253) {
            errorList.value.push("Hostname must be between 1 and 253 characters in length.");
            destHostErrorTag.value = true;
        }
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

watch(destPort, validatePort);

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
        } else if (!doesItExist(sourcePool.value, sourcePools.value)) {
            errorList.value.push("Source pool does not exist.");
            customSrcPoolErrorTag.value = true;
        }

        if (sourceDataset.value === '') {
            errorList.value.push("Source dataset is needed.");
            sourceDatasetErrorTag.value = true;
        } else if (!doesItExist(sourceDataset.value, sourceDatasets.value)) {
            errorList.value.push("Source dataset does not exist.");
            customSrcDatasetErrorTag.value = true;
        }
    }
}

function validateDestination() {
    if (destPool.value === '') {
        errorList.value.push("Destination pool is needed.");
        destPoolErrorTag.value = true;
    } else if (!doesItExist(destPool.value, destPools.value)) {
        errorList.value.push("Destination pool does not exist.");
        customDestPoolErrorTag.value = true;
    }

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
        return;
    }

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

/* ---------------- Direction-aware preflight check ---------------- */

async function checkDestDatasetContents() {
    if (!useExistingDest.value) return;

    try {
        const srcFs = `${sourcePool.value}/${sourceDataset.value}`;
        const dstFs = `${destPool.value}/${destDataset.value}`;

        const portToUse = transferMethod.value === "netcat" ? "22" : String(destPort.value);

        let srcSnaps: ZfsSnap[] = [];
        let dstSnaps: ZfsSnap[] = [];

        if (isPull.value) {
            if (!destHost.value) {
                errorList.value.push("Host is required for pull replication.");
                destHostErrorTag.value = true;
                destDatasetErrorTag.value = true;
                return;
            }
            srcSnaps = await listSnapshots(srcFs, destUser.value, destHost.value, portToUse);
            dstSnaps = await listSnapshots(dstFs);
        } else {
            srcSnaps = await listSnapshots(srcFs);
            dstSnaps = destHost.value
                ? await listSnapshots(dstFs, destUser.value, destHost.value, portToUse)
                : await listSnapshots(dstFs);
        }

        if (!dstSnaps.length) {
            destDatasetErrorTag.value = false;
            return;
        }

        const common = mostRecentCommonSnapshot(srcSnaps, dstSnaps);

        if (!common) {
            if (allowOverwrite.value) {
                destDatasetErrorTag.value = false;
                return;
            }
            errorList.value.push("No common snapshot found. Enable 'Allow overwrite' or choose an empty/new destination.");
            destDatasetErrorTag.value = true;
            return;
        }

        const diverged = destAheadOfCommon(srcSnaps, dstSnaps, common);
        if (diverged && !allowOverwrite.value) {
            errorList.value.push("Destination has newer snapshots than the common base. Enable 'Allow overwrite' to roll back, or pick a new destination.");
            destDatasetErrorTag.value = true;
            return;
        }

        destDatasetErrorTag.value = false;
    } catch (err) {
        console.error("checkDestDatasetContents:", err);
        errorList.value.push("Failed to verify destination snapshots.");
        destDatasetErrorTag.value = true;
    }
}

/* ---------------- Helpers ---------------- */

function isValidPoolName(poolName: string) {
    if (poolName === '') return false;
    if (/^(c[0-9]|log|mirror|raidz[123]?|spare)/.test(poolName)) return false;
    if (/^[0-9._: -]/.test(poolName)) return false;
    if (!/^[a-zA-Z0-9_.:-]*$/.test(poolName)) return false;
    if (poolName.match(/[ ]$/)) return false;
    return true;
}

function doesItExist(thisName: string, list: string[]) {
    return list.includes(thisName);
}

function isValidDatasetName(datasetName: string) {
    if (datasetName === '') return false;
    if (!/^[a-zA-Z0-9]/.test(datasetName)) return false;
    if (/[ \/]$/.test(datasetName)) return false;
    if (!/^[a-zA-Z0-9_.:\/-]*$/.test(datasetName)) return false;
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
    const directionPUSH = new SelectionOption('push', 'Push');
    const directionPULL = new SelectionOption('pull', 'Pull');
    const transferDirection = directionSwitched.value ? directionPULL : directionPUSH;

    let tm = transferMethod.value;
    if (tm === 'ssh' && !isPull.value && destHost.value === '') tm = 'local';
    if (tm !== 'netcat' && tm !== 'ssh' && tm !== 'local') tm = 'ssh';

    const newParams = new ParameterNode("ZFS Replication Task Config", "zfsRepConfig")
        .addChild(new ZfsDatasetParameter('Source Dataset', 'sourceDataset', '', 0, '', sourcePool.value, sourceDataset.value))
        .addChild(new ZfsDatasetParameter('Destination Dataset', 'destDataset', destHost.value, destPort.value, destUser.value, destPool.value, destDataset.value))
        .addChild(new SelectionParameter('Direction', 'direction', transferDirection.value))
        .addChild(new ParameterNode('Send Options', 'sendOptions')
            .addChild(new BoolParameter('Compressed', 'compressed_flag', sendCompressed.value))
            .addChild(new BoolParameter('Raw', 'raw_flag', sendRaw.value))
            .addChild(new BoolParameter('Recursive', 'recursive_flag', sendRecursive.value))
            .addChild(new IntParameter('MBuffer Size', 'mbufferSize', mbufferSize.value))
            .addChild(new StringParameter('MBuffer Unit', 'mbufferUnit', mbufferUnit.value))
            .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', useCustomName.value))
            .addChild(new StringParameter('Custom Name', 'customName', customName.value))
            .addChild(new StringParameter('Transfer Method', 'transferMethod', tm))
            .addChild(new BoolParameter('Allow Overwrite', 'allowOverwrite', allowOverwrite.value))
            .addChild(new BoolParameter('Resume Fail Allow Overwrite', 'resumeFailAllowOverwrite', resumeFailAllowOverwrite.value))
            .addChild(new BoolParameter('Use Existing Destination', 'useExistingDest', useExistingDest.value))
        )
        .addChild(new ParameterNode('Snapshot Retention', 'snapshotRetention')
            .addChild(new SnapshotRetentionParameter('Source', 'source', srcRetentionTime.value, srcRetentionUnit.value))
            .addChild(new SnapshotRetentionParameter('Destination', 'destination', destRetentionTime.value, destRetentionUnit.value))
        );

    parameters.value = newParams;
}

/* ---------------- Test buttons ---------------- */

async function confirmSSHTest(destHostVal: string, destUserVal: string) {
    testingSSH.value = true;
    const sshTarget = destUserVal + '@' + destHostVal;
    sshTestResult.value = await testSSH(sshTarget);

    if (sshTestResult.value) {
        pushNotification(new Notification('Connection Successful!', 'Passwordless SSH connection established. This host can be used for replication (Assuming ZFS exists on target).', 'success', 6000));
    } else {
        pushNotification(new Notification('Connection Failed', `Could not resolve hostname "${destHostVal}": \nName or service not known.\nMake sure passwordless SSH connection has been configured for target system.`, 'error', 6000));
    }
    testingSSH.value = false;
}

async function confirmNetcatTest(destHost2: string, destPort2: number) {
    testingNetcat.value = true;
    netCatTestResult.value = await testNetcat(destUser.value, destHost2, destPort2);

    if (netCatTestResult.value) {
        pushNotification(new Notification("Connection Successful!", "Netcat connection established. This host can be used for remote transfers.", "success", 6000));
    } else {
        pushNotification(new Notification("Connection Failed", `Netcat test failed. Ensure Netcat is installed and the specified port (${destPort.value}) is open on the receiving host.`, "error", 6000));
    }
    testingNetcat.value = false;
}

onMounted(async () => {
    await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});
</script>
