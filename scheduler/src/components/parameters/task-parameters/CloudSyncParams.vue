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
                        <!-- <InfoTile class="ml-1" title="" /> -->
                        <img v-if="selectedRemote" :src="getProviderLogo(undefined, selectedRemote)" alt="provider-logo"
                            class="inline-block w-5 h-5 ml-2" />
                    </label>
                    <ExclamationCircleIcon v-if="errorTags.selectedRemote" class="mt-1 w-5 h-5 text-danger" />
                </div>
                <select v-if="existingRemotes.length > 0" id="existing-remote-selection" v-model="selectedRemote"
                    name="existing-remote-selection"
                    :class="[errorTags.selectedRemote ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                    class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6 col-span-1">
                    <option :value="undefined">Select Remote</option>
                    <option v-for="remote, idx in existingRemotes" :key="idx" :value="remote">
                        {{ remote.name }}
                    </option>
                </select>
                <select v-else disabled id="existing-remote-selection" v-model="selectedRemote"
                    name="existing-remote-selection"
                    class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6 col-span-1">
                    <option :value="undefined">No Remotes Found</option>
                </select>
                <div class="col-span-1 button-group-row mt-0.5">
                    <button @click.stop="createRemoteBtn()" id="new-remote-btn" name="new-remote-btn"
                        class="mt-1 btn btn-primary h-fit w-full" :class=truncateText>
                        Create New
                    </button>
                    <button v-if="existingRemotes.length > 0" @click.stop="manageRemotesBtn()" id="manage-remotes-btn"
                        name="manage-remotes-btn" class="mt-1 btn btn-secondary h-fit w-full" :class=truncateText>
                        Manage Existing
                    </button>
                    <button v-else disabled @click.stop="manageRemotesBtn()" id="manage-remotes-btn"
                        name="manage-remotes-btn" class="mt-1 btn btn-secondary h-fit w-full" :class=truncateText>
                        Manage Existing
                    </button>
                </div>
                <!-- <div class="mt-1 col-span-2 button-group-row">
                    <button v-if="!selectedRemote"
                        class="mt-1 btn h-fit w-full col-span-2 btn btn-secondary text-default" disabled>
                        No Remote Selected
                    </button> -->

                    <!-- <button v-if="selectedRemote" @click.stop="authenticateRemoteBtn(selectedRemote)"
                        @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave"
                        class="mt-1 flex items-center justify-between h-fit w-full col-span-2 btn btn-secondary text-default"
                        :style="getButtonStyles(isHovered, undefined, selectedRemote)">
                        <span class="flex-grow text-center">
                            Authenticate {{ selectedRemote.name }}
                        </span>
                        <div class="flex items-center justify-center h-6 w-6 bg-white rounded-full ml-2">
                            <img :src="getProviderLogo(undefined, selectedRemote)" alt="provider-logo"
                                class="inline-block w-4 h-4" />
                        </div>
                    </button> -->
                <!--     
                    <button v-if="selectedRemote && selectedRemote.provider.providerParams.oAuthSupported!" @click.stop="refreshRemoteTokenBtn(selectedRemote)"
                        @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave"
                        class="mt-1 flex items-center justify-between h-fit w-full col-span-2 btn btn-secondary text-default"
                        :style="getButtonStyles(isHovered, undefined, selectedRemote)">
                        <span class="flex-grow text-center">
                            Refresh {{ selectedRemote.name }} Token
                        </span>
                        <div class="flex items-center justify-center h-6 w-6 bg-white rounded-full ml-2">
                            <img :src="getProviderLogo(undefined, selectedRemote)" alt="provider-logo"
                                class="inline-block w-4 h-4" />
                        </div>
                    </button>
                </div> -->
            </div>

            <div name="transfer-config" class="grid grid-cols-2 col-span-2 gap-x-2">
                <div name="transfer-type" class="col-span-1 mt-1.5">
                    <div class="flex flex-row justify-between items-center">
                        <label class="block text-sm leading-6 text-default">
                            Transfer Type
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <ExclamationCircleIcon v-if="errorTags.transferType" class="mt-1 w-5 h-5 text-danger" />
                    </div>
                    <div class="">
                        <select id="existing-remote-selection" v-model="transferType" name="existing-remote-selection"
                            :class="[errorTags.transferType ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
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
                            <span class="text-default">Cloud Remote</span>
                        </div>
                    </div>
                </div>
            </div>
            <div name="directory-config" class="grid grid-cols-2 col-span-2 gap-x-2">
                <div name="source-path">
                    <div class="flex flex-row justify-between items-center">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Local Path
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <ExclamationCircleIcon v-if="errorTags.localPath" class="mt-1 w-5 h-5 text-danger" />
                    </div>
                    <div>
                        <input type="text" v-model="localPath"
                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                            :class="[errorTags.localPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                            placeholder="Specify Local Path" />
                    </div>
                </div>
                <div name="destination-path">
                    <div class="flex flex-row justify-between items-center">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Target Path
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <ExclamationCircleIcon v-if="errorTags.targetPath" class="mt-1 w-5 h-5 text-danger" />
                    </div>
                    <div>
                        <input type="text" v-model="targetPath"
                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                            :class="[errorTags.targetPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                            placeholder="Specify Target Path" />
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
            <div class="grid grid-cols-4 gap-4 mt-2">
                <div class="col-span-1">
                    <div name="options-check-first"
                        class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                        <label class="text-sm leading-6 text-default"
                            title="Do all the checks before starting transfers">
                            Check First
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <input type="checkbox" v-model="checkFirst" class="ml-2 h-4 w-4 rounded" />
                    </div>
                    <div name="options-checksum"
                        class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                        <label class="text-sm leading-6 text-default" title="Check for changes with size & checksum">
                            Checksum
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <input type="checkbox" v-model="checksum" class="ml-2 h-4 w-4 rounded" />
                    </div>
                    <div name="options-update" title=""
                        class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Update
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <input type="checkbox" v-model="update" class=" h-4 w-4 rounded" />
                    </div>
                    <div name="options-ignore-existing"
                        class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                        <label class="text-sm leading-6 text-default" title="Skip all files that exist on destination">
                            Ignore Existing
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <input type="checkbox" v-model="ignoreExisting" class="ml-2 h-4 w-4 rounded" />
                    </div>
                    <div name="options-dry-run" title=""
                        class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                        <label class="block text-sm leading-6 text-default mt-0.5">
                            Dry Run
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <input type="checkbox" v-model="dryRun" class=" h-4 w-4 rounded" />
                    </div>

                </div>

                <div class="-mt-1 col-span-3 grid grid-cols-2 gap-2">
                    <div class="grid grid-cols-2 col-span-2 gap-2 w-full justify-center items-center text-center">
                        <div name="options-include" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="mt-1 block text-sm leading-6 text-default">
                                    Include Pattern
                                    <InfoTile class="ml-1"
                                        title="Pattern applying to specific directories/files to include. Separate patterns with commas (,)." />
                                </label>
                                <ExclamationCircleIcon v-if="errorTags.includePattern"
                                    class="mt-1 w-5 h-5 text-danger" />
                            </div>
                            <input type="text" v-model="includePattern"
                                :class="[errorTags.includePattern ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Eg. */, *.txt" />
                        </div>
                        <div name="options-exclude" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="mt-1 block text-sm leading-6 text-default">
                                    Exclude Pattern
                                    <InfoTile class="ml-1"
                                        title="Pattern applying to specific directories/files to exclude. Separate patterns with commas (,)." />
                                </label>
                                <ExclamationCircleIcon v-if="errorTags.excludePattern"
                                    class="mt-1 w-5 h-5 text-danger" />
                            </div>
                            <input type="text" v-model="excludePattern"
                                :class="[errorTags.excludePattern ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Eg. */, *.txt" />
                        </div>
                    </div>

                    <div name="options-parallel-threads" class="col-span-1">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Number of Transfers
                            <InfoTile class="ml-1" title="" />
                        </label>
                        <ExclamationCircleIcon v-if="errorTags.numberOfTransfers" class="mt-1 w-5 h-5 text-danger" />
                        <input type="number" min='0' v-model="numberOfTransfers"
                            :class="[errorTags.numberOfTransfers ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                            placeholder="Default is 1" />
                    </div>
                    <div name="options-extra-params" class="col-span-1">
                        <div class="flex flex-row justify-between items-center">
                            <label class="block text-sm leading-6 text-default">
                                Extra Parameters
                                <InfoTile class="ml-1"
                                    title="Separate any extra parameters, flags or options you wish to include with commas (,)." />
                            </label>
                            <ExclamationCircleIcon v-if="errorTags.customArgs" class="mt-1 w-5 h-5 text-danger" />
                        </div>
                        <textarea v-model="customArgs" rows="1"
                            :class="[errorTags.customArgs ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                            placeholder="Eg. -I, --ignore-checksum, etc." />
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
                            <div class="w-full grid grid-cols-4 gap-4 bg-default p-3 -mt-1">
                                <div class="col-span-1 grid grid-cols-1 px-1 -mt-1">
                                    <div name="options-ignore-size" title=""
                                        class="flex flex-row justify-between items-center col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            Ignore Size
                                            <InfoTile class="ml-1" title="" />
                                        </label>
                                        <input type="checkbox" v-model="ignoreSize" class=" h-4 w-4 rounded" />
                                    </div>
                                    <div name="options-inplace" title=""
                                        class="flex flex-row justify-between items-center col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            Inplace
                                            <InfoTile class="ml-1" title="" />
                                        </label>
                                        <input type="checkbox" v-model="inplace" class=" h-4 w-4 rounded" />
                                    </div>
                                    <div name="options-no-traverse" title=""
                                        class="flex flex-row justify-between items-center col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            No Traverse
                                            <InfoTile class="ml-1" title="" />
                                        </label>
                                        <input type="checkbox" v-model="noTraverse" class=" h-4 w-4 rounded" />
                                    </div>
                                    <div name="options-preserve-metadata" title=""
                                        class="flex flex-row justify-between items-center col-span-1 col-start-1">
                                        <label class="block text-sm leading-6 text-default mt-0.5">
                                            Preserve Metadata
                                            <InfoTile class="ml-1" title="" />
                                        </label>
                                        <input type="checkbox" v-model="preserveMetadata" class=" h-4 w-4 rounded" />
                                    </div>
                                </div>

                                <div class="col-span-3 grid grid-cols-3 grid-rows-2 gap-2">
                                    <div name="options-limit-bw" class="col-span-1">
                                        <label class="mt-1 text-sm leading-6 text-default">
                                            Limit Bandwidth (Kbps)
                                            <InfoTile class="ml-1" title="Limit I/O bandwidth; KBytes per second" />
                                        </label>
                                        <ExclamationCircleIcon v-if="errorTags.limitBandwidthKbps"
                                            class="mt-1 w-5 h-5 text-danger" />
                                        <input type="number" min='0' v-model="limitBandwidthKbps"
                                            :class="[errorTags.limitBandwidthKbps ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                            placeholder="Default is None" />
                                    </div>


                                    <div name="options-cutoff-mode" class="col-span-1">
                                        <label class="mt-1 text-sm leading-6 text-default">
                                            Cutoff Mode
                                            <InfoTile class="ml-1"
                                                title="Mode to stop transfers when reaching max transfer limit (Default is HARD)" />
                                        </label>
                                        <select v-model="cutoffMode"
                                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default">
                                            <option value=undefined>Select Mode</option>
                                            <option value="HARD">HARD</option>
                                            <option value="SOFT">SOFT</option>
                                            <option value="CAUTIOUS">CAUTIOUS</option>
                                        </select>
                                    </div>

                                    <div name="options-limit-bw" class="col-span-1">
                                        <label class="mt-1 text-sm leading-6 text-default">
                                            Max Transfer Size
                                            <InfoTile class="ml-1"
                                                title="Sets a cap on transfer size. Default is None" />
                                        </label>
                                        <ExclamationCircleIcon v-if="errorTags.maxTransferSize"
                                            class="mt-1 w-5 h-5 text-danger" />
                                        <div class="flex items-center">
                                            <input type="number" min='0' v-model="maxTransferSize"
                                                :class="[errorTags.maxTransferSize ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="" />
                                            <select v-model="maxTransferSizeUnit"
                                                class="mt-1 block text-default input-textlike sm:text-sm sm:leading-6 bg-default">
                                                <option value="B">B</option>
                                                <option value="KiB">KiB</option>
                                                <option value="MiB">MiB</option>
                                                <option value="GiB">GiB</option>
                                                <option value="TiB">TiB</option>
                                                <option value="PiB">PiB</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div
                                        class="col-span-3 row-start-2 grid grid-cols-2 gap-2 w-full justify-center items-center text-center">
                                        <div name="options-include-files-from-path" class="col-span-1">
                                            <div class="flex flex-row justify-between items-center">
                                                <label class="mt-1 block text-sm leading-6 text-default">
                                                    Include Files from Path
                                                    <InfoTile class="ml-1"
                                                        title="Reads file paths or patterns to include from an external file." />
                                                </label>
                                                <ExclamationCircleIcon v-if="errorTags.includeFromPath"
                                                    class="mt-1 w-5 h-5 text-danger" />
                                            </div>
                                            <input type="text" v-model="includeFromPath"
                                                :class="[errorTags.includeFromPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="Eg. '/path/to/included_file_paths.txt'" />
                                        </div>
                                        <div name="options-exclude-files-from-path" class="col-span-1">
                                            <div class="flex flex-row justify-between items-center">
                                                <label class="mt-1 block text-sm leading-6 text-default">
                                                    Exclude Files from Path
                                                    <InfoTile class="ml-1"
                                                        title="Reads file paths or patterns to exclude from an external file." />
                                                </label>
                                                <ExclamationCircleIcon v-if="errorTags.excludeFromPath"
                                                    class="mt-1 w-5 h-5 text-danger" />
                                            </div>
                                            <input type="text" v-model="excludeFromPath"
                                                :class="[errorTags.excludeFromPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="Eg. '/path/to/excluded_files.txt'" />
                                        </div>
                                    </div>
                                </div>


                                <div name="multi-thread-options"
                                    class="col-span-4 grid grid-cols-2 gap-1 border border-default rounded-md p-2 bg-accent">
                                    <label class="w-fit col-span-2 mt-1 block text-base leading-6 text-default items-center">
                                        Use Multiple Threads
                                        <input type="checkbox" v-model="multiThreadOptions"
                                            class="ml-4 mb-0.5 h-4 w-4 rounded" />
                                    </label>

                                    <div name="options-multi-thread-chunk-size">
                                        <div class="flex flex-row items-center justify-between mt-1">
                                            <label class="block text-sm leading-6 text-default"
                                                title="Chunk size for multi-thread downloads/uploads. Default is 64MiB">
                                                Chunk Size
                                                <InfoTile class="ml-1" title="" />
                                            </label>
                                            <ExclamationCircleIcon v-if="errorTags.multiThreadChunkSize"
                                                class="ml-1 w-5 h-5 text-danger" />
                                        </div>
                                        <div class="flex items-center">
                                            <input type="number" min="0" v-model="multiThreadChunkSize"
                                                :disabled="!multiThreadOptions"
                                                :class="[errorTags.multiThreadChunkSize ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="Default is 64 MiB" />
                                            <select v-model="multiThreadChunkSizeUnit" :disabled="!multiThreadOptions"
                                                class="mt-1 ml-1 block text-default input-textlike sm:text-sm sm:leading-6 bg-default">
                                                <option value="B">B</option>
                                                <option value="KiB">KiB</option>
                                                <option value="MiB">MiB</option>
                                                <option value="GiB">GiB</option>
                                                <option value="TiB">TiB</option>
                                                <option value="PiB">PiB</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div name="options-multi-thread-cutoff">
                                        <div class="flex flex-row items-center justify-between mt-1">
                                            <label class="block text-sm leading-6 text-default "
                                                title="Use multi-thread downloads for files above this size. Default is 256MiB">
                                                Cutoff Size
                                                <InfoTile class="ml-1" title="" />
                                            </label>
                                            <ExclamationCircleIcon v-if="errorTags.multiThreadCutoff"
                                                class="mt-1 w-5 h-5 text-danger" />
                                        </div>
                                        <div class="flex items-center">
                                            <input type="number" min='0' v-model="multiThreadCutoff"
                                                :disabled="!multiThreadOptions"
                                                :class="[errorTags.multiThreadCutoff ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="Default is 256 MiB" />
                                            <select v-model="multiThreadCutoffUnit" :disabled="!multiThreadOptions"
                                                class="mt-1 ml-1 block text-default input-textlike sm:text-sm sm:leading-6 bg-default">
                                                <option value="B">B</option>
                                                <option value="KiB">KiB</option>
                                                <option value="MiB">MiB</option>
                                                <option value="GiB">GiB</option>
                                                <option value="TiB">TiB</option>
                                                <option value="PiB">PiB</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div name="options-multi-thread-streams">
                                        <div class="flex flex-row items-center justify-between mt-1">
                                            <label class="block text-sm leading-6 text-default"
                                                title="Number of streams to use for multi-thread downloads. Default is 4">
                                                Number of Streams
                                                <InfoTile class="ml-1" title="" />
                                            </label>
                                            <ExclamationCircleIcon v-if="errorTags.multiThreadStreams"
                                                class="mt-1 w-5 h-5 text-danger" />
                                        </div>

                                        <input type="number" v-model="multiThreadStreams" min="1"
                                            :disabled="!multiThreadOptions"
                                            :class="[errorTags.multiThreadStreams ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                            class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                            placeholder="Default is 4 Streams" />
                                    </div>

                                    <div name="options-multi-thread-write-buffer-size">
                                        <div class="flex flex-row items-center justify-between mt-1">
                                            <label class="block text-sm leading-6 text-default"
                                                :disabled="!multiThreadOptions"
                                                title="In-memory buffer size for writing in multi-thread mode. Default is 128KiB">
                                                Write Buffer Size
                                                <InfoTile class="ml-1" title="" />
                                            </label>
                                            <ExclamationCircleIcon v-if="errorTags.multiThreadWriteBufferSize"
                                                class="mt-1 w-5 h-5 text-danger" />
                                        </div>
                                        <div class="flex items-center">
                                            <input type="number" min='0' v-model="multiThreadWriteBufferSize"
                                                :disabled="!multiThreadOptions"
                                                :class="[errorTags.multiThreadWriteBufferSize ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="Default is 128 KiB" />
                                            <select v-model="multiThreadWriteBufferSizeUnit"
                                                :disabled="!multiThreadOptions"
                                                class="mt-1 ml-1 block text-default input-textlike sm:text-sm sm:leading-6 bg-default">
                                                <option value="B">B</option>
                                                <option value="KiB">KiB</option>
                                                <option value="MiB">MiB</option>
                                                <option value="GiB">GiB</option>
                                                <option value="TiB">TiB</option>
                                                <option value="PiB">PiB</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>

                            </div>
                        </DisclosurePanel>
                    </Disclosure>
                </div>
            </div>
        </div>
    </div>

    <div v-if="showCreateRemote">
        <component :is="createRemoteComponent" :id-key="'create-remote-modal'" />
    </div>

    <div v-if="showManageRemotes">
        <component :is="manageRemotesComponent" :id-key="'manage-remotes-modal'" />
    </div>
</template>

<script setup lang="ts">
import { ref, Ref, onMounted, inject, provide, watch } from 'vue';
import { Disclosure, DisclosureButton, DisclosurePanel, Switch } from '@headlessui/vue';
import { ExclamationCircleIcon, ChevronDoubleRightIcon, ChevronUpIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, IntParameter, StringParameter, BoolParameter, SelectionParameter, SelectionOption } from '../../../models/Parameters';
import { CloudSyncRemote, getProviderLogo, getButtonStyles, CloudSyncProvider, CloudAuthParameter, cloudSyncProviders } from '../../../models/CloudSync';
import { injectWithCheck, checkLocalPathExists } from '../../../composables/utility';
import { rcloneRemotesInjectionKey, truncateTextInjectionKey } from '../../../keys/injection-keys';

interface CloudSyncParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
}

const props = defineProps<CloudSyncParamsProps>();
const loading = ref(false);
const truncateText = injectWithCheck(truncateTextInjectionKey, "truncateText not provided!");
const parameters = inject<Ref<any>>('parameters')!;

const initialParameters = ref({});

// Create dummy CloudSyncRemote instance for dev
// const dummyDropboxProvider: CloudSyncProvider = cloudSyncProviders["dropbox"];
// const dummyDropboxAuthParams: CloudAuthParameter = {
//     parameters: {
//         token: { value: "", type: "object", defaultValue: "" },
//         client_id: { value: "dropbox-client-id", type: "string", defaultValue: "" },
//         client_secret: { value: "dropbox-client-secret", type: "string", defaultValue: "" },
//     },
//     oAuthSupported: true,
// };
// const dummyCloudSyncRemote = new CloudSyncRemote(
//     "dummyRemote",          // Name of the remote
//     "dropbox",              // Type of remote, matching the provider type
//     dummyDropboxAuthParams,      // Authentication parameters for Dropbox
//     dummyDropboxProvider         // The Dropbox provider instance
// );
// const dummyRemote = ref(dummyCloudSyncRemote);

const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, "remotes not provided!");
const errorList = inject<Ref<string[]>>('errors')!;
const errorTags = ref({
    localPath: false,
    targetPath: false,
    selectedRemote: false,
    transferType: false,
    numberOfTransfers: false,
    includePattern: false,
    excludePattern: false,
    customArgs: false, 
    limitBandwidthKbps: false,
    includeFromPath: false, 
    excludeFromPath: false, 
    maxTransferSize: false,
    cutoffMode: false, 
    multiThreadChunkSize: false,
    multiThreadCutoff: false,
    multiThreadStreams: false,
    multiThreadWriteBufferSize: false,
});

const localPath = ref('');
const targetPath = ref('');
const directionSwitched = ref(false)
const transferType = ref(undefined);
const selectedRemote = ref<CloudSyncRemote>();
const checkFirst = ref(false);
const checksum = ref(false);
const update = ref(false);
const ignoreExisting = ref(false);
const dryRun = ref(false);
const numberOfTransfers = ref();
const includePattern = ref('');
const excludePattern = ref('');
const customArgs = ref('');

const limitBandwidthKbps = ref()
const ignoreSize = ref(false);
const inplace = ref(false);
const multiThreadOptions = ref(false);
const multiThreadChunkSize = ref();
const multiThreadChunkSizeUnit = ref('MiB');
const multiThreadCutoff = ref();
const multiThreadCutoffUnit = ref('MiB');
const multiThreadStreams = ref();
const multiThreadWriteBufferSize = ref();
const multiThreadWriteBufferSizeUnit = ref('KiB');
const includeFromPath = ref('');
const excludeFromPath = ref('');
const maxTransferSize = ref(0);
const maxTransferSizeUnit = ref('MiB');
const cutoffMode = ref();
const noTraverse = ref(false);
const preserveMetadata = ref(false);

onMounted(async () => {
    //for development only
    // if (existingRemotes.value.length < 1) {
    //     existingRemotes.value.push(dummyRemote.value);
    // }

    await initializeData();
    console.log("Existing remotes:", existingRemotes);
});


async function initializeData() {
    if (props.task) {
        loading.value = true;

        const params = props.task.parameters.children;
        localPath.value = params.find(p => p.key === 'local_path')!.value;
        targetPath.value = params.find(p => p.key === 'target_path')!.value;

        const transferDirection = params.find(p => p.key === 'direction')!.value;
        if (transferDirection == 'pull') {
            directionSwitched.value = true;
        } else {
            directionSwitched.value = false;
        }
        transferType.value = params.find(p => p.key === 'type')!.value;
        selectedRemote.value = params.find(p => p.key === 'cloud_sync_remote')!.value;

        const rcloneOptions = params.find(p => p.key === 'rcloneOptions')!.value;
        checkFirst.value = rcloneOptions.find(p => p.key === '')!.value;
        checksum.value = rcloneOptions.find(p => p.key === '')!.value;
        update.value = rcloneOptions.find(p => p.key === '')!.value;
        ignoreExisting.value = rcloneOptions.find(p => p.key === '')!.value;
        dryRun.value = rcloneOptions.find(p => p.key === '')!.value;
        numberOfTransfers.value = rcloneOptions.find(p => p.key === '')!.value;
        includePattern.value = rcloneOptions.find(p => p.key === '')!.value;
        excludePattern.value = rcloneOptions.find(p => p.key === '')!.value;
        customArgs.value = rcloneOptions.find(p => p.key === '')!.value;

        limitBandwidthKbps.value = rcloneOptions.find(p => p.key === '')!.value;
        ignoreSize.value = rcloneOptions.find(p => p.key === '')!.value;
        inplace.value = rcloneOptions.find(p => p.key === '')!.value;
        
        multiThreadChunkSize.value = rcloneOptions.find(p => p.key === 'multithread_chunk_size')!.value;
        multiThreadChunkSizeUnit.value = rcloneOptions.find(p => p.key === 'multithread_chunk_size_unit')!.value;
        multiThreadCutoff.value = rcloneOptions.find(p => p.key === 'multithread_cutoff')!.value;
        multiThreadCutoffUnit.value = rcloneOptions.find(p => p.key === 'multithread_cutoff_unit')!.value;
        multiThreadStreams.value = rcloneOptions.find(p => p.key === 'multithread_streams')!.value;
        multiThreadWriteBufferSize.value = rcloneOptions.find(p => p.key === 'multithread_write_buffer_size')!.value;
        multiThreadWriteBufferSizeUnit.value = rcloneOptions.find(p => p.key === 'multithread_write_buffer_size_unit')!.value;

        // Enable multiThreadOptions if any multi-thread-related parameter is non-default
        multiThreadOptions.value = (
            multiThreadChunkSize.value > 0 ||
            multiThreadCutoff.value > 0 ||
            multiThreadStreams.value > 0 ||
            multiThreadWriteBufferSize.value > 0
        );

        includeFromPath.value = rcloneOptions.find(p => p.key === 'include_from_path')!.value;
        excludeFromPath.value = rcloneOptions.find(p => p.key === 'exclude_from_path')!.value;
        maxTransferSize.value = rcloneOptions.find(p => p.key === 'max_transfer_size')!.value;
        maxTransferSizeUnit.value = rcloneOptions.find(p => p.key === 'max_transfer_size_unit')!.value;
        cutoffMode.value = rcloneOptions.find(p => p.key === 'cutoff_mode')!.value;
        noTraverse.value = rcloneOptions.find(p => p.key === 'no_traverse_flag')!.value;
        preserveMetadata.value = rcloneOptions.find(p => p.key === 'metadata_flag')!.value;

        initialParameters.value = JSON.parse(JSON.stringify({
            localPath: localPath.value,
            targetPath: targetPath.value,
            directionSwitched: directionSwitched.value,
            transferType: transferType.value,
            selectedRemote: selectedRemote.value,
            checkFirst: checkFirst.value,
            checksum: checksum.value,
            update: update.value,
            ignoreExisting: ignoreExisting.value,
            dryRun: dryRun.value,
            numberOfTransfers: numberOfTransfers.value,
            includePattern: includePattern.value,
            excludePattern: excludePattern.value,
            customArgs: customArgs.value,
            limitBandwidthKbps: limitBandwidthKbps.value,
            ignoreSize: ignoreSize.value,
            inplace: inplace.value,
            multiThreadChunkSize: multiThreadChunkSize.value,
            multiThreadCutoff: multiThreadCutoff.value,
            multiThreadStreams: multiThreadStreams.value,
            multiThreadWriteBufferSize: multiThreadWriteBufferSize.value,
            includeFromPath: includeFromPath.value,
            excludeFromPath: excludeFromPath.value,
            maxTransferSize: maxTransferSize.value,
            maxTransferSizeUnit: maxTransferSizeUnit.value,
            cutoffMode: cutoffMode.value,
            noTraverse: noTraverse.value,
            preserveMetadata: preserveMetadata.value,
        }));

        loading.value = false;
    }
}

function hasChanges() {
    const currentParams = {
        localPath: localPath.value,
        targetPath: targetPath.value,
        directionSwitched: directionSwitched.value,
        transferType: transferType.value,
        selectedRemote: selectedRemote.value,
        checkFirst: checkFirst.value,
        checksum: checksum.value,
        update: update.value,
        ignoreExisting: ignoreExisting.value,
        dryRun: dryRun.value,
        numberOfTransfers: numberOfTransfers.value,
        includePattern: includePattern.value,
        excludePattern: excludePattern.value,
        customArgs: customArgs.value,
        limitBandwidthKbps: limitBandwidthKbps.value,
        ignoreSize: ignoreSize.value,
        inplace: inplace.value,
        multiThreadChunkSize: multiThreadChunkSize.value,
        multiThreadCutoff: multiThreadCutoff.value,
        multiThreadStreams: multiThreadStreams.value,
        multiThreadWriteBufferSize: multiThreadWriteBufferSize.value,
        includeFromPath: includeFromPath.value,
        excludeFromPath: excludeFromPath.value,
        maxTransferSize: maxTransferSize.value,
        maxTransferSizeUnit: maxTransferSizeUnit.value,
        cutoffMode: cutoffMode.value,
        noTraverse: noTraverse.value,
        preserveMetadata: preserveMetadata.value,
    };

    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}


// Watch for changes in selectedRemote
watch(selectedRemote, (newVal) => {
    console.log("Selected remote changed:", newVal);  // Logs whenever selectedRemote changes
});

// const isHovered = ref(false);

// function handleMouseEnter() {
//     isHovered.value = true;
// }

// function handleMouseLeave() {
//     isHovered.value = false;
// }

// function authenticateRemoteBtn(selectedRemote: CloudSyncRemote) {

// }

// function refreshRemoteTokenBtn(selectedRemote: CloudSyncRemote) {

// }


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

const showManageRemotes = ref(false);
async function manageRemotesBtn() {
    await loadManageRemotesComponent();
    showManageRemotes.value = true;
}

const manageRemotesComponent = ref();
async function loadManageRemotesComponent() {
    const module = await import('../../modals/ManageRemotes.vue');
    manageRemotesComponent.value = module.default;
}


function validatePath(path) {
    // Regular expression to validate a UNIX-like file path
    const pathRegex = /^(\/[^/ ]*)+\/?$/;
    return pathRegex.test(path);
}

async function validateLocalPath() {
    if (!localPath.value) {
        errorList.value.push("Local path is required.");
        errorTags.value.localPath = true;
        return false;
    }
    if (await checkLocalPathExists(localPath.value) && validatePath(localPath.value)) {
        errorTags.value.localPath = false;
        console.log("Valid source path.");
        return true;
    } else {
        errorList.value.push("Source path is invalid.");
        errorTags.value.localPath = true;
        return false;
    }
}

function validateDestinationPath() {
    if (!targetPath.value) {
        errorList.value.push("Target path is required.");
        errorTags.value.targetPath = true;
        return false;
    }
    if (validatePath(targetPath.value)) {
        errorTags.value.targetPath = false;
        if (!targetPath.value.endsWith('/')) {
            targetPath.value += '/';
        }
        console.log("Valid destination path: " + targetPath.value);
        return true;
    } else {
        errorList.value.push("Target path is invalid.");
        errorTags.value.targetPath = true;
        return false;
    }
}

function validateAllValues() {
    if (!selectedRemote.value) {
        errorList.value.push("Remote is required.");
        errorTags.value.selectedRemote = true;
    }

    if (!transferType.value) {
        errorList.value.push("Transfer type is required.");
        errorTags.value.transferType = true;
    }

    validateLocalPath();
    validateDestinationPath();

    if (numberOfTransfers.value && typeof numberOfTransfers.value !== 'number' || numberOfTransfers.value < 0) {
        errorList.value.push("Number of Transfers must be a valid number.");
        errorTags.value.numberOfTransfers = true;
    }

    // Validate includePattern
    if (includePattern.value && typeof includePattern.value !== 'string') {
        errorList.value.push("Include Pattern must be a string.");
        errorTags.value.includePattern = true;
    }

    // Validate excludePattern
    if (excludePattern.value && typeof excludePattern.value !== 'string') {
        errorList.value.push("Exclude Pattern must be a string.");
        errorTags.value.excludePattern = true;
    }

    // Validate customArgs
    if (customArgs.value && typeof customArgs.value !== 'string') {
        errorList.value.push("Extra Parameters must be a string.");
        errorTags.value.customArgs = true;
    }

    // Validate limitBandwidthKbps
    if (limitBandwidthKbps.value && (typeof limitBandwidthKbps.value !== 'number' || limitBandwidthKbps.value < 0)) {
        errorList.value.push("Limit Bandwidth must be a positive number.");
        errorTags.value.limitBandwidthKbps = true;
    }

    // Validate includeFromPath
    if (includeFromPath.value && typeof includeFromPath.value !== 'string') {
        errorList.value.push("Include Files from Path must be a valid path string.");
        errorTags.value.includeFromPath = true;
    }

    // Validate excludeFromPath
    if (excludeFromPath.value && typeof excludeFromPath.value !== 'string') {
        errorList.value.push("Exclude Files from Path must be a valid path string.");
        errorTags.value.excludeFromPath = true;
    }

    // Validate maxTransferSize
    if (maxTransferSize.value && (typeof maxTransferSize.value !== 'number' || maxTransferSize.value < 0)) {
        errorList.value.push("Max Transfer Size must be a positive number.");
        errorTags.value.maxTransferSize = true;
    }

    if (multiThreadOptions.value) {
        // Validate multiThreadChunkSize
        if (multiThreadChunkSize.value && (typeof multiThreadChunkSize.value !== 'number' || multiThreadChunkSize.value <= 0)) {
            errorList.value.push("Chunk Size must be a positive number.");
            errorTags.value.multiThreadChunkSize = true;
        }

        // Validate multiThreadCutoff
        if (multiThreadCutoff.value && (typeof multiThreadCutoff.value !== 'number' || multiThreadCutoff.value <= 0)) {
            errorList.value.push("Cutoff Size must be a positive number.");
            errorTags.value.multiThreadCutoff = true;
        }

        // Validate multiThreadStreams
        if (multiThreadStreams.value && (typeof multiThreadStreams.value !== 'number' || multiThreadStreams.value <= 0)) {
            errorList.value.push("Number of Streams must be a positive integer.");
            errorTags.value.multiThreadStreams = true;
        }

        // Validate multiThreadWriteBufferSize
        if (multiThreadWriteBufferSize.value && (typeof multiThreadWriteBufferSize.value !== 'number' || multiThreadWriteBufferSize.value <= 0)) {
            errorList.value.push("Write Buffer Size must be a positive number.");
            errorTags.value.multiThreadWriteBufferSize = true;
        }
    }
}


function clearErrorTags() {
    for (const key in errorTags.value) {
        errorTags.value[key] = false;
    }
    errorList.value = [];
}

function validateParams() {
    clearErrorTags();
    validateAllValues();

    if (errorList.value.length == 0 && Object.values(errorTags.value).every(tag => tag === false)) {
        setParams();
    } 
    // else {
    //     pushNotification(new Notification('Error', `There are errors:\n${errorList.value.join("\n")}`, 'error', 8000));
    // }
}

function setParams() {
    const directionPUSH = new SelectionOption('push', 'Push');
    const directionPULL = new SelectionOption('pull', 'Pull');

    const transferDirection = directionSwitched.value ? directionPULL : directionPUSH;

    const newParams = new ParameterNode("Cloud Sync Task Config", "cloudSyncConfig")
        .addChild(new StringParameter('Local Path', 'local_path', localPath.value))
        .addChild(new StringParameter('Target Path', 'target_path', targetPath.value))
        .addChild(new SelectionParameter('Direction', 'direction', transferDirection.value))
        .addChild(new SelectionParameter('Transfer Type', 'type', transferType.value))
        .addChild(new SelectionParameter('Provider', 'provider', selectedRemote.value!.type))
        .addChild(new CloudSyncRemote(selectedRemote.value!.name, selectedRemote.value!.type, selectedRemote.value!.authParams, selectedRemote.value!.provider))
        .addChild(new ParameterNode('Rclone Options', 'rcloneOptions')
            .addChild(new BoolParameter('Check First', 'check_first_flag', checkFirst.value))
            .addChild(new BoolParameter('Checksum', 'checksum_flag', checksum.value))
            .addChild(new BoolParameter('Update', 'update_flag', update.value))
            .addChild(new BoolParameter('Ignore Existing', 'ignore_existing_flag', ignoreExisting.value))
            .addChild(new BoolParameter('Dry Run', 'dry_run_flag', dryRun.value))
            .addChild(new IntParameter('Number of Transfers', 'transfers', numberOfTransfers.value))
            .addChild(new StringParameter('Include Pattern', 'include_pattern', includePattern.value))
            .addChild(new StringParameter('Exclude Pattern', 'exclude_pattern', excludePattern.value))
            .addChild(new StringParameter('Additional Custom Arguments', 'custom_args', customArgs.value))

            .addChild(new IntParameter('Limit Bandwidth', 'bandwidth_limit_kbps', limitBandwidthKbps.value))
            .addChild(new BoolParameter('Ignore Size', 'ignore_size_flag', ignoreSize.value))
            .addChild(new BoolParameter('Inplace', 'inplace_flag', inplace.value))
            .addChild(new IntParameter('Multi-Thread Chunk Size', 'multithread_chunk_size', multiThreadChunkSize.value))
            .addChild(new StringParameter('Multi-Thread Chunk Size Unit', 'multithread_chunk_size_unit', multiThreadChunkSizeUnit.value))
            .addChild(new IntParameter('Multi-Thread Cutoff', 'multithread_cutoff', multiThreadCutoff.value))
            .addChild(new StringParameter('Multi-Thread Cutoff Unit', 'multithread_cutoff_unit', multiThreadCutoffUnit.value))
            .addChild(new IntParameter('Multi-Thread Streams', 'multithread_streams', multiThreadStreams.value))
            .addChild(new IntParameter('Multi-Thread Write Buffer Size', 'multithread_write_buffer_size', multiThreadWriteBufferSize.value))
            .addChild(new StringParameter('Multi-Thread Write Buffer Size Unit', 'multithread_write_buffer_size_unit', multiThreadWriteBufferSizeUnit.value))
            .addChild(new StringParameter('Files From', 'include_from_path', includeFromPath.value))
            .addChild(new StringParameter('Exclude From', 'exclude_from_path', excludeFromPath.value))
            .addChild(new IntParameter('Max Transfer Size', 'max_transfer_size', maxTransferSize.value))
            .addChild(new SelectionParameter('Cutoff Mode', 'cutoff_mode', cutoffMode.value))
            .addChild(new BoolParameter('No Traverse', 'no_traverse_flag', noTraverse.value))
            .addChild(new BoolParameter('Preserve Metadata', 'metadata_flag', preserveMetadata.value))
        );

    parameters.value = newParams;
    console.log('newParams:', newParams);
}

onMounted(async () => {
    await initializeData();
    // console.log("Component mounted");
    console.log("Existing remotes:", existingRemotes);  // Check if existingRemotes are populated
});


defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});

provide('show-create-remote', showCreateRemote);
provide('show-manage-remotes', showManageRemotes);
</script>