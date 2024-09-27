<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                :fillColor="'fill-gray-500'" />
        </div>
    </div>
    <div v-else class="grid grid-cols-2 my-2 gap-2 h-full" style="grid-template-rows: auto auto 1fr;">
        <!-- TOP -->
        <div name="rclone-remotes"
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-1 bg-accent"
            style="grid-row: 1 / span 1;">
            <label class="mt-1 mb-2 col-span-1 block text-base leading-6 text-default">Remote Configuration</label>
            <div name="select-remote" class="grid grid-cols-2 gap-x-2">
                <div class="flex flex-row justify-between items-center col-span-2">
                    <label class="mt-1 block text-sm leading-6 text-default">
                        Select Existing Remote
                        <InfoTile class="ml-1" title="" />
                    </label>
                </div>
                <select id="existing-remote-selection" v-model="selectedRemote" name="existing-remote-selection"
                    class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6 col-span-1">
                    <option :value="undefined">Select Remote</option>
                    <option v-for="remote, idx in existingRemotes" :key="idx" :value="remote.name">
                        {{ remote.name}}
                    </option>
                </select>
                <div class="col-span-1 button-group-row mt-0.5">
                    <button @click.stop="createRemoteBtn()" id="new-remote-btn" name="new-remote-btn"
                        class="mt-1 btn btn-primary h-fit w-full pl-1">
                        Create New Remote
                    </button>
                    <button @click.stop="" id="manage-remotes-btn" name="manage-remotes-btn"
                        class="mt-1 btn btn-secondary h-fit w-full">
                        Manage Existing Remotes
                    </button>
                </div>
                <!-- Change button based on remote's provider/type (Remote Name, and provider Logo + Color) -->
                <button @click.stop="authenticateRemoteBtn(selectedRemote!)" id="authenticate-selected-remote-btn"
                    name="authenticate-selected-remote-btn" class="mt-1 btn btn-danger h-fit w-full col-span-2">
                    Authenticate (REMOTE NAME) (LOGO)
                </button>
            </div>

            <div name="transfer-config" class="grid grid-cols-2 col-span-2 gap-x-2">
                <div name="transfer-type" class="col-span-1 mt-1.5">
                    <div class="flex flex-row justify-between items-center">
                        <label class="block text-sm leading-6 text-default">
                            Transfer Type
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <!-- <ExclamationCircleIcon v-if="selectedRemoteErrorTag" class="mt-1 w-5 h-5 text-danger" /> -->
                    </div>
                    <div class="">
                        <select id="existing-remote-selection" v-model="selectedRemote" name="existing-remote-selection"
                            class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                            <option :value="undefined">Select Type of Rclone Transfer</option>
                            <option :value="'copy'">Copy</option>
                            <option :value="'move'">Move</option>
                            <option :value="'sync'">Sync</option>
                        </select>
                    </div>
                </div>
                <div name="direction" class="col-span-1">
                    <div
                        class="w-full mt-2 flex flex-row justify-between items-center text-center space-x-2 text-default">
                        <label v-if="directionSwitched" class="block text-sm leading-6 text-default">
                            Direction - Pull
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
                        <div
                            class="flex flex-row justify-around text-center items-center space-x-1 bg-plugin-header rounded-lg p-2">
                            <span class="text-default">Local Directory</span>
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
                            <span class="text-default">Cloud Target</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- BOTTOM -->
        <div name="rclone-options"
            class="border border-default rounded-md p-2 col-span-2 row-span-1 row-start-2 bg-accent"
            style="grid-row: 2 / span 1;">
            <label class="mt-1 block text-base leading-6 text-default">Rclone Options</label>
            <!-- Basic options -->
            <div class="grid grid-cols-4 gap-4">
                <div class="col-span-1">
                    <!-- <div name="options-archive" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Archive
                            <InfoTile class="ml-1"
                                title="Archive mode. Equivalent to Recursive + Preserve the following: Times, Symbolic Links, Permissions, Groups, Owner, Devices/Specials (cli flags: -rlptgoD)" />
                        </label>
                        <input type="checkbox" v-model="isArchive" class=" h-4 w-4 rounded"
                            :class="[isDeleteErrorTag ? 'rounded-md outline outline-1 outline-offset-1 outline-rose-500 dark:outline-rose-700' : '']" />
                    </div>
                    <div name="options-recursive" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Recursive
                            <InfoTile class="ml-1" title="Recurse into directories." />
                        </label>
                        <input type="checkbox" v-model="isRecursive" class=" h-4 w-4 rounded"
                            :class="[isDeleteErrorTag ? 'rounded-md outline outline-1 outline-offset-1 outline-rose-500 dark:outline-rose-700' : '']" />
                    </div>
                    <div name="options-compressed" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Compressed
                            <InfoTile class="ml-1" title="Compress file data during the transfer." />
                        </label>
                        <input type="checkbox" v-model="isCompressed" class=" h-4 w-4 rounded" />
                    </div>
                    <div name="options-preserve-times"
                        class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Preserve Times
                            <InfoTile class="ml-1" title="Preserve modification times." />
                        </label>
                        <input type="checkbox" v-model="preserveTimes" class=" h-4 w-4 rounded" />
                    </div>
                    <div name="options-delete" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Delete Files
                            <InfoTile class="ml-1"
                                title="Deletes files in target path that do not exist in source. (REQUIRES Archive or Recursive)" />
                        </label>
                        <input type="checkbox" v-model="deleteFiles" class=" h-4 w-4 rounded" />
                    </div>
                    <div name="options-quiet" class="flex flex-row justify-between items-center mt-1 col-span-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Quiet
                            <InfoTile class="ml-1" title="Suppress non-error messages." />
                        </label>
                        <input type="checkbox" v-model="isQuiet" class=" h-4 w-4 rounded" />
                    </div> -->
                </div>

                <div class="-mt-1 col-span-3 grid grid-cols-2 gap-2">
                    <div class="grid grid-cols-2 col-span-2 gap-2 w-full justify-center items-center text-center">
                        <div name="options-include" class="col-span-1">
                            <!-- <div class="flex flex-row justify-between items-center">
                                <label class="mt-1 block text-sm leading-6 text-default">
                                    Include Pattern
                                    <InfoTile class="ml-1"
                                        title="Pattern applying to specific directories/files to include. Separate patterns with commas (,)." />
                                </label>
                            </div>
                            <input type="text" v-model="includePattern"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Eg. */, *.txt" /> -->
                        </div>
                        <div name="options-exclude" class="col-span-1">

                        </div>
                    </div>
                    <div name="options-extra-params" class="col-span-2">

                    </div>
                </div>

                <div class="col-span-4">
                    <Disclosure v-slot="{ open }">
                        <DisclosureButton
                            class="bg-default mt-2 w-full justify-start text-center rounded-md flex flex-row">
                            <div class="m-1">
                                <ChevronUpIcon class="h-7 w-7 text-default transition-all duration-200 transform"
                                    :class="{ 'rotate-90': !open, 'rotate-180': open, }" />
                            </div>
                            <div class="ml-3 mt-1.5">
                                <span class="text-start text-base text-default">Advanced Options</span>
                            </div>
                        </DisclosureButton>
                        <DisclosurePanel>
                            <div class="w-full grid grid-cols-4 gap-4 bg-default p-4 -mt-1">
                                <div class="col-span-2 grid grid-cols-2">

                                </div>

                                <div class="col-span-2 grid grid-cols-2">

                                </div>
                            </div>
                        </DisclosurePanel>
                    </Disclosure>
                </div>
            </div>
        </div>
    </div>

    <div v-if="showCreateRemote">
        <component :is="createRemoteComponent" :id-key="'create-remote-modal'"/>
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, inject, provide } from 'vue';
import { Disclosure, DisclosureButton, DisclosurePanel, Switch } from '@headlessui/vue';
import { ExclamationCircleIcon, ChevronDoubleRightIcon, ChevronUpIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, IntParameter, StringParameter, BoolParameter, SelectionParameter, SelectionOption, LocationParameter, ObjectParameter } from '../../../models/Parameters';
import { CloudAuthParameter, cloudSyncProviders, CloudSyncProvider, CloudSyncRemote, createCloudAuthParameter } from '../../../models/CloudSync';
import { injectWithCheck, testSSH } from '../../../composables/utility';
import { pushNotification, Notification } from 'houston-common-ui';
import { rcloneRemotesInjectionKey } from '../../../keys/injection-keys';

interface CloudSyncParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
}

const props = defineProps<CloudSyncParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const initialParameters = ref({});
const directionSwitched = ref(false)

const selectedRemote = ref<CloudSyncRemote>();
const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, "remotes not provided!");


function authenticateRemoteBtn(selectedRemote: CloudSyncRemote) {

}

interface ProviderLogo {
    logo: string;
    color: string;
}

const providerLogos: { [key: string]: ProviderLogo } = {
    "s3-AWS": {
        logo: "/public/img/s3-amazon.svg",
        color: "#E05243"
    },
    "s3-Wasabi": {
        logo: "/public/img/s3-wasabi.svg",
        color: "#01CE3F"
    },
    "b2": {
        logo: "/public/img/backblaze.svg",
        color: "#D2202F"
    },
    "dropbox": {
        logo: "/public/img/dropbox.svg",
        color: "#0061FF"
    },
    "drive": {
        logo: "/public/img/google-drive.svg",
        color: "#FF4329"
    },
    "onedrive": {
        logo: "/public/img/onedrive.svg",
        color: "#4F8AD8"
    },
    "google cloud storage": {
        logo: "/public/img/google-cloud.svg",
        color: "#FF7E56"
    },
    "azureblob": {
        logo: "/public/img/azure.svg",
        color: "#00BCF2"
    }
};

// Function to fetch logo and color
function getProviderLogo(providerKey: string): ProviderLogo | undefined {
    return providerLogos[providerKey];
}

// Example usage
const awsLogo = getProviderLogo("s3-AWS");
console.log(awsLogo?.logo, awsLogo?.color);


const showCreateRemote = ref(false);
async function createRemoteBtn() {
    await loadCreateRemoteComponent();
    showCreateRemote.value = true;
}
const createRemoteComponent = ref();
async function loadCreateRemoteComponent() {
    const module = await import('../../modals/CreateRemote.vue');
    createRemoteComponent.value = module.default;
}



function hasChanges() {
    // const currentParams = {
    //     sourcePath: sourcePath.value,
    //     destPath: destPath.value,
    //     destHost: destHost.value,
    //     destUser: destUser.value,
    //     destRoot: destRoot.value,
    //     destPort: destPort.value,
    //     directionSwitched: directionSwitched.value,
    //     isArchive: isArchive.value,
    //     isRecursive: isRecursive.value,
    //     isCompressed: isCompressed.value,
    //     isQuiet: isQuiet.value,
    //     deleteFiles: deleteFiles.value,
    //     preserveTimes: preserveTimes.value,
    //     preserveHardLinks: preserveHardLinks.value,
    //     preservePerms: preservePerms.value,
    //     preserveXattr: preserveXattr.value,
    //     limitBandwidthKbps: limitBandwidthKbps.value,
    //     includePattern: includePattern.value,
    //     excludePattern: excludePattern.value,
    //     extraUserParams: extraUserParams.value,
    //     isParallel: isParallel.value,
    //     parallelThreads: parallelThreads.value
    // };

    // return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}

function clearErrorTags() {
    // sourcePathErrorTag.value = false;
    // destPathErrorTag.value = false;
    // destHostErrorTag.value = false;
    // isDeleteErrorTag.value = false;
    // errorList.value = [];
}

function validateParams() {
    // // clearErrorTags();
    // validateSourcePath();
    // validateHost();
    // validateDestinationPath();
    // validateDependantParams();
    // // validateNumber('Bandwidth limit', limitBandwidthKbps.value);
    // sanitizeNumber(limitBandwidthKbps.value);

    // if (errorList.value.length == 0 && sourcePathErrorTag.value == false && destPathErrorTag.value == false) {
    //     setParams();
    // }
}

function setParams() {
    const directionPUSH = new SelectionOption('push', 'Push');
    const directionPULL = new SelectionOption('pull', 'Pull');

    const transferDirection = ref();
    // PUSH = false, PULL = true
    // if (directionSwitched.value) {
    //     transferDirection.value = directionPULL;
    // } else {
    //     transferDirection.value = directionPUSH;
    // }

    // const newParams = new ParameterNode("Rsync Task Config", "rsyncConfig")
    //     .addChild(new StringParameter('Local Path', 'local_path', sourcePath.value))
    //     .addChild(new LocationParameter('Target Information', 'target_info', destHost.value, destPort.value, destUser.value, destRoot.value, destPath.value))
    //     .addChild(new SelectionParameter('Direction', 'direction', transferDirection.value.value))
    //     .addChild(new ParameterNode('Rsync Options', 'rsyncOptions')
    //         .addChild(new BoolParameter('Archive', 'archive_flag', isArchive.value))
    //         .addChild(new BoolParameter('Recursive', 'recursive_flag', isRecursive.value))
    //         .addChild(new BoolParameter('Compressed', 'compressed_flag', isCompressed.value))
    //         .addChild(new BoolParameter('Delete', 'delete_flag', deleteFiles.value))
    //         .addChild(new BoolParameter('Quiet', 'quiet_flag', isQuiet.value))
    //         .addChild(new BoolParameter('Preserve Times', 'times_flag', preserveTimes.value))
    //         .addChild(new BoolParameter('Preserve Hard Links', 'hardLinks_flag', preserveHardLinks.value))
    //         .addChild(new BoolParameter('Preserve Permissions', 'permissions_flag', preservePerms.value))
    //         .addChild(new BoolParameter('Preserve Extended Attributes', 'xattr_flag', preserveXattr.value))
    //         .addChild(new IntParameter('Limit Bandwidth', 'bandwidth_limit_kbps', limitBandwidthKbps.value))
    //         .addChild(new StringParameter('Include', 'include_pattern', `'${includePattern.value}'`))
    //         .addChild(new StringParameter('Exclude', 'exclude_pattern', `'${excludePattern.value}'`))
    //         .addChild(new BoolParameter('Parallel Transfer', 'parallel_flag', isParallel.value))
    //         .addChild(new IntParameter('Threads', 'parallel_threads', parallelThreads.value))
    //         .addChild(new StringParameter('Additional Custom Arguments', 'custom_args', `'${extraUserParams.value}'`))
    //     );

    // parameters.value = newParams;
    // console.log('newParams:', newParams);
}

async function confirmTest(destHost, destUser) {
    // testingSSH.value = true;

    // const sshTarget = destUser + '@' + destHost;
    // sshTestResult.value = await testSSH(sshTarget);

    // if (sshTestResult.value) {
    //     pushNotification(new Notification('Connection Successful!', `Passwordless SSH connection established. This host can be used for remote transfers.`, 'success', 8000));
    // } else {
    //     pushNotification(new Notification('Connection Failed', `Could not resolve hostname "${destHost}": \nName or service not known.\nMake sure passwordless SSH connection has been configured for target system.`, 'error', 8000));
    // }
    // testingSSH.value = false;
}

onMounted(async () => {
    // await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});

provide('show-create-remote', showCreateRemote);
</script>