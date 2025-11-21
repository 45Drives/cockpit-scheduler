<template>
    <!-- SIMPLE MODE -->
    <div v-if="props.simple" class="space-y-4 my-2">

        <!-- Paths -->
        <SimpleFormCard title="What do you want to copy?" description="Choose a folder stored on this server that was
            created by a client backup. This is the backed-up copy of your files, not your live PC.">
            <label class="block text-sm mt-1 text-default">Local folder</label>

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
                <select v-model="localPath" class="input-textlike text-sm w-full text-default bg-default rounded-md">
                    <option v-for="opt in opts" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                    </option>
                </select>
                <p class="text-[11px] text-muted mt-1">
                    Scope: {{ shareRoot || '—' }}
                    <span> • Full Path: {{ localPath }}</span>
                    <span v-if="smbUser"> • User: {{ smbUser }}</span>
                </p>
            </div>

            <!-- manual input fallback -->
            <div v-else class="mt-1">
                <input type="text" v-model="localPath" @blur="ensureTrailingSlash('local')" :class="[
                    'mt-1 block w-full input-textlike sm:text-sm bg-default text-default',
                    errorTags?.localPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]" placeholder="/data/photos/" />
                <p class="text-[11px] text-muted mt-1">No folders found; enter a path manually.</p>
                <p class="text-[11px] text-muted mt-1">
                    Tip: Local path should end with a <code>/</code>. We’ll add it for you if missing.
                </p>
            </div>

        </SimpleFormCard>
        <!-- Remote/account -->
        <SimpleFormCard title="Choose your cloud account" description="Pick an existing account or add a new one.">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-2">
                <div class="lg:col-span-2">
                    <label class="block text-sm mt-1 text-default">Cloud account</label>
                    <div class="flex items-center gap-2">
                        <select v-model="selectedRemote"
                            class="mt-1 block w-full input-textlike sm:text-sm text-default" :class="[
                                errorTags?.selectedRemote ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                            ]">
                            <option :value="undefined">Select Remote</option>
                            <option v-for="(remote, idx) in existingRemotes" :key="idx" :value="remote">
                                {{ remote.name }}
                            </option>
                        </select>
                        <img v-if="selectedRemote" :src="getProviderLogo(undefined, selectedRemote)"
                            :title="selectedRemote.getProviderName?.() || selectedRemote.name" alt="provider"
                            class="w-5 h-5" />
                    </div>
                    <p class="text-[11px] text-muted mt-1">
                        We use an rclone “remote” for the cloud connection.
                    </p>
                </div>

                <div class="flex lg:justify-end gap-2">
                    <!-- <button @click.stop="createRemoteBtn()" class="btn btn-primary w-full lg:w-auto">Add
                        Account</button> -->
                    <button @click.stop="manageRemotesBtn()" class="btn btn-secondary w-full lg:w-auto">
                        Add/Manage Cloud Credentials
                    </button>
                </div>
            </div>
        </SimpleFormCard>

        <!-- Direction + behavior -->
        <!-- <SimpleFormCard title="How should we transfer?" description="Set direction and behavior."> -->
        <SimpleFormCard title="How should we transfer?">
            <!-- <div class="flex items-center justify-between bg-plugin-header rounded-lg p-2 cursor-pointer select-none"
                role="button" tabindex="0" @click="directionSwitched = !directionSwitched"
                @keydown.enter.prevent="directionSwitched = !directionSwitched"
                @keydown.space.prevent="directionSwitched = !directionSwitched">
                <span class="text-sm text-default font-medium">
                    {{ directionSwitched ? 'Download from Cloud → Local' : 'Upload from Local → Cloud' }}
                </span>

                <Switch v-model="directionSwitched" @click.stop :class="[
                    directionSwitched ? 'bg-secondary' : 'bg-well',
                    'relative inline-flex h-6 w-11 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-slate-600 focus:ring-offset-2'
                ]">
                    <span class="sr-only">Toggle direction</span>
                    <span aria-hidden="true" :class="[
                        directionSwitched ? 'translate-x-5' : 'translate-x-0',
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-default shadow ring-0 transition duration-200'
                    ]" />
                </Switch>
            </div> -->


            <fieldset class="mt-2">
                <legend class="sr-only">Transfer behavior</legend>
                <div class="grid gap-2 sm:grid-cols-3">
                    <label
                        class="flex items-start gap-2 rounded-md border border-default p-2 cursor-pointer bg-default">
                        <input type="radio" class="mt-1 h-4 w-4" value="copy" v-model="transferType" />
                        <div>
                            <div class="text-sm text-default font-medium">Copy</div>
                            <div class="text-[11px] text-muted">Add/update files; don’t delete at destination.</div>
                        </div>
                    </label>

                    <label
                        class="flex items-start gap-2 rounded-md border border-default p-2 cursor-pointer bg-default">
                        <input type="radio" class="mt-1 h-4 w-4" value="sync" v-model="transferType" />
                        <div>
                            <div class="text-sm text-default font-medium">Sync</div>
                            <div class="text-[11px] text-muted">Make destination match source (may delete extras).
                            </div>
                        </div>
                    </label>

                    <label
                        class="flex items-start gap-2 rounded-md border border-default p-2 cursor-pointer bg-default">
                        <input type="radio" class="mt-1 h-4 w-4" value="move" v-model="transferType" />
                        <div>
                            <div class="text-sm text-default font-medium">Move</div>
                            <div class="text-[11px] text-muted">Copy then remove from source after success.</div>
                        </div>
                    </label>
                </div>
            </fieldset>
        </SimpleFormCard>

        <!-- Paths -->
        <SimpleFormCard title="Where do you want to copy it to?" description="Choose where it will live in the cloud.">

            <label class="block text-sm mt-2 text-default">
                Cloud folder <span v-if="selectedRemote">({{ selectedRemote.name }})</span>
            </label>
            <input type="text" v-model="targetPath"
                class="mt-1 block w-full input-textlike sm:text-sm bg-default text-default"
                :class="[errorTags?.targetPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                placeholder="e.g. bucket/folder" />
            <p class="text-[11px] text-muted mt-1">
                Example: <code>my-bucket/backups/</code>. This is the path inside the selected cloud account.
            </p>
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
            <!-- TOP -->
            <div name="rclone-remotes"
                class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-1 bg-accent"
                style="grid-row: 1 / span 1;">
                <label class="mt-1 mb-2 col-span-1 block text-base leading-6 text-default">Remote Configuration</label>
                <div name="select-remote" class="grid grid-cols-2 gap-x-2">
                    <div class="flex flex-row justify-between items-center col-span-2">
                        <label class="mt-1 block text-sm leading-6 text-default">
                            Select Existing Remote
                            <InfoTile class="ml-1"
                                title="Choose a preconfigured Rclone remote connection to use for this task." />
                            <img v-if="selectedRemote" :src="getProviderLogo(undefined, selectedRemote)"
                                alt="provider-logo" class="inline-block w-5 h-5 ml-2"
                                :title="selectedRemote.getProviderName()" />
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
                            class="mt-1 btn btn-primary h-fit w-full" :class=truncateText
                            :title="'Create a new Rclone remote.'">
                            Create New
                        </button>
                        <button v-if="existingRemotes.length > 0" @click.stop="manageRemotesBtn()"
                            id="manage-remotes-btn" :title="'Edit or delete an existing Rclone remote.'"
                            name="manage-remotes-btn" class="mt-1 btn btn-secondary h-fit w-full" :class=truncateText>
                            Manage Existing
                        </button>
                        <button v-else disabled @click.stop="manageRemotesBtn()" id="manage-remotes-btn"
                            :title="'No existing Rclone remotes detected.'" name="manage-remotes-btn"
                            class="mt-1 btn btn-secondary h-fit w-full" :class=truncateText>
                            Manage Existing
                        </button>
                    </div>
                </div>

                <div name="transfer-config" class="grid grid-cols-2 col-span-2 gap-x-2">
                    <div name="transfer-type" class="col-span-1 mt-1.5">
                        <div class="flex flex-row justify-between items-center">
                            <label class="block text-sm leading-6 text-default">
                                Transfer Type
                                <InfoTile class="ml-1" :title="transferTypeComputed" />
                            </label>
                            <ExclamationCircleIcon v-if="errorTags.transferType" class="mt-1 w-5 h-5 text-danger" />
                        </div>
                        <div class="">
                            <select id="existing-remote-selection" v-model="transferType"
                                name="existing-remote-selection"
                                :class="[errorTags.transferType ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                                <option :value="undefined">Select Type of Rclone Transfer</option>
                                <option :value="'copy'">COPY</option>
                                <option :value="'move'">MOVE</option>
                                <option :value="'sync'">SYNC</option>
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
                            <div @click="directionSwitched = !directionSwitched"
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
                                <InfoTile class="ml-1" :title="localTitleComputed" />
                            </label>
                            <ExclamationCircleIcon v-if="errorTags.localPath" class="mt-1 w-5 h-5 text-danger" />
                        </div>
                        <div>
                            <input type="text" v-model="localPath"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                :class="[errorTags.localPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                placeholder="Specify Local Path" :title="localTitleComputed" />
                        </div>
                    </div>
                    <div name="destination-path">
                        <div class="flex flex-row justify-between items-center">
                            <label class="mt-1 block text-sm leading-6 text-default">
                                Target Path
                                <InfoTile class="ml-1" :title="targetTitleComputed" />
                            </label>
                            <ExclamationCircleIcon v-if="errorTags.targetPath" class="mt-1 w-5 h-5 text-danger" />
                        </div>
                        <div>
                            <input type="text" v-model="targetPath"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                :class="[errorTags.targetPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                placeholder="Specify Target Path" :title="targetTitleComputed" />
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
                    <div class="col-span-1 items-center">
                        <div name="options-parallel-threads" class="col-span-1 mt-1">
                            <label class="mt-1 block text-sm leading-6 text-default">
                                Number of Transfers
                                <InfoTile class="ml-1"
                                    :title="`Limit the number of simultaneous file transfers. Higher values may speed up transfers but require more system resources.\nDefault is 4.`" />
                            </label>
                            <ExclamationCircleIcon v-if="errorTags.numberOfTransfers"
                                class="mt-1 w-5 h-5 text-danger" />
                            <input type="number" min='1' v-model="numberOfTransfers"
                                title="Limit the number of simultaneous file transfers. Higher values may speed up transfers but require more system resources."
                                :class="[errorTags.numberOfTransfers ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Default is 4" />
                        </div>
                        <div name="options-check-first"
                            class="flex flex-row justify-between items-center mt-2 col-span-1 col-start-1">
                            <label class="text-sm leading-6 text-default">
                                Check First
                                <InfoTile class="ml-1"
                                    title="Perform a check before transferring files to compare the source and destination. Useful for validating integrity." />
                            </label>
                            <input type="checkbox" v-model="checkFirst" class="ml-2 h-4 w-4 rounded" />
                        </div>

                        <div name="options-update"
                            class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Update
                                <InfoTile class="ml-1"
                                    title="Transfer only updated files, skipping files that are already up-to-date in the destination." />
                            </label>
                            <input type="checkbox" v-model="update" class=" h-4 w-4 rounded" />
                        </div>

                        <div name="options-dry-run"
                            class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                            <label class="block text-sm leading-6 text-default mt-0.5">
                                Dry Run
                                <InfoTile class="ml-1"
                                    title="Simulate the operation without making any actual changes. Ideal for testing command behavior." />
                            </label>
                            <input type="checkbox" v-model="dryRun" class=" h-4 w-4 rounded" />
                        </div>

                    </div>

                    <div class="-mt-1 col-span-3 grid grid-cols-2 gap-2 pr-1">
                        <div class="grid grid-cols-2 col-span-2 gap-2 w-full justify-center items-center text-center">
                            <div name="options-include" class="col-span-1">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="mt-1 block text-sm leading-6 text-default">
                                        Include Pattern
                                        <InfoTile class="ml-1"
                                            :title="`Specify a pattern of files to include in the transfer.\n(E.g., *.txt includes all text files.)\n- Separate patterns with commas (,).`" />
                                    </label>
                                    <ExclamationCircleIcon v-if="errorTags.includePattern"
                                        class="mt-1 w-5 h-5 text-danger" />
                                </div>
                                <input type="text" v-model="includePattern"
                                    :class="[errorTags.includePattern ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                    placeholder="Eg. */, *.txt"
                                    :title="`Specify a pattern of files to include in the transfer.\n(E.g., *.txt includes all text files.)\n- Separate patterns with commas (,).`" />
                            </div>
                            <div name="options-exclude" class="col-span-1">
                                <div class="flex flex-row justify-between items-center">
                                    <label class="mt-1 block text-sm leading-6 text-default">
                                        Exclude Pattern
                                        <InfoTile class="ml-1"
                                            :title="`Specify a pattern of files to exclude in the transfer.\n(E.g., *.log excludes all log files.)\n- Separate patterns with commas (,).`" />
                                    </label>
                                    <ExclamationCircleIcon v-if="errorTags.excludePattern"
                                        class="mt-1 w-5 h-5 text-danger" />
                                </div>
                                <input type="text" v-model="excludePattern"
                                    :class="[errorTags.excludePattern ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                    placeholder="Eg. */, *.txt"
                                    :title="`Specify a pattern of files to exclude in the transfer.\n(E.g., *.log excludes all log files.)\n- Separate patterns with commas (,).`" />
                            </div>
                        </div>
                        <div name="options-log-file-path" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="block text-sm leading-6 text-default">
                                    Log File Path
                                    <InfoTile class="ml-1"
                                        :title="`Optional path to an rclone log file. If set, rclone will write logs to this file using --log-file=PATH.`" />
                                </label>
                                <ExclamationCircleIcon v-if="errorTags.logFilePath" class="mt-1 w-5 h-5 text-danger" />
                            </div>
                            <input type="text" v-model="logFilePath"
                                :class="[errorTags.logFilePath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Eg. /var/log/newtask"
                                :title="`Optional path to an rclone log file. If set, rclone will write logs to this file using --log-file=PATH.`" />
                        </div>
                        <div name="options-extra-params" class="col-span-1">
                            <div class="flex flex-row justify-between items-center">
                                <label class="block text-sm leading-6 text-default">
                                    Extra Parameters
                                    <InfoTile class="ml-1"
                                        :title="`Specify any additional Rclone parameters not covered by other options.\n(E.g., --ignore-checksum.)\n- Separate any extra parameters, flags or options you wish to include with commas (,).`" />
                                </label>
                                <ExclamationCircleIcon v-if="errorTags.customArgs" class="mt-1 w-5 h-5 text-danger" />
                            </div>
                            <textarea v-model="customArgs" rows="1"
                                :class="[errorTags.customArgs ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                placeholder="Eg. -I, --ignore-checksum, etc."
                                :title="`Specify any additional Rclone parameters not covered by other options.\n(E.g., --ignore-checksum.)\n- Separate any extra parameters, flags or options you wish to include with commas (,).`" />
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
                                        <div name="options-checksum"
                                            class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                                            <label class="text-sm leading-6 text-default">
                                                Checksum
                                                <InfoTile class="ml-1"
                                                    title="Use checksums to verify file integrity, where possible. Note that this may increase transfer time." />
                                            </label>
                                            <input type="checkbox" v-model="checksum" class="ml-2 h-4 w-4 rounded" />
                                        </div>
                                        <div name="options-ignore-existing"
                                            class="flex flex-row justify-between items-center mt-1 col-span-1 col-start-1">
                                            <label class="text-sm leading-6 text-default">
                                                Ignore Existing
                                                <InfoTile class="ml-1"
                                                    title="Skip files that already exist on the destination without verifying their integrity." />
                                            </label>
                                            <input type="checkbox" v-model="ignoreExisting"
                                                class="ml-2 h-4 w-4 rounded" />
                                        </div>
                                        <div name="options-ignore-size" title=""
                                            class="flex flex-row justify-between items-center col-span-1 col-start-1">
                                            <label class="block text-sm leading-6 text-default mt-0.5">
                                                Ignore Size
                                                <InfoTile class="ml-1"
                                                    title="Ignore file sizes during the transfer, transferring files regardless of their size difference between source and destination." />
                                            </label>
                                            <input type="checkbox" v-model="ignoreSize" class=" h-4 w-4 rounded" />
                                        </div>
                                        <div name="options-inplace" title=""
                                            class="flex flex-row justify-between items-center col-span-1 col-start-1">
                                            <label class="block text-sm leading-6 text-default mt-0.5">
                                                Inplace
                                                <InfoTile class="ml-1"
                                                    title="Write files directly to the destination, instead of using temporary files. This option may speed up transfers but can risk partial data if interrupted." />
                                            </label>
                                            <input type="checkbox" v-model="inplace" class=" h-4 w-4 rounded" />
                                        </div>
                                        <div name="options-no-traverse" title=""
                                            class="flex flex-row justify-between items-center col-span-1 col-start-1">
                                            <label class="block text-sm leading-6 text-default mt-0.5">
                                                No Traverse
                                                <InfoTile class="ml-1"
                                                    title="Do not traverse the destination folder. Useful for remote systems where directory listing is slow." />
                                            </label>
                                            <input type="checkbox" v-model="noTraverse" class=" h-4 w-4 rounded" />
                                        </div>
                                    </div>

                                    <div class="col-span-3 grid grid-cols-3 grid-rows-2 gap-2">
                                        <div name="options-limit-bw" class="col-span-1">
                                            <label class="mt-1 text-sm leading-6 text-default">
                                                Limit Bandwidth (Kbps)
                                                <InfoTile class="ml-1"
                                                    title="Throttle bandwidth usage in kilobytes per second to control transfer speed and reduce network load." />
                                            </label>
                                            <ExclamationCircleIcon v-if="errorTags.limitBandwidthKbps"
                                                class="mt-1 w-5 h-5 text-danger" />
                                            <input type="number" min='0' v-model="limitBandwidthKbps"
                                                :class="[errorTags.limitBandwidthKbps ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="Default is None" />
                                        </div>
                                        <div name="options-limit-bw" class="col-span-1">
                                            <label class="mt-1 text-sm leading-6 text-default">
                                                Max Transfer Size
                                                <InfoTile class="ml-1"
                                                    :title="`Set a maximum size limit for files to be transferred. Files larger than this size will be skipped.\nDefault is None.`" />
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
                                        <div name="options-cutoff-mode" class="col-span-1">
                                            <label class="mt-1 text-sm leading-6 text-default">
                                                Cutoff Mode
                                                <InfoTile class="ml-1"
                                                    :title="`(Requires Max Transfer Size)\nSpecify the cutoff mode to use when reaching max transfer limit.\nDefault is HARD.`" />
                                            </label>
                                            <select v-model="cutoffMode"
                                                :title="`(Requires Max Transfer Size)\nSpecify the cutoff mode to use when reaching max transfer limit.\nDefault is HARD.`"
                                                :disabled="!maxTransferSize || maxTransferSize <= 0"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default">
                                                <option :value="undefined">Select Mode</option>
                                                <option value="HARD">HARD</option>
                                                <option value="SOFT">SOFT</option>
                                                <option value="CAUTIOUS">CAUTIOUS</option>
                                            </select>
                                        </div>

                                        <div
                                            class="col-span-3 row-start-2 grid grid-cols-2 gap-2 w-full justify-center items-center text-center">
                                            <div name="options-include-files-from-path" class="col-span-1">
                                                <div class="flex flex-row justify-between items-center">
                                                    <label class="mt-1 block text-sm leading-6 text-default">
                                                        Include Files from Path
                                                        <InfoTile class="ml-1"
                                                            title="Specify a file containing a list of files to include in the transfer." />
                                                    </label>
                                                    <ExclamationCircleIcon v-if="errorTags.includeFromPath"
                                                        class="mt-1 w-5 h-5 text-danger" />
                                                </div>
                                                <input type="text" v-model="includeFromPath"
                                                    title="Specify a file containing a list of files to include in the transfer."
                                                    :class="[errorTags.includeFromPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                    placeholder="Eg. '/path/to/included_file_paths.txt'" />
                                            </div>
                                            <div name="options-exclude-files-from-path" class="col-span-1">
                                                <div class="flex flex-row justify-between items-center">
                                                    <label class="mt-1 block text-sm leading-6 text-default">
                                                        Exclude Files from Path
                                                        <InfoTile class="ml-1"
                                                            title="Specify a file containing a list of files to exclude from the transfer." />
                                                    </label>
                                                    <ExclamationCircleIcon v-if="errorTags.excludeFromPath"
                                                        class="mt-1 w-5 h-5 text-danger" />
                                                </div>
                                                <input type="text" v-model="excludeFromPath"
                                                    title="Specify a file containing a list of files to exclude from the transfer."
                                                    :class="[errorTags.excludeFromPath ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                    placeholder="Eg. '/path/to/excluded_files.txt'" />
                                            </div>
                                        </div>
                                    </div>

                                    <div name="multi-thread-options"
                                        class="col-span-4 grid grid-cols-2 gap-1 border border-default rounded-md p-2 bg-accent">
                                        <label
                                            class="w-fit col-span-2 mt-1 block text-base leading-6 text-default items-center">
                                            Use Multiple Threads
                                            <input type="checkbox" v-model="multiThreadOptions"
                                                class="ml-4 mb-0.5 h-4 w-4 rounded" />
                                        </label>

                                        <div name="options-multi-thread-chunk-size">
                                            <div class="flex flex-row items-center justify-between mt-1">
                                                <label class="block text-sm leading-6 text-default">
                                                    Chunk Size
                                                    <InfoTile class="ml-1"
                                                        :title="`Set the size of chunks for chunked transfers. This option may improve performance for large files.\nDefault is 64MiB.`" />
                                                </label>
                                                <ExclamationCircleIcon v-if="errorTags.multiThreadChunkSize"
                                                    class="ml-1 w-5 h-5 text-danger" />
                                            </div>
                                            <div class="flex items-center">
                                                <input type="number" min="0" v-model="multiThreadChunkSize"
                                                    :disabled="!multiThreadOptions"
                                                    :title="`Set the size of chunks for chunked transfers. This option may improve performance for large files.\nDefault is 64MiB.`"
                                                    :class="[errorTags.multiThreadChunkSize ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                    placeholder="Default is 64 MiB" />
                                                <select v-model="multiThreadChunkSizeUnit"
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

                                        <div name="options-multi-thread-cutoff">
                                            <div class="flex flex-row items-center justify-between mt-1">
                                                <label class="block text-sm leading-6 text-default">
                                                    Cutoff Size
                                                    <InfoTile class="ml-1"
                                                        :title="`Specify a maximum file size for which chunking will be used. Files above this size will not be chunked.\nDefault is 256MiB.`" />
                                                </label>
                                                <ExclamationCircleIcon v-if="errorTags.multiThreadCutoff"
                                                    class="mt-1 w-5 h-5 text-danger" />
                                            </div>
                                            <div class="flex items-center">
                                                <input type="number" min='0' v-model="multiThreadCutoff"
                                                    :disabled="!multiThreadOptions"
                                                    :title="`Specify a maximum file size for which chunking will be used. Files above this size will not be chunked.\nDefault is 256MiB.`"
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
                                                <label class="block text-sm leading-6 text-default">
                                                    Number of Streams
                                                    <InfoTile class="ml-1"
                                                        :title="`Set the number of streams (threads) to be used for chunked transfers, where supported.\nDefault is 4.`" />
                                                </label>
                                                <ExclamationCircleIcon v-if="errorTags.multiThreadStreams"
                                                    class="mt-1 w-5 h-5 text-danger" />
                                            </div>

                                            <input type="number" v-model="multiThreadStreams" min="1"
                                                :disabled="!multiThreadOptions"
                                                :title="`Set the number of streams (threads) to be used for chunked transfers, where supported.\nDefault is 4.`"
                                                :class="[errorTags.multiThreadStreams ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']"
                                                class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                                                placeholder="Default is 4 Streams" />
                                        </div>

                                        <div name="options-multi-thread-write-buffer-size">
                                            <div class="flex flex-row items-center justify-between mt-1">
                                                <label class="block text-sm leading-6 text-default"
                                                    :disabled="!multiThreadOptions">
                                                    Write Buffer Size
                                                    <InfoTile class="ml-1"
                                                        :title="`Specify the buffer size for writing data, potentially improving performance for high-throughput transfers.\nDefault is 128KiB.`" />
                                                </label>
                                                <ExclamationCircleIcon v-if="errorTags.multiThreadWriteBufferSize"
                                                    class="mt-1 w-5 h-5 text-danger" />
                                            </div>
                                            <div class="flex items-center">
                                                <input type="number" min='0' v-model="multiThreadWriteBufferSize"
                                                    :disabled="!multiThreadOptions"
                                                    :title="`Specify the buffer size for writing data, potentially improving performance for high-throughput transfers.\nDefault is 128KiB.`"
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
    </div>
    <div v-if="showCreateRemote">
        <component :is="createRemoteComponent" :id-key="'create-remote-modal'" />
    </div>

    <div v-if="showManageRemotes">
        <component :is="manageRemotesComponent" :id-key="'manage-remotes-modal'" />
    </div>
</template>

<script setup lang="ts">
import { ref, Ref, onMounted, inject, provide, watch, computed, watchEffect } from 'vue';
import { Disclosure, DisclosureButton, DisclosurePanel, Switch } from '@headlessui/vue';
import { ExclamationCircleIcon, ChevronDoubleRightIcon, ChevronUpIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, IntParameter, StringParameter, BoolParameter, SelectionParameter, SelectionOption } from '../../../models/Parameters';
import { CloudSyncRemote, getProviderLogo, getButtonStyles, CloudSyncProvider, CloudAuthParameter, cloudSyncProviders } from '../../../models/CloudSync';
import { injectWithCheck, checkLocalPathExists, validateRemotePath, validateLocalPath } from '../../../composables/utility';
import { rcloneRemotesInjectionKey, remoteManagerInjectionKey, truncateTextInjectionKey } from '../../../keys/injection-keys';
import SimpleFormCard from '../../simple/SimpleFormCard.vue';
import { useRoute, useRouter } from 'vue-router';
import { useUserScopedFolderListByInstall } from '../../../composables/useUserScopedFolderListByInstall';
import { useClientContextStore } from '../../../stores/clientContext';

const router = useRouter()
const route = useRoute()

interface CloudSyncParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
    simple?: boolean;
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

const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remote manager not provided!");
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
    logFilePath: false,
});

const localPath = ref('');
const targetPath = ref('');
const directionSwitched = ref(false)
const transferType = ref('copy');
const selectedRemote = ref<CloudSyncRemote>();
const checkFirst = ref(false);
const checksum = ref(false);
const update = ref(false);
const ignoreExisting = ref(false);
const dryRun = ref(false);
const numberOfTransfers = ref(4);
const includePattern = ref('');
const excludePattern = ref('');
const customArgs = ref('');
const logFilePath = ref('');
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

const isTaskLoading = ref(false);

onMounted(async () => {
    //for development only
    // if (existingRemotes.value.length < 1) {
    //     existingRemotes.value.push(dummyRemote.value);
    // }

    isTaskLoading.value = true; // Start loading the task
    await initializeData();
    isTaskLoading.value = false; // Mark loading as complete

    //  console.log("Existing remotes:", existingRemotes);
});

watch(selectedRemote, (newVal) => {
    // Only auto-update the targetPath when not loading an existing task
    if (!isTaskLoading.value && newVal) {
        targetPath.value = `${selectedRemote.value!.name}:`;
    }
});

// ---------- User-scoped folder discovery (same as Rsync) ----------
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
    console.log('[cloud-sync folderList]',
        'loading=', folderList.loading.value,
        'error=', folderList.error.value,
        'shareRoot=', folderList.shareRoot.value,
        'smbUser=', folderList.smbUser.value,
        'abs=', folderList.absDirs.value.length
    );
});

// derived values for template
const loadingFolders = folderList.loading;
const discoveryError = folderList.error;
const shareRoot = computed(() => folderList.shareRoot.value);
const smbUser = computed(() => folderList.smbUser.value);
const isEditMode = computed(() => !!props.task);

// label builder to hide UUID segment (same as Rsync)
function prettyLabelFromAbs(abs: string) {
    const root = shareRoot.value || '';
    if (!abs.startsWith(root)) return abs;
    const rel = abs.slice(root.length).replace(/^\/+/, '');
    const parts = rel.split('/').filter(Boolean);
    // drop UUID segment
    return parts.length >= 2 ? parts.slice(1).join('/') + '/' : rel + '/';
}

const opts = computed<Array<{ value: string; label: string }>>(() =>
    (folderList.absDirs.value ?? []).map(abs => ({
        value: abs,
        label: prettyLabelFromAbs(abs),
    }))
);

// choose a sane default when options arrive
watch(opts, (list) => {
    if (!props.simple || isEditMode.value) return;           // ⟵ only in Simple mode
    if (!list.length) return;
    if (!localPath.value || !folderList.underRoot(localPath.value)) {
        localPath.value = list[0].value;
    }
}, { immediate: true });

watch([() => folderList.absDirs.value, () => folderList.shareRoot.value], ([abs]) => {
    if (!props.simple || isEditMode.value) return;           // ⟵ only in Simple mode
    const list = abs || [];
    if (!list.length) return;
    if (!localPath.value || !folderList.underRoot(localPath.value)) {
        localPath.value = list[0];
    }
}, { immediate: true });

// trailing slash helper (mirrors Rsync)
function ensureTrailingSlash(which: 'local' | 'target') {
    if (which === 'local') {
        if (localPath.value && !localPath.value.endsWith('/')) localPath.value += '/';
    } else {
        if (targetPath.value && !targetPath.value.endsWith('/')) targetPath.value += '/';
    }
}

async function initializeData() {
    if (props.task) {
         console.log('loading task:', props.task);
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

        const remoteName = params.find(p => p.key === 'rclone_remote')!.value;
        selectedRemote.value = await myRemoteManager.getRemoteByName(remoteName) || undefined;

        const rcloneOptions = params.find(p => p.key === 'rcloneOptions')!.children;
        const logFileParam = rcloneOptions.find(p => p.key === 'log_file_path');
        logFilePath.value = logFileParam ? logFileParam.value : '';
        checkFirst.value = rcloneOptions.find(p => p.key === 'check_first_flag')!.value;
        checksum.value = rcloneOptions.find(p => p.key === 'checksum_flag')!.value;
        update.value = rcloneOptions.find(p => p.key === 'update_flag')!.value;
        ignoreExisting.value = rcloneOptions.find(p => p.key === 'ignore_existing_flag')!.value;
        dryRun.value = rcloneOptions.find(p => p.key === 'dry_run_flag')!.value;
        numberOfTransfers.value = rcloneOptions.find(p => p.key === 'transfers')!.value;
        includePattern.value = rcloneOptions.find(p => p.key === 'include_pattern')!.value;
        excludePattern.value = rcloneOptions.find(p => p.key === 'exclude_pattern')!.value;
        customArgs.value = rcloneOptions.find(p => p.key === 'custom_args')!.value;

        limitBandwidthKbps.value = rcloneOptions.find(p => p.key === 'bandwidth_limit_kbps')!.value;
        ignoreSize.value = rcloneOptions.find(p => p.key === 'ignore_size_flag')!.value;
        inplace.value = rcloneOptions.find(p => p.key === 'inplace_flag')!.value;

        multiThreadChunkSize.value = rcloneOptions.find(p => p.key === 'multithread_chunk_size')!.value;
        multiThreadChunkSizeUnit.value = rcloneOptions.find(p => p.key === 'multithread_chunk_size_unit')!.value || 'MiB';
        multiThreadCutoff.value = rcloneOptions.find(p => p.key === 'multithread_cutoff')!.value;
        multiThreadCutoffUnit.value = rcloneOptions.find(p => p.key === 'multithread_cutoff_unit')!.value || 'MiB';
        multiThreadStreams.value = rcloneOptions.find(p => p.key === 'multithread_streams')!.value;
        multiThreadWriteBufferSize.value = rcloneOptions.find(p => p.key === 'multithread_write_buffer_size')!.value;
        multiThreadWriteBufferSizeUnit.value = rcloneOptions.find(p => p.key === 'multithread_write_buffer_size_unit')!.value || 'KiB';

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
        maxTransferSizeUnit.value = rcloneOptions.find(p => p.key === 'max_transfer_size_unit')!.value || 'MiB';
        cutoffMode.value = rcloneOptions.find(p => p.key === 'cutoff_mode')!.value || 'HARD';
        noTraverse.value = rcloneOptions.find(p => p.key === 'no_traverse_flag')!.value;

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
            logFilePath: logFilePath.value,
        }));

        loading.value = false;
        // enableTargetPathWatcher.value = true; // Re-enable watcher
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
        logFilePath: logFilePath.value,
    };

    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}

watch(
    [
        update,
        ignoreExisting,
        multiThreadOptions,
        checksum,
        ignoreSize,
        noTraverse,
        includeFromPath,
        excludeFromPath,
    ],
    () => handleMutuallyExclusiveOptions()
);

function handleMutuallyExclusiveOptions() {
    // Case: Update vs Ignore Existing
    if (update.value && ignoreExisting.value) {
        ignoreExisting.value = false; // Prefer update by default
    }

    // Case: Checksum vs Ignore Size
    if (checksum.value && ignoreSize.value) {
        ignoreSize.value = false; // Prefer checksum for accuracy
    }

    // Case: No Traverse vs Include/Exclude Files from Path
    if (noTraverse.value && (includeFromPath.value || excludeFromPath.value)) {
        includeFromPath.value = '';
        excludeFromPath.value = ''; // Clear include/exclude paths if noTraverse is enabled
    }

    // Case: Multi-threading settings
    if (multiThreadOptions.value) {
        multiThreadChunkSize.value = multiThreadChunkSize.value || 64;
        multiThreadCutoff.value = multiThreadCutoff.value || 256;
        multiThreadStreams.value = multiThreadStreams.value || 4;
        multiThreadWriteBufferSize.value =
            multiThreadWriteBufferSize.value || 128;
    } else {
        multiThreadChunkSize.value = undefined;
        multiThreadCutoff.value = undefined;
        multiThreadStreams.value = undefined;
        multiThreadWriteBufferSize.value = undefined;
    }

    // Case: Max Transfer Size vs Cutoff Mode
    if (maxTransferSize.value > 0 && cutoffMode.value) {
        cutoffMode.value = null; // Prioritize max transfer size if both are set
    }

    // Case: Dry Run vs Transfer Options
    if (dryRun.value) {
        update.value = false;
        ignoreExisting.value = false;
        checksum.value = false;
        // Additional options affecting transfers can be disabled here
    }
}

const localTitleComputed = computed(() => {
    if (!directionSwitched.value) {
        //Push from local to target
        return `This is the source path on your local system. Files from this path will be transferred to the cloud remote.
- With a trailing slash (/): Transfers only the contents of the directory, not the directory itself.
- Without a trailing slash: Transfers the directory and its contents.
- For files, specify the full file path without a trailing slash.`;
    } else {
        //Pull from target to local
        return `This is the destination path on your local system. Files from the remote storage will be downloaded here.
- With a trailing slash (/): Files will be placed directly into this directory.
- Without a trailing slash: The remote directory itself will be created here with its contents.
- Ensure there's sufficient free space and the directory is writable.`;
    }
});

const targetTitleComputed = computed(() => {
    if (!directionSwitched.value) {
        // Push from local to remote
        return `This is the destination path on the remote storage. Files from the local path will be uploaded here.

Format: remoteName:bucketName/path/to/folder

- remoteName: The rclone remote (e.g., 'gdrive', 's3remote', 'azureblob')
- bucketName or container: Required for cloud remotes like S3, B2, Azure, etc.
- path/to/folder: Optional subdirectory within the bucket/container

Examples:
- gdrive:Backups/April2025
- s3remote:my-bucket/daily
- azureblob:container/data

Tips:
- Verify the path exists or rclone is allowed to create it.
- Avoid uploading directly to the root of a bucket unless necessary.`;
    } else {
        // Pull from remote to local
        return `This is the source path on the remote storage. Files from this path will be pulled to your local system.

Format: remoteName:bucketName/path/to/folder

- remoteName: The rclone remote (e.g., 'gdrive', 's3remote', 'azureblob')
- bucketName or container: Required for cloud remotes like S3, B2, Azure, etc.
- path/to/folder: Specific directory or file path to download

Examples:
- dropbox:Projects/Reports
- b2:mybucket/backups
- idrive:archive/2024

Tips:
- Make sure the path exists and contains the files you want.
- Avoid pulling large or unnecessary directories unless required.`;
    }
});

const transferTypeComputed = computed(() => {
    if (!directionSwitched.value) {
        //Push from local to target
        return `Select the transfer type for sending files from your local path to the remote path:
COPY: Copy files to the remote, skipping files that already exist.
MOVE: Move files to the remote and delete them locally after a successful transfer.
SYNC: Make the remote identical to your local path by adding, updating, or deleting files on the remote. Use carefully, as it may delete remote files.`;
    } else {
        //Pull from target to local
        return `Select the transfer type for retrieving files from the remote path to your local path:
COPY: Copy files to the local system, skipping files that already exist.
MOVE: Move files to the local system and delete them from the remote after a successful transfer.
SYNC: Make the local path identical to the remote by adding, updating, or deleting files locally. Use carefully, as it may delete local files.`;
    }
});

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
    if (props.simple) {
        router.push({ name: 'SimpleManageRemotes', query: { returnTo: route.fullPath } })
    } else {
        await loadManageRemotesComponent();
        showManageRemotes.value = true;
    }

}

const manageRemotesComponent = ref();
async function loadManageRemotesComponent() {
    const module = await import('../../modals/ManageRemotes.vue');
    manageRemotesComponent.value = module.default;
}


async function validateLocalTransferPath() {
    // Clear the local path error before validation
    errorTags.value.localPath = false;

    if (!localPath.value) {
        errorList.value.push("Local path is required.");
        errorTags.value.localPath = true;
        return false;
    }

    // Check if the path exists asynchronously
    const pathExists = await checkLocalPathExists(localPath.value);
    const validPath = validatePath(localPath.value);
    //  console.log(`Path Exists: ${pathExists}, Valid Format: ${validPath}`);

    if (!pathExists) {
        errorList.value.push(`Path does not exist: ${localPath.value}`);
        errorTags.value.localPath = true;
        return false;
    }

    if (!validPath) {
        errorList.value.push("Source path format is invalid.");
        errorTags.value.localPath = true;
        return false;
    }

    // If everything is valid
    //  console.log("Valid source path.");
    return true;
}

function validateDestinationTransferPath() {
    if (!targetPath.value) {
        errorList.value.push("Target path is required.");
        errorTags.value.targetPath = true;
        return false;
    }

    if (validatePath(targetPath.value, true)) {
        errorTags.value.targetPath = false;
        // if (!targetPath.value.endsWith('/')) {
        //     targetPath.value += '/';
        // }
        //  console.log("Valid destination path: " + targetPath.value);
        return true;
    } else {
        errorList.value.push("Target path is invalid.");
        errorTags.value.targetPath = true;
        return false;
    }
}

function validatePath(path: string, isRemote?: boolean) {
    return isRemote ? validateRemotePath(path) : validateLocalPath(path);
}

// function validatePath(path, isRemote?) {
//     //no spaces allowed
//     // const pathRegex = /^(?:[a-zA-Z]:\\|\/)?(?:[\w\-.]+(?:\\|\/)?)*$/;

//     if (isRemote) {
//         const rcloneRegex = /^[\w\-.]+:[\\/]*(?:[\w\s\-.]+[\\/])*[\w\s\-.]*$/;
//         return rcloneRegex.test(path);
//     } else {
//         // Allow flexible, valid paths with spaces
//         const localPathRegex = /^(?:[a-zA-Z]:\\|\/)?(?:[\w\s\-.]+(?:\\|\/)?)*$/;
//         return localPathRegex.test(path);
//     }
// }


async function validateAllValues() {

    if (!transferType.value) {
        errorList.value.push("Transfer type is required.");
        errorTags.value.transferType = true;
    }

    if (numberOfTransfers.value && typeof numberOfTransfers.value !== 'number' || numberOfTransfers.value < 0) {
        errorList.value.push("Number of Transfers must be a valid number.");
        errorTags.value.numberOfTransfers = true;
    }

    // Validate logFilePath
    if (logFilePath.value && typeof logFilePath.value !== 'string') {
        errorList.value.push("Log File Path must be a string.");
        errorTags.value.logFilePath = true;
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

async function validateSelectedRemote() {
    // Clear previous error
    errorTags.value.selectedRemote = false;

    // Check if selectedRemote is set
    if (!selectedRemote.value) {
        errorList.value.push("Remote is required.");
        errorTags.value.selectedRemote = true;
        return false;
    }

    // Verify the remote exists in the list of existingRemotes
    const remoteExists = existingRemotes.value.some(
        (remote) => remote.name === selectedRemote.value!.name
    );

    if (!remoteExists) {
        errorList.value.push(`Selected remote "${selectedRemote.value.name}" does not exist.`);
        errorTags.value.selectedRemote = true;
        return false;
    }

    return true;
}


function clearErrorTags() {
    for (const key in errorTags.value) {
        errorTags.value[key] = false;
    }
    errorList.value = [];
}

async function validateParams() {
    // clearErrorTags();
    await validateSelectedRemote();
    await validateAllValues();
    await validateLocalTransferPath();
    validateDestinationTransferPath();

    if (errorList.value.length == 0 && Object.values(errorTags.value).every(tag => tag === false)) {
        setParams();
    }
}

function setParams() {
    const directionPUSH = new SelectionOption('push', 'Push');
    const directionPULL = new SelectionOption('pull', 'Pull');

    const transferDirection = directionSwitched.value ? directionPULL : directionPUSH;
    // const rclonePath = `${selectedRemote.value!.name}:${targetPath.value}`;
    const newParams = new ParameterNode("Cloud Sync Task Config", "cloudSyncConfig")
        .addChild(new StringParameter('Local Path', 'local_path', localPath.value))
        .addChild(new StringParameter('Target Path', 'target_path', targetPath.value))
        .addChild(new SelectionParameter('Direction', 'direction', transferDirection.value))
        .addChild(new SelectionParameter('Transfer Type', 'type', transferType.value))
        .addChild(new SelectionParameter('Provider', 'provider', selectedRemote.value!.type))
        .addChild(new StringParameter('Rclone Remote', 'rclone_remote', selectedRemote.value!.name))
        .addChild(new ParameterNode('Rclone Options', 'rcloneOptions')
            .addChild(new StringParameter('Log File Path', 'log_file_path', logFilePath.value))

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
        );

    parameters.value = newParams;
    //  console.log('newParams:', newParams);
}

onMounted(async () => {
    await initializeData();
    // console.log("Component mounted");
    //  console.log("Existing remotes:", existingRemotes);  // Check if existingRemotes are populated
});

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});

provide('show-create-remote', showCreateRemote);
provide('show-manage-remotes', showManageRemotes);
</script>