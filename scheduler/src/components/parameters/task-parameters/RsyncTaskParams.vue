<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'"/>
        </div>
    </div>
    <div v-else class="grid grid-cols-2 my-2 gap-2 h-full" style="grid-template-rows: auto auto 1fr;">
        <!-- TOP LEFT -->
        <div name="paths-data" class="border border-default rounded-md p-2 col-span-1 row-start-1 row-span-1 bg-accent" style="grid-row: 1 / span 1;">
            <label class="mt-1 mb-2 col-span-1 block text-base leading-6 text-default">Transfer Details</label>
            <div name="source-path">
                <div class="flex flex-row justify-between items-center">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Source
                            <InfoTile class="ml-1" title="Use a trailing slash (/) if you wish to transfer just the source directory's contents. Leave trailing slash out if you wish to transfer the entire directory." />
                        </label>
                        <ExclamationCircleIcon v-if="sourcePathErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <div>
                    <input v-if="sourcePathErrorTag" type="text" v-model="sourcePath" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Source Path"/> 
                    <input v-else type="text" v-model="sourcePath" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Source Path"/> 
                </div>
            </div>
            <div name="destination-path">
                <div class="flex flex-row justify-between items-center">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Target
                            <InfoTile class="ml-1" title="Target directory must always have a trailing slash (If none is provided it will be added automatically.)" />
                        </label>                  
                    <ExclamationCircleIcon v-if="sourcePathErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <div>
                    <input v-if="destPathErrorTag" type="text" v-model="destPath" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Specify Target Path"/> 
                    <input v-else type="text" v-model="destPath" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Specify Target Path"/> 
                </div>
            </div>
            <div name="direction" class="">
                <div class="w-full mt-2 flex flex-row justify-between items-center text-center space-x-2 text-default">
                    <span v-if="directionSwitched" class="">Direction - Pull</span>
                    <span v-else class="">Direction - Push</span>
                    <Switch
                        v-model="directionSwitched"
                        :class="[directionSwitched ? 'bg-secondary' : 'bg-well', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-slate-600 focus:ring-offset-2']"
                    >
                        <span class="sr-only">Use setting</span>
                        <span
                        aria-hidden="true"
                        :class="[directionSwitched ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-default shadow ring-0 transition duration-200 ease-in-out']"
                        />
                    </Switch>
                </div>
                <div class="w-full mt-2 justify-center items-center">
                    <div class="flex flex-row justify-around text-center items-center space-x-1 bg-plugin-header rounded-lg p-2">
                        <span class="text-default">Source</span>
                        <div class="relative flex items-center justify-around">
                            <span :class="[directionSwitched ? 'rotate-180' : '', 'flex items-center transition-transform duration-200']">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted"/>
                            </span>
                            <span :class="[directionSwitched ? 'rotate-180' : '', 'flex items-center transition-transform duration-200']">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted"/>
                            </span>
                            <span :class="[directionSwitched ? 'rotate-180' : '', 'flex items-center transition-transform duration-200']">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted"/>
                            </span>
                        </div>
                        <span class="text-default">Target</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- TOP RIGHT -->
        <div name="destination-ssh-data" class="border border-default rounded-md p-2 col-span-1 bg-accent" style="grid-row: 1 / span 1;">
            <div class="grid grid-cols-2">
                <label class="mt-1 col-span-1 block text-base leading-6 text-default">Remote Target</label>
                <div class="col-span-1 items-end text-end justify-end">
                    <button disabled v-if="testingSSH" class="mt-0.5 btn btn-secondary object-right justify-end h-fit">
                        <svg aria-hidden="true" role="status" class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                            <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="text-success"/>
                        </svg>
                        Testing...
                    </button>
                    <button v-else @click="confirmTest(destHost, destUser)" class="mt-0.5 btn btn-secondary object-right justify-end h-fit">Test SSH</button>
                </div> 
            </div>
            <div name="destination-host" class="mt-1">
                <div class="flex flex-row justify-between items-center">
                    <label class="block text-sm leading-6 text-default">Host</label>
                    <ExclamationCircleIcon v-if="destHostErrorTag" class="mt-1 w-5 h-5 text-danger"/>
                </div>
                <input v-if="destHostErrorTag" type="text" v-model="destHost" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default outline outline-1 outline-rose-500 dark:outline-rose-700" placeholder="Leave blank for local transfer."/> 
                <input v-else type="text" v-model="destHost" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Leave blank for local transfer."/> 
            </div>
            <div name="destination-user" class="mt-1">
                <label class="block text-sm leading-6 text-default">User</label>
                <input v-if="destHost === ''" disabled type="text" v-model="destUser" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="'root' is default"/> 
                <input v-else type="text" v-model="destUser" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="'root' is default"/> 
            </div>
            <div name="destination-port" class="mt-1">
                <label class="block text-sm leading-6 text-default">Port</label>
                <input v-if="destHost === ''" disabled type="number" v-model="destPort" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" min="0" max="65535" placeholder="22 is default"/>
                <input v-else type="number" v-model="destPort" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" min="0" max="65535" placeholder="22 is default"/> 
            </div>
        </div>
        
        <!-- BOTTOM -->
        <div name="send-options" class="border border-default rounded-md p-2 col-span-2 row-span-1 row-start-2 bg-accent" style="grid-row: 2 / span 1;">
            <label class="mt-1 block text-base leading-6 text-default">Rsync Options</label>
            <!-- Basic options -->
            <div class="grid grid-cols-4 gap-4">
                <div class="col-span-1">
                    <div name="options-archive" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Archive
                            <InfoTile class="ml-1" title="Archive mode. Equivalent to Recursive + Preserve the following: Times, Symbolic Links, Permissions, Groups, Owner, Devices/Specials (cli flags: -rlptgoD)" />
                        </label>
                        <input type="checkbox" v-model="isArchive" class=" h-4 w-4 rounded"/>
                    </div>
                    <div name="options-recursive" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Recursive
                            <InfoTile class="ml-1" title="Recurse into directories." />
                        </label>
                        <!-- <input v-if="isArchive" disabled :checked="true" type="checkbox" class=" h-4 w-4 rounded"/>
                        <input v-else type="checkbox" v-model="isRecursive" class=" h-4 w-4 rounded"/> -->
                        <input type="checkbox" v-model="isRecursive" class=" h-4 w-4 rounded"/>
                    </div>
                    <div name="options-compressed" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Compressed
                            <InfoTile class="ml-1" title="Compress file data during the transfer." />
                    </label>
                        <input type="checkbox" v-model="isCompressed" class=" h-4 w-4 rounded"/>
                    </div>
                    <div name="options-preserve-times" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Preserve Times
                            <InfoTile class="ml-1" title="Preserve modification times." />
                        </label>
                        <!-- <input v-if="isArchive" disabled :checked="true" type="checkbox" class=" h-4 w-4 rounded"/>
                        <input v-else type="checkbox" v-model="preserveTimes" class=" h-4 w-4 rounded"/> -->
                        <input type="checkbox" v-model="preserveTimes" class=" h-4 w-4 rounded"/>
                    </div>
                    <div name="options-delete" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Delete Files
                            <InfoTile class="ml-1" title="Deletes files in target path that do not exist in source." />
                        </label>
                        <input type="checkbox" v-model="deleteFiles" class=" h-4 w-4 rounded"/>
                    </div>
                    <div name="options-quiet" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Quiet
                            <InfoTile class="ml-1" title="Suppress non-error messages." />
                        </label>
                        <input type="checkbox" v-model="isQuiet" class=" h-4 w-4 rounded"/>
                    </div>
                </div>
                
                <div class="-mt-1 col-span-3 grid grid-cols-2 gap-2">
                    <div class="grid grid-cols-2 col-span-2 gap-2 w-full justify-center items-center text-center">
                        <div name="options-include" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="mt-1 block text-sm leading-6 text-default">
                                    Include Pattern
                                    <InfoTile class="ml-1" title="Pattern applying to specific directories/files to include." />
                                </label>
                            </div>
                            <input type="text" v-model="includePattern" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Include files matching this pattern."/> 
                        </div>
                        <div name="options-exclude" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="mt-1 block text-sm leading-6 text-default">
                                    Exclude Pattern
                                    <InfoTile class="ml-1" title="Pattern applying to specific directories/files to exclude." />
                                </label>
                            </div>
                            <input type="text" v-model="excludePattern" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Exclude files matching this pattern."/> 
                        </div>
                    </div>
                    <div name="options-extra-params" class="col-span-2">
                        <div class="flex flex-row justify-between items-center">
                            <label class="block text-sm leading-6 text-default">
                                Extra Parameters
                                <InfoTile class="ml-1" title="Separate any extra parameters, flags or options you wish to include with commas (,)." />
                            </label>
                        </div>
                        <input type="text" v-model="extraUserParams" class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="Eg. --partial, -c, -d"/> 
                    </div>
                </div>

                <div class="col-span-4">
                    <Disclosure v-slot="{ open }">
                        <DisclosureButton class="bg-default mt-2 w-full justify-start text-center rounded-md flex flex-row">
                            <div class="m-1">
                                <ChevronUpIcon class="h-7 w-7 text-default transition-all duration-200 transform" :class="{ 'rotate-90': !open, 'rotate-180': open, }"/>
                            </div>
                            <div class="ml-3 mt-1.5">
                                <span class="text-start text-base text-default">Advanced Options</span>
                            </div>
                        </DisclosureButton>
                        <DisclosurePanel>
                            <div class="w-full grid grid-cols-4 gap-4 bg-default p-4 -mt-1">
                                <div class="col-span-2 grid grid-cols-2">
                                    <div name="options-preserve-hard-links" class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            Preserve Hard Links
                                        </label>
                                        <input type="checkbox" v-model="preserveHardLinks" class=" h-4 w-4 rounded"/>
                                    </div>
                                    <div name="options-preserve-extended-attributes" class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            Preserve Extended Attributes
                                        </label>
                                        <input type="checkbox" v-model="preserveXattr" class=" h-4 w-4 rounded"/>
                                    </div>
                                    <div name="options-limit-bw" class="col-span-2">        
                                        <label class="mt-1 block text-sm leading-6 text-default">
                                            Limit Bandwidth (Kbps)
                                            <InfoTile class="ml-1" title="Limit I/O bandwidth; KBytes per second" />
                                        </label>
                                        <input type="text" v-model="limitBandwidthKbps" class="mt-1 block w-fit text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder="0"/> 
                                    </div>
                                </div>

                                <div class="col-span-2 grid grid-cols-2">
                                    <div name="options-preserve-permissions" class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            Preserve Permissions
                                        </label>
                                        <!-- <input v-if="isArchive" disabled :checked="true" type="checkbox" class=" h-4 w-4 rounded"/>
                                        <input v-else type="checkbox" v-model="preservePerms" class=" h-4 w-4 rounded"/> -->
                                        <input type="checkbox" v-model="preservePerms" class=" h-4 w-4 rounded"/>
                                    </div>
                                   
                                    <div name="options-parallel" class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            Use Parallel Threads
                                            <InfoTile class="ml-1" title="Increase transfer speeds by starting simulaneous transfers. Keep in mind system resources." />
                                        </label>
                                        <input type="checkbox" v-model="isParallel" class=" h-4 w-4 rounded"/>
                                    </div>
                                    <div name="options-parallel-threads" class="col-span-2">
                                        <label class="mt-1 block text-sm leading-6 text-default">
                                            # of Threads
                                            <InfoTile class="ml-1" title="Choosing the amount of threads depends on the system/load on the system. Keep in mind system resources." />
                                        </label>
                                        <input v-if="isParallel" type="number" v-model="parallelThreads" class="mt-1 block w-min text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder=""/> 
                                        <input v-else disabled type="number" v-model="parallelThreads" class="mt-1 block w-fit text-default input-textlike sm:text-sm sm:leading-6 bg-default" placeholder=""/> 
                                    </div>

                                </div>
                            </div>
                        </DisclosurePanel>
                    </Disclosure>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, inject } from 'vue';
import { Disclosure, DisclosureButton, DisclosurePanel, Switch } from '@headlessui/vue';
import { ExclamationCircleIcon, ChevronDoubleRightIcon, ChevronUpIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, IntParameter, StringParameter, BoolParameter } from '../../../models/Parameters';
import { testSSH } from '../../../composables/utility';
import { pushNotification, Notification } from 'houston-common-ui';

interface RsyncTaskParamsProps {
   parameterSchema: ParameterNodeType;
   task?: TaskInstanceType;
}

const props = defineProps<RsyncTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;

const sourcePath = ref('');
const sourcePathErrorTag = ref(false);
const destPath = ref('');
const destPathErrorTag = ref(false);

const destHost = ref('');
const destHostErrorTag = ref(false);
const destPort = ref(22);
const destUser = ref('root');
const directionSwitched = ref(false)

const isArchive = ref(true);
const isRecursive = ref(false);
const isCompressed = ref(true);
const isQuiet = ref(false);
const deleteFiles = ref(false);
const preserveTimes = ref(false);
const preserveHardLinks = ref(false);
const preservePerms = ref(false);
const preserveXattr = ref(false);
const limitBandwidthKbps = ref('');
const includePattern = ref('');
const excludePattern = ref('');
const isParallel = ref(false);
const parallelThreads = ref(0);
const extraUserParams = ref('');

const testingSSH = ref(false);
const sshTestResult = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

async function initializeData() {
    // if props.task, then edit mode active (retrieve data)
    if (props.task) {
        loading.value = true;

        // assign values

        loading.value = false;
    } else {
       //if no props.task, new task configuration (default values)

    }
}

function handleCheckboxChange(checkbox) {
    /* // Ensure only one checkbox (raw, compressed) is selected at a time
    if (checkbox === 'sendCompressed' && sendCompressed.value) {
        sendRaw.value = false;
    } else if (checkbox === 'sendRaw' && sendRaw.value) {
        sendCompressed.value = false;
    } */
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

function validateSourcePath() {

}

function validateDestinationPath() {
  
}


function isValidPoolName(poolName) {
   /*  if (poolName === '') {
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
    return true; */
}

function doesItExist(thisName: string, list: string[]) {
   /*  if (list.includes(thisName)) {
        return true;
    } else {
        return false;
    } */
}


function isValidDatasetName(datasetName) {
   /*  if (datasetName === '') {
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
    return true; */
}

function clearErrorTags() {
    destHostErrorTag.value = false;
    sourcePathErrorTag.value = false;
    destPathErrorTag.value = false;
    errorList.value = [];
}

function validateParams() {
    // clearErrorTags();
    validateSourcePath();
    validateHost();
    validateDestinationPath();

    if (errorList.value.length == 0) {
        setParams();
    }
}

function setParams() {
    const newParams = new ParameterNode("Rsync Task Config", "rsyncConfig")
        
    ;

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

onMounted(async () => {
    await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
});
</script>