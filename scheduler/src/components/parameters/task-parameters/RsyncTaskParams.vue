<template>
    <!-- SIMPLE MODE -->
    <div v-if="props.simple" class="space-y-4 my-2">

        <!-- What to copy -->
        <SimpleFormCard title="What do you want to copy?"
            description="Choose a folder stored on this server that was created by a client backup. This is the backed-up copy of your files, not your live PC.">
            <label class="block text-sm mt-1 text-default">
                From (Source)
                <InfoTile class="ml-1" :title="tooltips.source" />
            </label>

            <!-- loading -->
            <div v-if="loadingFolders" class="mt-2 flex items-center gap-2">
                <CustomLoadingSpinner :width="'w-5'" :height="'h-5'" :baseColor="'text-gray-200'"
                    :fillColor="'fill-gray-500'" />
                <span class="text-sm text-muted">Discovering your folders…</span>
            </div>

            <!-- error -->
            <div v-else-if="discoveryError" class="mt-2 p-2 rounded bg-danger/10 text-danger text-sm">
                {{ discoveryError }}
                <div class="mt-1 text-xs text-default/70">
                    You can still type a path manually below.
                    <button class="btn btn-xxs btn-secondary ml-2" @click="folderList.refresh()">Retry</button>
                </div>
            </div>

            <!-- select when we have options -->
            <div v-else-if="opts.length">
                <select v-model="sourcePath" class="input-textlike text-sm w-full text-default bg-default rounded-md">
                    <option v-for="opt in opts" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                    </option>
                </select>
                <p class="text-[11px] text-muted mt-1">
                    Scope: {{ shareRoot || '—' }}
                    <span> • Full Path: {{ sourcePath }}</span>
                    <span v-if="smbUser"> • User: {{ smbUser }}</span>
                </p>
            </div>

            <!-- manual input fallback -->
            <div v-else class="mt-1">
                <input type="text" v-model="sourcePath" :class="[
                    'mt-1 block w-full input-textlike sm:text-sm bg-default text-default',
                    sourcePathErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]" placeholder="e.g. /mnt/backup/projects/" />
                <p class="text-[11px] text-muted mt-1">No folders found; enter a path manually.</p>
                <p class="text-[11px] text-muted mt-1">
                    Note: In this mode, source must be a folder (end with <code>/</code>).
                </p>
            </div>

            <label class="block text-sm mt-3 text-default">
                To (Target)
                <InfoTile class="ml-1" :title="tooltips.target" />
            </label>

            <input type="text" v-model="destPath" :class="[
                'mt-1 block w-full input-textlike sm:text-sm bg-default text-default',
                destPathErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
            ]" placeholder="e.g. /mnt/backup/projects/ or /mnt/backup/archive.tar" />

            <p class="text-[11px] text-muted mt-1">
                Tip: A trailing <code>/</code> changes how rsync copies folders; see tooltip.
            </p>
        </SimpleFormCard>

        <!-- Copy to another server (optional) -->
        <SimpleFormCard title="Copy to another server (optional)"
            description="Leave “Server address” empty to copy on this machine.">
            <template #header-right>
                <button v-if="!testingSSH" @click="handleTestSSH" class="btn btn-secondary h-fit">
                    Test SSH
                </button>
                <button v-else disabled class="btn btn-secondary h-fit">Testing…</button>
            </template>

            <div class="grid grid-cols-3 gap-2">
                <div>
                    <label class="block text-sm mt-3 text-default">Server address</label>
                    <input type="text" v-model="destHost" :class="[
                        'mt-1 block w-full input-textlike sm:text-sm bg-default text-default',
                        destHostErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" placeholder="e.g. backup.example.com or 10.0.0.5" />
                </div>

                <div>
                    <label class="block text-sm mt-3 text-default">User</label>
                    <input type="text" v-model="destUser"
                        class="mt-1 block w-full input-textlike sm:text-sm bg-default text-default"
                        placeholder="root (default)" :disabled="!destHost" />
                </div>

                <div>
                    <label class="block text-sm mt-3 text-default" for="dest-pass">Password</label>
                    <div class="relative mt-1">
                        <input :type="showPassword ? 'text' : 'password'" id="dest-pass" v-model="destUserPass"
                            class="block w-full input-textlike sm:text-sm bg-default text-default pr-10"
                            :disabled="!destHost" />
                        <button type="button" @click="togglePassword"
                            class="absolute inset-y-0 right-0 px-3 flex items-center text-muted"
                            :aria-label="showPassword ? 'Hide password' : 'Show password'">
                            <EyeIcon v-if="!showPassword" class="w-5 h-5" />
                            <EyeSlashIcon v-else class="w-5 h-5" />
                        </button>
                    </div>
                </div>
            </div>

            <template #footer>
                <p class="text-[11px] text-muted">
                    We’ll use SSH for remote copies. Keep the server field empty for local copies.
                </p>
            </template>
        </SimpleFormCard>
    </div>

    <div v-else>
        <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
            <div
                class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
                <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                    :fillColor="'fill-gray-500'" />
            </div>
        </div>

        <div v-else class="grid grid-cols-2 my-2 gap-2 h-full" style="grid-template-rows: auto auto 1fr;">
            <!-- TOP LEFT -->
            <div name="paths-data"
                class="border border-default rounded-md p-2 col-span-1 row-start-1 row-span-1 bg-accent"
                style="grid-row: 1 / span 1;">
                <label class="mt-1 mb-2 col-span-1 block text-base leading-6 text-default">Transfer Details</label>

                <div name="source-path">
                    <div class="flex flex-row justify-between items-center">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Source
                            <InfoTile class="ml-1" :title="tooltips.source" />
                        </label>
                        <ExclamationCircleIcon v-if="sourcePathErrorTag" class="mt-1 w-5 h-5 text-danger" />
                    </div>
                    <div>
                        <input type="text" v-model="sourcePath"
                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                            :class="[sourcePathErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                            placeholder="Specify source path" />
                    </div>
                </div>

                <div name="destination-path">
                    <div class="flex flex-row justify-between items-center">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Target
                            <InfoTile class="ml-1" :title="tooltips.target" />
                        </label>
                        <ExclamationCircleIcon v-if="destPathErrorTag" class="mt-1 w-5 h-5 text-danger" />
                    </div>
                    <div>
                        <input type="text" v-model="destPath"
                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                            :class="[destPathErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                            placeholder="Specify target path" />
                    </div>
                </div>

                <div name="direction" class="">
                    <div
                        class="w-full mt-2 flex flex-row justify-between items-center text-center space-x-2 text-default">
                        <span v-if="directionSwitched">Direction - Pull</span>
                        <span v-else>Direction - Push</span>

                        <Switch v-model="directionSwitched" :class="[
                            directionSwitched ? 'bg-secondary' : 'bg-well',
                            'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-slate-600 focus:ring-offset-2'
                        ]">
                            <span class="sr-only">Use setting</span>
                            <span aria-hidden="true" :class="[
                                directionSwitched ? 'translate-x-5' : 'translate-x-0',
                                'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-default shadow ring-0 transition duration-200 ease-in-out'
                            ]" />
                        </Switch>
                    </div>

                    <div class="w-full mt-2 justify-center items-center">
                        <div
                            class="flex flex-row justify-around text-center items-center space-x-1 bg-plugin-header rounded-lg p-2">
                            <span class="text-default">Source</span>
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
                            <span class="text-default">Target</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TOP RIGHT -->
            <div name="destination-ssh-data" class="border border-default rounded-md p-2 col-span-1 bg-accent"
                style="grid-row: 1 / span 1;">
                <div class="grid grid-cols-2">
                    <label class="mt-1 col-span-1 block text-base leading-6 text-default">Remote Target</label>
                    <div class="col-span-1 items-end text-end justify-end">
                        <button disabled v-if="testingSSH"
                            class="mt-0.5 btn btn-secondary object-right justify-end h-fit">
                            <svg aria-hidden="true" role="status"
                                class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default"
                                viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path
                                    d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                                    fill="currentColor" />
                                <path
                                    d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                                    fill="text-success" />
                            </svg>
                            Testing...
                        </button>

                        <button v-else @click="confirmTest(destHost, destUser)"
                            class="mt-0.5 btn btn-secondary object-right justify-end h-fit">
                            Test SSH
                        </button>
                    </div>
                </div>

                <div name="destination-host" class="mt-1">
                    <div class="flex flex-row justify-between items-center">
                        <label class="block text-sm leading-6 text-default">Host</label>
                        <ExclamationCircleIcon v-if="destHostErrorTag" class="mt-1 w-5 h-5 text-danger" />
                    </div>
                    <input type="text" v-model="destHost"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        :class="[destHostErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                        placeholder="Leave blank for local transfer." />
                </div>

                <div name="destination-user" class="mt-1">
                    <label class="block text-sm leading-6 text-default">User</label>
                    <input :disabled="destHost === ''" type="text" v-model="destUser"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="'root' is default" />
                </div>

                <div name="destination-port" class="mt-1">
                    <label class="block text-sm leading-6 text-default">Port</label>
                    <input :disabled="destHost === ''" type="number" v-model="destPort"
                        class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default" min="0"
                        max="65535" placeholder="22 is default" />
                </div>
            </div>

            <!-- BOTTOM -->
            <div name="send-options"
                class="border border-default rounded-md p-2 col-span-2 row-span-1 row-start-2 bg-accent"
                style="grid-row: 2 / span 1;">
                <label class="mt-1 block text-base leading-6 text-default">Rsync Options</label>

                <div class="grid grid-cols-4 gap-4">
                    <div class="col-span-1">
                        <div name="options-archive" class="flex flex-row justify-between items-center mt-1 col-span-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Archive
                                <InfoTile class="ml-1" :title="tooltips.archive" />
                            </label>
                            <input type="checkbox" v-model="isArchive" class="h-4 w-4 rounded"
                                :class="[isDeleteErrorTag ? 'rounded-md outline outline-1 outline-offset-1 outline-rose-500 dark:outline-rose-700' : '']" />
                        </div>

                        <div name="options-recursive"
                            class="flex flex-row justify-between items-center mt-1 col-span-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Recursive
                                <InfoTile class="ml-1" :title="tooltips.recursive" />
                            </label>
                            <input type="checkbox" v-model="isRecursive" class="h-4 w-4 rounded"
                                :class="[isDeleteErrorTag ? 'rounded-md outline outline-1 outline-offset-1 outline-rose-500 dark:outline-rose-700' : '']" />
                        </div>

                        <div name="options-compressed"
                            class="flex flex-row justify-between items-center mt-1 col-span-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Compressed
                                <InfoTile class="ml-1" :title="tooltips.compressed" />
                            </label>
                            <input type="checkbox" v-model="isCompressed" class="h-4 w-4 rounded" />
                        </div>

                        <div name="options-preserve-times"
                            class="flex flex-row justify-between items-center mt-1 col-span-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Preserve Times
                                <InfoTile class="ml-1" :title="tooltips.times" />
                            </label>
                            <input type="checkbox" v-model="preserveTimes" class="h-4 w-4 rounded" />
                        </div>

                        <div name="options-delete" class="flex flex-row justify-between items-center mt-1 col-span-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Delete Files
                                <InfoTile class="ml-1" :title="tooltips.delete" />
                            </label>
                            <input type="checkbox" v-model="deleteFiles" class="h-4 w-4 rounded" />
                        </div>

                        <div name="options-quiet" class="flex flex-row justify-between items-center mt-1 col-span-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Quiet
                                <InfoTile class="ml-1" :title="tooltips.quiet" />
                            </label>
                            <input type="checkbox" v-model="isQuiet" class="h-4 w-4 rounded" />
                        </div>
                    </div>

                    <div class="-mt-1 col-span-3 grid grid-cols-2 gap-2">
                        <div class="grid grid-cols-2 col-span-2 gap-2 w-full justify-center items-center text-center">
                            <div name="options-include" class="col-span-1">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="mt-1 block text-sm leading-6 text-default">
                                        Include Pattern
                                        <InfoTile class="ml-1" :title="tooltips.include" />
                                    </label>
                                </div>
                                <input type="text" v-model="includePattern"
                                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                    placeholder="Eg. */, *.txt" />
                            </div>

                            <div name="options-exclude" class="col-span-1">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="mt-1 block text-sm leading-6 text-default">
                                        Exclude Pattern
                                        <InfoTile class="ml-1" :title="tooltips.exclude" />
                                    </label>
                                </div>
                                <input type="text" v-model="excludePattern"
                                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                    placeholder="Eg. temp*, *.py" />
                            </div>
                        </div>

                        <div name="options-log-file-path" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="block text-sm leading-6 text-default">
                                    Log File Path
                                    <InfoTile class="ml-1" :title="tooltips.logFile" />
                                </label>
                            </div>
                            <input type="text" v-model="logFilePath"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Eg. /var/log/newtask.log" :title="tooltips.logFile" />
                        </div>

                        <div name="options-extra-params" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="block text-sm leading-6 text-default">
                                    Extra Parameters
                                    <InfoTile class="ml-1" :title="tooltips.extra" />
                                </label>
                            </div>
                            <input type="text" v-model="extraUserParams"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Eg. --partial, -c, -d" />
                        </div>
                    </div>

                    <div class="col-span-4">
                        <Disclosure v-slot="{ open }">
                            <DisclosureButton
                                class="bg-default mt-2 w-full justify-start text-center rounded-md flex flex-row">
                                <div class="m-1">
                                    <ChevronUpIcon class="h-7 w-7 text-default transition-all duration-200 transform"
                                        :class="{ 'rotate-90': !open, 'rotate-180': open }" />
                                </div>
                                <div class="ml-3 mt-1.5">
                                    <span class="text-start text-base text-default">Advanced Options</span>
                                </div>
                            </DisclosureButton>

                            <DisclosurePanel>
                                <div class="w-full grid grid-cols-4 gap-4 bg-default p-4 -mt-1">
                                    <div class="col-span-2 grid grid-cols-2 gap-2">
                                        <div name="options-preserve-hard-links"
                                            class="flex items-center gap-2 mt-1 col-span-1">
                                            <label class="text-sm leading-6 text-default">
                                                Preserve Hard Links
                                                <InfoTile class="ml-1" :title="tooltips.hardLinks" />
                                            </label>
                                            <input type="checkbox" v-model="preserveHardLinks"
                                                class="h-4 w-4 rounded" />
                                        </div>

                                        <div name="options-preserve-extended-attributes"
                                            class="flex items-center gap-2 mt-1 col-span-1">
                                            <label class="text-sm leading-6 text-default">
                                                Preserve Extended Attrs.
                                                <InfoTile class="ml-1" :title="tooltips.xattr" />
                                            </label>
                                            <input type="checkbox" v-model="preserveXattr" class="h-4 w-4 rounded" />
                                        </div>

                                        <div name="options-limit-bw" class="col-span-2">
                                            <label class="mt-1 block text-sm leading-6 text-default">
                                                Limit Bandwidth (Kbps)
                                                <InfoTile class="ml-1" :title="tooltips.bw" />
                                            </label>
                                            <input type="number" v-model="limitBandwidthKbps"
                                                class="mt-1 block w-fit text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="0" />
                                        </div>
                                    </div>

                                    <div class="col-span-2 grid grid-cols-2 gap-2">
                                        <div name="options-preserve-permissions"
                                            class="flex items-center gap-2 mt-1 col-span-1">
                                            <label class="text-sm leading-6 text-default">
                                                Preserve Permissions
                                                <InfoTile class="ml-1" :title="tooltips.perms" />
                                            </label>
                                            <input type="checkbox" v-model="preservePerms" class="h-4 w-4 rounded" />
                                        </div>

                                        <div name="options-parallel" class="flex items-center gap-2 mt-1 col-span-1">
                                            <label class="text-sm leading-6 text-default flex items-center">
                                                Use Parallel Threads
                                                <InfoTile class="ml-1" :title="tooltips.parallel" />
                                            </label>
                                            <input type="checkbox" v-model="isParallel" class="h-4 w-4 rounded"
                                                :disabled="parallelDisabled"
                                                :title="parallelDisabled ? tooltips.parallelDisabled : tooltips.parallel" />
                                        </div>

                                        <div name="options-parallel-threads" class="col-span-1">
                                            <label class="mt-1 block text-sm leading-6 text-default">
                                                # of Threads
                                                <InfoTile class="ml-1" :title="tooltips.parallelThreads" />
                                            </label>
                                            <input :disabled="!isParallel || parallelDisabled" type="number"
                                                v-model="parallelThreads"
                                                class="mt-1 block w-fit text-default input-textlike sm:text-sm sm:leading-6 bg-default" />
                                        </div>

                                        <div v-if="parallelDisabled" class="col-span-2 -mt-1">
                                            <p class="text-[11px] text-muted">
                                                Parallel mode requires a directory-style source (ending with
                                                <code>/</code>).
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </DisclosurePanel>
                        </Disclosure>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, Ref, onMounted, inject, watch, computed, watchEffect } from 'vue';
import { Disclosure, DisclosureButton, DisclosurePanel, Switch } from '@headlessui/vue';
import { ExclamationCircleIcon, ChevronDoubleRightIcon, ChevronUpIcon, EyeIcon, EyeSlashIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import {
    ParameterNode,
    IntParameter,
    StringParameter,
    BoolParameter,
    SelectionParameter,
    SelectionOption,
    LocationParameter
} from '../../../models/Parameters';
import { testSSH, testOrSetupSSH, validateLocalPath } from '../../../composables/utility';
import { pushNotification, Notification } from '@45drives/houston-common-ui';
import SimpleFormCard from '../../simple/SimpleFormCard.vue';
import { useUserScopedFolderListByInstall } from '../../../composables/useUserScopedFolderListByInstall';
import { useClientContextStore } from '../../../stores/clientContext';

interface RsyncTaskParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
    simple?: boolean;
}

const props = defineProps<RsyncTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const initialParameters = ref({});

const sourcePath = ref('');
const sourcePathErrorTag = ref(false);
const destPath = ref('');
const destPathErrorTag = ref(false);
const destRoot = ref('');
const destHost = ref('');
const destHostErrorTag = ref(false);
const destPort = ref(22);
const destUser = ref('root');
const destUserPass = ref('');
const showPassword = ref(false);

const directionSwitched = ref(false);

const isArchive = ref(true);
const isRecursive = ref(false);
const isCompressed = ref(false);
const isQuiet = ref(false);

const deleteFiles = ref(false);
const isDeleteErrorTag = ref(false);

const preserveTimes = ref(false);
const preserveHardLinks = ref(false);
const preservePerms = ref(false);
const preserveXattr = ref(false);
const logFilePath = ref('');
const limitBandwidthKbps = ref(0);
const includePattern = ref('');
const excludePattern = ref('');

const isParallel = ref(false);
const parallelThreads = ref(0);

const extraUserParams = ref('');

const testingSSH = ref(false);
const sshTestResult = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

const sshReady = ref(false);

const tooltips = {
    source:
        "For folders, a trailing slash changes what rsync copies: " +
        "source/ copies the folder contents, while source copies the folder itself into the target. ",
    target:
        "Target can be a folder or a full file path. " +
        "For folder-to-folder copies, trailing slashes have the same meaning as the source: " +
        "target/ means ‘copy into this folder’, while target without / may create or rename the top-level folder. " +
        "If you set a file path, rsync writes to that filename (when copying a file).",

    archive:
        "Archive mode: preserves permissions, ownership, timestamps, symlinks, devices, and recurses. Equivalent to -rlptgoD.",

    recursive:
        "Recurse into directories (-r). If you only want to copy a single file, leave this off.",

    compressed:
        "Compress file data during transfer (-z). Helps on slow links; can hurt on CPU-bound systems.",

    times:
        "Preserve modification times (-t).",

    delete:
        "Delete files on the target that do not exist on the source (--delete). Requires Archive or Recursive. Use with care.",

    quiet:
        "Suppress non-error messages (-q).",

    include:
        "Patterns to include. Separate patterns with commas. Example: */ , *.txt",

    exclude:
        "Patterns to exclude. Separate patterns with commas. Example: temp* , *.py",

    logFile:
        "Optional path to an rsync log file. If set, rsync writes logs using --log-file=PATH.",

    extra:
        "Additional rsync arguments. Separate with commas. Example: --partial, --checksum, --inplace",

    hardLinks:
        "Preserve hard links (-H). Can increase memory usage on large trees.",

    xattr:
        "Preserve extended attributes (-X). Useful for ACLs/metadata when supported.",

    perms:
        "Preserve permissions (-p).",

    bw:
        "Limit bandwidth in KBytes per second (--bwlimit). Use 0 for unlimited.",

    parallel:
        "Splits directory work across multiple rsync processes to improve throughput. " +
        "Only valid when the source is a directory-style path (ends with /).",

    parallelDisabled:
        "Parallel mode requires a directory source path ending with /. Disable or add a trailing slash.",

    parallelThreads:
        "Number of parallel workers. Higher can be faster but uses more CPU, disk, and network."
} as const;

async function handleTestSSH() {
    testingSSH.value = true;
    try {
        const res = await testOrSetupSSH({
            host: destHost.value,
            user: destUser.value || 'root',
            port: destPort.value || 22,
            passwordRef: destUserPass,
            onEvent: ({ type, title, message }) => {
                pushNotification(new Notification(title, message, type, type === 'info' ? 6000 : 6000));
            }
        });
        sshReady.value = res.success;
    } finally {
        testingSSH.value = false;
    }
}

const ctx = useClientContextStore();
const allowContextFallback = ref(false);

function parseFromHash(): string {
    const m = (window.location.hash || '').match(/[?&]client_id=([^&#]+)/);
    return m ? decodeURIComponent(m[1]) : '';
}

const installId = computed(() => {
    const fromHash = parseFromHash();
    return fromHash || (allowContextFallback.value ? (ctx.clientId || '') : '');
});

const folderList = useUserScopedFolderListByInstall(installId, 2);

watchEffect(() => {
    console.log('[folderList state]',
        'loading=', folderList.loading.value,
        'error=', folderList.error.value,
        'shareRoot=', folderList.shareRoot.value,
        'smbUser=', folderList.smbUser.value,
        'uuids=', folderList.uuids.value,
        'abs=', folderList.absDirs.value.length
    );
});

const loadingFolders = folderList.loading;
const discoveryError = folderList.error;
const shareRoot = computed(() => folderList.shareRoot.value);
const smbUser = computed(() => folderList.smbUser.value);
const isEditMode = computed(() => !!props.task);

function prettyLabelFromAbs(abs: string) {
    const root = shareRoot.value || '';
    if (!abs.startsWith(root)) return abs;
    const rel = abs.slice(root.length).replace(/^\/+/, '');
    const parts = rel.split('/').filter(Boolean);
    return parts.length >= 2 ? parts.slice(1).join('/') + '/' : rel + '/';
}

const opts = computed<Array<{ value: string; label: string }>>(() =>
    (folderList.absDirs.value ?? []).map(abs => ({
        value: abs,
        label: prettyLabelFromAbs(abs),
    }))
);

watch(opts, (list) => {
    if (!props.simple || isEditMode.value) return;
    if (!list.length) return;
    if (!sourcePath.value || !folderList.underRoot(sourcePath.value)) {
        sourcePath.value = list[0].value;
    }
}, { immediate: true });

watch([() => folderList.absDirs.value, () => folderList.shareRoot.value], ([abs]) => {
    if (!props.simple || isEditMode.value) return;
    const list = abs || [];
    if (!list.length) return;
    if (!sourcePath.value || !folderList.underRoot(sourcePath.value)) {
        sourcePath.value = list[0];
    }
}, { immediate: true });

const togglePassword = () => {
    showPassword.value = !showPassword.value;
};

const parallelDisabled = computed(() => {
    if (!isParallel.value) return false;
    return !sourcePath.value || !sourcePath.value.endsWith('/');
});

watch(parallelDisabled, (disabled) => {
    if (disabled) {
        isParallel.value = false;
        parallelThreads.value = 0;
        errorList.value.push('Parallel mode requires the source to be a directory path ending with /.');
    }
});

async function initializeData() {
    if (props.task) {
        loading.value = true;
        const params = props.task.parameters.children;

        sourcePath.value = params.find(p => p.key === 'local_path')!.value;

        const targetInfoParams = params.find(p => p.key === 'target_info')!.children;
        destPath.value = targetInfoParams.find(p => p.key === 'path')!.value;
        destHost.value = targetInfoParams.find(p => p.key === 'host')!.value;
        destUser.value = targetInfoParams.find(p => p.key === 'user')!.value;
        destRoot.value = targetInfoParams.find(p => p.key === 'root')!.value;
        destPort.value = targetInfoParams.find(p => p.key === 'port')!.value;

        const transferDirection = params.find(p => p.key === 'direction')!.value;
        directionSwitched.value = transferDirection === 'pull';

        const rsyncOptions = params.find(p => p.key === 'rsyncOptions')!.children;

        const logFileParam = rsyncOptions.find(p => p.key === 'log_file_path');
        logFilePath.value = logFileParam ? logFileParam.value : '';

        isArchive.value = rsyncOptions.find(p => p.key === 'archive_flag')!.value;
        isRecursive.value = rsyncOptions.find(p => p.key === 'recursive_flag')!.value;
        isCompressed.value = rsyncOptions.find(p => p.key === 'compressed_flag')!.value;
        isQuiet.value = rsyncOptions.find(p => p.key === 'quiet_flag')!.value;
        deleteFiles.value = rsyncOptions.find(p => p.key === 'delete_flag')!.value;
        preserveTimes.value = rsyncOptions.find(p => p.key === 'times_flag')!.value;
        preserveHardLinks.value = rsyncOptions.find(p => p.key === 'hardLinks_flag')!.value;
        preservePerms.value = rsyncOptions.find(p => p.key === 'permissions_flag')!.value;
        preserveXattr.value = rsyncOptions.find(p => p.key === 'xattr_flag')!.value;

        const bw = rsyncOptions.find(p => p.key === 'bandwidth_limit_kbps')!.value;
        limitBandwidthKbps.value = parseInt(bw) === 0 ? 0 : bw;

        includePattern.value = rsyncOptions.find(p => p.key === 'include_pattern')!.value.replace(/^'|'$/g, '');
        excludePattern.value = rsyncOptions.find(p => p.key === 'exclude_pattern')!.value.replace(/^'|'$/g, '');
        extraUserParams.value = rsyncOptions.find(p => p.key === 'custom_args')!.value.replace(/^'|'$/g, '');

        isParallel.value = rsyncOptions.find(p => p.key === 'parallel_flag')!.value;
        parallelThreads.value = rsyncOptions.find(p => p.key === 'parallel_threads')!.value;

        initialParameters.value = JSON.parse(JSON.stringify({
            sourcePath: sourcePath.value,
            destPath: destPath.value,
            destHost: destHost.value,
            destUser: destUser.value,
            destRoot: destRoot.value,
            destPort: destPort.value,
            directionSwitched: directionSwitched.value,
            isArchive: isArchive.value,
            isRecursive: isRecursive.value,
            isCompressed: isCompressed.value,
            isQuiet: isQuiet.value,
            deleteFiles: deleteFiles.value,
            preserveTimes: preserveTimes.value,
            preserveHardLinks: preserveHardLinks.value,
            preservePerms: preservePerms.value,
            preserveXattr: preserveXattr.value,
            limitBandwidthKbps: limitBandwidthKbps.value,
            includePattern: includePattern.value,
            excludePattern: excludePattern.value,
            extraUserParams: extraUserParams.value,
            isParallel: isParallel.value,
            parallelThreads: parallelThreads.value,
            logFilePath: logFilePath.value
        }));

        loading.value = false;
    }
}

function hasChanges() {
    const currentParams = {
        sourcePath: sourcePath.value,
        destPath: destPath.value,
        destHost: destHost.value,
        destUser: destUser.value,
        destRoot: destRoot.value,
        destPort: destPort.value,
        directionSwitched: directionSwitched.value,
        isArchive: isArchive.value,
        isRecursive: isRecursive.value,
        isCompressed: isCompressed.value,
        isQuiet: isQuiet.value,
        deleteFiles: deleteFiles.value,
        preserveTimes: preserveTimes.value,
        preserveHardLinks: preserveHardLinks.value,
        preservePerms: preservePerms.value,
        preserveXattr: preserveXattr.value,
        limitBandwidthKbps: limitBandwidthKbps.value,
        includePattern: includePattern.value,
        excludePattern: excludePattern.value,
        extraUserParams: extraUserParams.value,
        isParallel: isParallel.value,
        parallelThreads: parallelThreads.value,
        logFilePath: logFilePath.value
    };

    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}

function validateHost() {
    destHostErrorTag.value = false;

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

function validatePath(path: string): boolean {
    return validateLocalPath(path);
}

function validateSourcePath() {
    if (validatePath(sourcePath.value)) {
        if (props.simple && sourcePath.value && !sourcePath.value.endsWith('/')) {
            errorList.value.push("In Simple mode, source must be a folder path ending with '/'.");
            sourcePathErrorTag.value = true;
            return false;
        }
        return true;
    } else {
        errorList.value.push("Source path is invalid.");
        sourcePathErrorTag.value = true;
        return false;
    }
}

function validateDestinationPath() {
    if (validatePath(destPath.value)) {
        return true;
    } else {
        errorList.value.push("Target path is invalid.");
        destPathErrorTag.value = true;
        return false;
    }
}

function validateDependantParams() {
    if (deleteFiles.value && !(isArchive.value || isRecursive.value)) {
        errorList.value.push("Delete Files requires either Archive or Recursive to be selected.");
        isDeleteErrorTag.value = true;
        return false;
    }
    isDeleteErrorTag.value = false;

    if (isParallel.value && (!sourcePath.value || !sourcePath.value.endsWith('/'))) {
        errorList.value.push("Parallel mode requires the source to be a directory path ending with '/'.");
        return false;
    }

    return true;
}

function sanitizeNumber(value: number): number {
    if (isNaN(value) || value < 0) {
        return 0;
    }
    return value;
}

function clearErrorTags() {
    sourcePathErrorTag.value = false;
    destPathErrorTag.value = false;
    destHostErrorTag.value = false;
    isDeleteErrorTag.value = false;
    errorList.value = [];
}

async function validateParams() {
    clearErrorTags();

    validateSourcePath();
    validateHost();
    validateDestinationPath();
    validateDependantParams();

    limitBandwidthKbps.value = sanitizeNumber(limitBandwidthKbps.value);

    const noErrors =
        errorList.value.length === 0 &&
        sourcePathErrorTag.value === false &&
        destPathErrorTag.value === false &&
        destHostErrorTag.value === false &&
        isDeleteErrorTag.value === false;

    if (noErrors) {
        setParams();
    }
}

function setParams() {
    const directionPUSH = new SelectionOption('push', 'Push');
    const directionPULL = new SelectionOption('pull', 'Pull');

    const transferDirection = ref<SelectionOption>();
    transferDirection.value = directionSwitched.value ? directionPULL : directionPUSH;

    const newParams = new ParameterNode("Rsync Task Config", "rsyncConfig")
        .addChild(new StringParameter('Local Path', 'local_path', sourcePath.value))
        .addChild(
            new LocationParameter(
                'Target Information',
                'target_info',
                destHost.value,
                destPort.value,
                destUser.value,
                destRoot.value,
                destPath.value
            )
        )
        .addChild(new SelectionParameter('Direction', 'direction', transferDirection.value.value))
        .addChild(
            new ParameterNode('Rsync Options', 'rsyncOptions')
                .addChild(new StringParameter('Log File Path', 'log_file_path', logFilePath.value))
                .addChild(new BoolParameter('Archive', 'archive_flag', isArchive.value))
                .addChild(new BoolParameter('Recursive', 'recursive_flag', isRecursive.value))
                .addChild(new BoolParameter('Compressed', 'compressed_flag', isCompressed.value))
                .addChild(new BoolParameter('Delete', 'delete_flag', deleteFiles.value))
                .addChild(new BoolParameter('Quiet', 'quiet_flag', isQuiet.value))
                .addChild(new BoolParameter('Preserve Times', 'times_flag', preserveTimes.value))
                .addChild(new BoolParameter('Preserve Hard Links', 'hardLinks_flag', preserveHardLinks.value))
                .addChild(new BoolParameter('Preserve Permissions', 'permissions_flag', preservePerms.value))
                .addChild(new BoolParameter('Preserve Extended Attributes', 'xattr_flag', preserveXattr.value))
                .addChild(new IntParameter('Limit Bandwidth', 'bandwidth_limit_kbps', limitBandwidthKbps.value))
                .addChild(new StringParameter('Include', 'include_pattern', `'${includePattern.value}'`))
                .addChild(new StringParameter('Exclude', 'exclude_pattern', `'${excludePattern.value}'`))
                .addChild(new BoolParameter('Parallel Transfer', 'parallel_flag', isParallel.value))
                .addChild(new IntParameter('Threads', 'parallel_threads', parallelThreads.value))
                .addChild(new StringParameter('Additional Custom Arguments', 'custom_args', `'${extraUserParams.value}'`))
        );

    parameters.value = newParams;
}

async function confirmTest(destHostVal: string, destUserVal: string) {
    testingSSH.value = true;

    const sshTarget = destUserVal + '@' + destHostVal;
    sshTestResult.value = await testSSH(sshTarget);

    if (sshTestResult.value) {
        pushNotification(
            new Notification(
                'Connection Successful!',
                'Passwordless SSH connection established. This host can be used for remote transfers.',
                'success',
                6000
            )
        );
    } else {
        pushNotification(
            new Notification(
                'Connection Failed',
                `Could not resolve hostname "${destHostVal}":
Name or service not known.
Make sure passwordless SSH connection has been configured for target system.`,
                'error',
                6000
            )
        );
    }
    testingSSH.value = false;
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
