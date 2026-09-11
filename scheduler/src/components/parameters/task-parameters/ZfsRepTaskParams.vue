<template>
    <!-- Loading spinner (shared) -->
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 auto-rows-min items-start">
        <div
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                :fillColor="'fill-gray-500'" />
        </div>
    </div>

    <!-- ═══ SIMPLE MODE ═══ -->
    <div v-else-if="props.simple" class="space-y-4 my-2">

        <!-- Source: Which dataset to back up -->
        <SimpleFormCard title="Which folder do you want to back up?"
            description="Pick the ZFS pool and dataset (folder) on this server that you want to protect.">

            <label class="block text-sm mt-1 text-default">Pool</label>
            <div v-if="loadingSourcePools" class="mt-1 flex items-center gap-2">
                <CustomLoadingSpinner :width="'w-5'" :height="'h-5'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'" />
                <span class="text-sm text-muted">Loading pools…</span>
            </div>
            <select v-else v-model="sourcePool" :class="[
                'mt-1 block w-full input-textlike text-sm bg-default text-default rounded-md',
                sourcePoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
            ]">
                <option value="">Select a pool</option>
                <option v-for="pool in sourcePools" :key="pool" :value="pool">{{ pool }}</option>
            </select>

            <label class="block text-sm mt-3 text-default">Dataset (Folder)</label>
            <div v-if="loadingSourceDatasets" class="mt-1 flex items-center gap-2">
                <CustomLoadingSpinner :width="'w-5'" :height="'h-5'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'" />
                <span class="text-sm text-muted">Loading datasets…</span>
            </div>
            <select v-else v-model="sourceDataset" :disabled="!sourcePool" :class="[
                'mt-1 block w-full input-textlike text-sm bg-default text-default rounded-md',
                sourceDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
            ]">
                <option value="">{{ sourcePool ? 'Select a dataset' : 'Pick a pool first' }}</option>
                <option v-for="ds in sourceDatasets" :key="ds" :value="ds">{{ ds }}</option>
            </select>

            <template #footer>
                <p class="text-[11px] text-muted">
                    This is the data you want to send <strong>from</strong> this server.
                </p>
            </template>
        </SimpleFormCard>

        <!-- Destination: Where to send it -->
        <SimpleFormCard title="Where should the backup go?"
            description="Enter the backup server details and pick the destination ZFS pool and dataset.">
            <template #header-right>
                <div class="flex items-center gap-2">
                    <span :title="wireShieldMissing ? wireShieldMissingMessage : 'Set up a secure connection to a backup server at another location, so backups travel safely over the internet.'">
                        <button @click="openWireShield" :disabled="wireShieldMissing" class="btn btn-secondary h-fit text-xs inline-flex items-center gap-1">
                            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                            Connect Off-Site Server
                        </button>
                    </span>
                    <button v-if="!testingSSH" @click="handleTestSSH" :disabled="!destHost" class="btn btn-secondary h-fit">
                        Test Connection (SSH)
                    </button>
                    <button v-else disabled class="btn btn-secondary h-fit">Testing…</button>
                </div>
            </template>

            <div class="grid grid-cols-3 gap-2">
                <div>
                    <label class="block text-sm text-default">Server address <span class="text-danger">*</span></label>
                    <input type="text" v-model="destHost" @input="debouncedDestHostChange()"
                        @blur="commitDestHostChange()" @keyup.enter="commitDestHostChange()" :class="[
                        'mt-1 block w-full input-textlike text-sm bg-default text-default',
                        destHostErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" placeholder="e.g. 10.0.0.5 or backup.local" />
                </div>
                <div>
                    <label class="block text-sm text-default">User <span class="text-danger">*</span></label>
                    <input type="text" v-model="destUser"
                        class="mt-1 block w-full input-textlike text-sm bg-default text-default"
                        placeholder="root (default)" :disabled="!destHost" />
                </div>
                <div>
                    <label class="block text-sm text-default" for="zfs-dest-pass">Password</label>
                    <div class="relative mt-1">
                        <input :type="showSshSetupPassword ? 'text' : 'password'" id="zfs-dest-pass"
                            v-model="sshSetupPassword"
                            class="block w-full input-textlike text-sm bg-default text-default pr-10"
                            :disabled="!destHost" />
                        <button type="button" @click="showSshSetupPassword = !showSshSetupPassword"
                            class="absolute inset-y-0 right-0 px-3 flex items-center text-muted"
                            :aria-label="showSshSetupPassword ? 'Hide password' : 'Show password'">
                            <EyeIcon v-if="!showSshSetupPassword" class="w-5 h-5" />
                            <EyeSlashIcon v-else class="w-5 h-5" />
                        </button>
                    </div>
                    <p class="text-[11px] text-muted mt-1">
                        Only used once to install an SSH key. It is not saved or used to run the backup.
                    </p>
                </div>
            </div>

            <!-- SSH Key Setup Prompt (one-time, shown when VPN host set but SSH not configured) -->
            <div v-if="sshSetupNeeded" class="mt-3 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 p-3">
                <p class="text-sm font-medium text-amber-800 dark:text-amber-200 mb-1">
                    First-time setup
                </p>
                <p class="text-xs text-amber-600 dark:text-amber-400 mb-3">
                    This server needs an SSH key on <strong>{{ destUser || 'root' }}@{{ destHost }}</strong> before it can send snapshots there.
                    We'll use the password you entered above to install one — this is a one-time step and the password is not saved.
                </p>
                <div class="flex items-center gap-2">
                    <button @click="handleSSHKeySetup" :disabled="!sshSetupPassword || settingUpSSH"
                        class="btn btn-primary h-fit text-sm">
                        {{ settingUpSSH ? 'Setting up…' : 'Create + Use SSH Key' }}
                    </button>
                    <span v-if="!sshSetupPassword" class="text-xs text-amber-700 dark:text-amber-300">
                        Enter the {{ destUser || 'root' }} password in the Password field above first.
                    </span>
                </div>
                <div v-if="sshSetupError" class="mt-2 text-xs text-red-600 dark:text-red-400">
                    <p class="font-medium">{{ sshSetupError }}</p>
                    <p v-if="sshSetupDetail" class="mt-1 text-red-500 dark:text-red-300">{{ sshSetupDetail }}</p>
                    <button v-if="sshSetupLog" type="button" class="mt-1 underline"
                        @click="showSshSetupLog = !showSshSetupLog">
                        {{ showSshSetupLog ? 'Hide' : 'Show' }} technical details
                    </button>
                    <pre v-if="showSshSetupLog && sshSetupLog"
                        class="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-default/60 p-2 text-[10px] text-default">{{ sshSetupLog }}</pre>
                </div>
            </div>

            <!-- Auto SSH check kicked off by the WireShield hand-off -->
            <div v-if="autoTestingSSH" class="mt-3 flex items-center gap-2">
                <CustomLoadingSpinner :width="'w-5'" :height="'h-5'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'" />
                <span class="text-sm text-muted">Checking connection to {{ destUser || 'root' }}@{{ destHost }}…</span>
            </div>

            <label v-if="!destSelectionBlocked" class="block text-sm mt-3 text-default">Destination Pool</label>
            <div v-if="!destSelectionBlocked && loadingDestPools" class="mt-1 flex items-center gap-2">
                <CustomLoadingSpinner :width="'w-5'" :height="'h-5'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'" />
                <span class="text-sm text-muted">Loading backup server pools…</span>
            </div>
            <select v-else-if="!destSelectionBlocked" v-model="destPool" :disabled="!destHost" :class="[
                'mt-1 block w-full input-textlike text-sm bg-default text-default rounded-md',
                destPoolErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
            ]">
                <option value="">{{ destHost ? 'Select a pool' : 'Enter server address first' }}</option>
                <option v-for="pool in destPools" :key="pool" :value="pool">{{ pool }}</option>
            </select>

            <template v-if="!destSelectionBlocked">
            <label class="block text-sm mt-3 text-default">Destination Dataset</label>
            <div v-if="loadingDestDatasets" class="mt-1 flex items-center gap-2">
                <CustomLoadingSpinner :width="'w-5'" :height="'h-5'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'" />
                <span class="text-sm text-muted">Loading datasets…</span>
            </div>
            <div v-else>
                <div class="flex items-center gap-2 mb-1">
                    <label class="text-xs text-muted">Use existing dataset?</label>
                    <input type="checkbox" v-model="useExistingDest" class="h-3.5 w-3.5 rounded" />
                </div>
                <select v-if="useExistingDest" v-model="destDataset" :disabled="!destPool" :class="[
                    'mt-1 block w-full input-textlike text-sm bg-default text-default rounded-md',
                    destDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]">
                    <option value="">{{ destPool ? 'Select a dataset' : 'Pick a pool first' }}</option>
                    <option v-for="ds in destDatasets" :key="ds" :value="ds">{{ ds }}</option>
                </select>
                <input v-else type="text" v-model="destDataset" :disabled="!destPool" :class="[
                    'mt-1 block w-full input-textlike text-sm bg-default text-default',
                    customDestDatasetErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]" placeholder="New dataset name (created on first run)" />
            </div>
            </template>

            <template #footer>
                <p v-if="autoTestingSSH" class="text-[11px] text-muted">
                    Verifying SSH access to the backup server…
                </p>
                <p v-else-if="sshSetupNeeded" class="text-[11px] text-amber-600 dark:text-amber-400">
                    SSH login must be configured before pools can be loaded.
                </p>
                <p v-else class="text-[11px] text-muted">
                    We'll use SSH to send ZFS snapshots to this server. Make sure passwordless SSH is configured.
                </p>
            </template>
        </SimpleFormCard>

        <!-- Snapshot retention is now configured per-interval in the Schedule modal -->
    </div>

    <!-- ═══ ADVANCED MODE (existing UI) ═══ -->
    <div v-else class="grid grid-flow-cols grid-cols-2 my-2 gap-2 items-stretch">
        <!-- TOP LEFT -->
        <div name="source-data"
            class="border border-default rounded-md p-2 col-span-1 row-start-1 row-span-1 bg-accent h-full">
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

            <!-- Source retention moved to per-interval in Schedule modal -->

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
                                class="flex items-center">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted" />
                            </span>
                            <span
                                class="flex items-center">
                                <ChevronDoubleRightIcon class="w-5 h-5 text-muted" />
                            </span>
                            <span
                                class="flex items-center">
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
            class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent h-full min-h-[34rem]">
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
                    <p v-if="emptyDestState === 'empty'" class="mt-1 text-xs text-muted">
                        This dataset is empty, so the first run will seed it with a full send.
                    </p>
                    <p v-else-if="emptyDestState === 'occupied'" class="mt-1 text-xs text-yellow-500">
                        This dataset has no snapshots but already contains data. A first send has to overwrite it,
                        which needs Allow Overwrite below.
                    </p>
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

            <!-- Destination retention moved to per-interval in Schedule modal -->

            <div v-if="useExistingDest" name="migration-overwrite" class="mt-2 border-t border-default pt-2">
                <div class="flex items-center justify-between">
                    <label class="block text-sm leading-6 text-default">
                        Allow overwrite if no common base or destination is ahead
                    </label>
                    <input type="checkbox" v-model="allowOverwrite" :disabled="forceFullSend"
                        class="h-4 w-4 rounded" :class="{ 'opacity-50 cursor-not-allowed': forceFullSend }" />
                </div>
                <p class="mt-1 text-xs text-default/70">
                    If destination has diverged from the source, enabling this permits rollback with
                    <code>zfs receive -F</code>. Leave off to refuse destructive overwrite.
                </p>
                <p v-if="forceFullSend" class="mt-0.5 text-xs text-yellow-500">
                    Locked on — required by Force Full Resync.
                </p>
                <div class="flex items-center justify-between mt-2">
                    <label class="text-sm leading-6 text-default flex items-center">
                        On resume failure, clear token and continue
                        <InfoTile class="ml-1"
                            :title="`If a resume token exists but the destination changed, this will discard the token and proceed with normal replication. This can trigger a rollback on the destination when overwrite is enabled, which may discard newer snapshots or changes.`" />
                    </label>
                    <input type="checkbox" v-model="resumeFailAllowOverwrite"
                        :disabled="!allowOverwrite || forceFullSend"
                        class="h-4 w-4 rounded" :class="{ 'opacity-50 cursor-not-allowed': !allowOverwrite || forceFullSend }" />
                </div>
                <p class="mt-1 text-xs text-default/70">
                    If a resume token exists but the destination was modified, clear the token and
                    continue with normal replication. If overwrite is allowed, the task may roll back with
                    <code>zfs receive -F</code>.
                </p>
                <p v-if="forceFullSend" class="mt-0.5 text-xs text-yellow-500">
                    Disabled — Force Full Resync destroys all destination snapshots; there is nothing to resume.
                </p>
                <p v-else-if="!allowOverwrite" class="mt-0.5 text-xs text-yellow-500">
                    Requires Allow Overwrite to be enabled.
                </p>
                <div class="flex items-center justify-between mt-2">
                    <label class="text-sm leading-6 text-default flex items-center">
                        Resume stall timeout (seconds)
                        <InfoTile class="ml-1"
                            :title="`If a resumed transfer receives no data for this many seconds, it will be aborted so the next scheduled run can retry. Set to 0 to disable stall detection. Default: 3600 (1 hour).`" />
                    </label>
                    <input type="number" v-model.number="resumeStallTimeout" min="0" step="60"
                        class="w-24 text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="3600" />
                </div>
                <p class="mt-1 text-xs text-default/70">
                    Abort a stalled resume after this many seconds of no data flow. Prevents
                    hung tasks after network outages. Set to 0 to disable.
                </p>
                <div class="flex items-center justify-between mt-2 border-t border-default pt-2">
                    <label class="text-sm leading-6 text-default flex items-center">
                        Force full resync (next run only)
                        <InfoTile class="ml-1"
                            :title="`WARNING: This will destroy ALL existing snapshots on the destination dataset before performing a complete full send. The flag is automatically cleared after a successful transfer. Use this to re-seed the destination after pool recovery or data loss.`" />
                    </label>
                    <input type="checkbox" v-model="forceFullSend" class="h-4 w-4 rounded" />
                </div>
                <p class="mt-1 text-xs text-red-400">
                    Destroys all snapshots on the destination and performs a non-incremental full send
                    on the next run. Automatically disables itself after completion.
                </p>
            </div>
        </div>

        <!-- TOP RIGHT -->
        <div name="destination-ssh-data" class="border border-default rounded-md p-2 col-span-1 bg-accent h-full">
            <div class="grid grid-cols-2">
                <label class="mt-1 col-span-1 block text-base leading-6 text-default">Select Transfer Method</label>
                <select v-model="transferMethod" :disabled="!hasRemoteEndpoint"
                    class="text-default bg-default mt-0 block w-full input-textlike sm:text-sm sm:leading-6"
                    id="method">
                    <option value="ssh">SSH</option>
                    <option value="netcat">Netcat</option>
                    <option value="mbuffer">mBuffer</option>
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
                    <button v-else-if="transferMethod === 'ssh' || transferMethod === 'mbuffer'" @click="handleTestSSH"
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
                <input type="text" v-model="destHost" @input="debouncedDestHostChange()"
                    @blur="commitDestHostChange()" @keyup.enter="commitDestHostChange()" :class="[
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
                    :placeholder="transferMethod === 'netcat' || transferMethod === 'mbuffer' ? 'Enter data port (not 22)' : '22 is default'"
                    @input="validatePort" />
            </div>

            <div v-if="transferMethod === 'mbuffer' && isPull" name="mbuffer-callback-host" class="mt-1">
                <label class="block text-sm leading-6 text-default">mBuffer Callback Host (Optional)</label>
                <input :disabled="remoteFieldsDisabled" type="text" v-model="mbufferCallbackHost"
                    class="mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                    placeholder="Leave blank to auto-detect via SSH client source IP" />
                <p class="mt-1 text-xs text-muted">
                    Use this when pull+mbuffer runs across multi-homed networks and auto-detected callback IP is not reachable.
                </p>
            </div>

            <div v-if="hasRemoteEndpoint" name="ssh-cipher" class="mt-2 border-t border-default pt-2">
                <div class="flex flex-row justify-between items-center">
                    <label class="text-sm leading-6 text-default flex items-center">
                        SSH Cipher
                        <InfoTile class="ml-1"
                            :title="`Encryption algorithm used for the SSH connection. On CPUs with AES-NI, AES-GCM is noticeably faster than the ChaCha20 default that OpenSSH usually negotiates. Leave on Automatic if you are unsure.`" />
                    </label>
                    <ExclamationCircleIcon v-if="sshCipherUnsupportedLocally || sshCipherUnsupportedRemotely"
                        class="mt-1 w-5 h-5 text-danger" />
                </div>
                <select v-model="sshCipher" :class="[
                    'text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6',
                    (sshCipherUnsupportedLocally || sshCipherUnsupportedRemotely) ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                ]" id="ssh-cipher">
                    <option v-for="option in sshCipherOptions" :key="option.value" :value="option.value">
                        {{ option.label }}
                    </option>
                </select>
                <p class="mt-1 text-xs text-muted">{{ selectedSshCipherDetail }}</p>
                <p v-if="sshCipherUnsupportedLocally" class="mt-1 text-xs text-red-400">
                    This server's SSH client does not support {{ sshCipher }}. The transfer will fail to start until
                    you choose another cipher.
                </p>
                <p v-else-if="sshCipherUnsupportedRemotely" class="mt-1 text-xs text-red-400">
                    {{ destHost }} does not offer {{ sshCipher }}. The connection will be refused with "no matching
                    cipher found".
                </p>
                <p v-else-if="sshCipherProbeError" class="mt-1 text-xs text-yellow-500">
                    {{ sshCipherProbeError }} Availability could not be verified.
                </p>
                <p v-if="sshCipher && !sshCipherAffectsThroughput" class="mt-1 text-xs text-yellow-500">
                    With {{ transferMethod }}, only the control channel is encrypted. The bulk data stream bypasses
                    SSH entirely, so this setting will not change transfer speed.
                </p>
            </div>
        </div>

        <!-- BOTTOM RIGHT -->
        <div name="send-options"
            class="border border-default rounded-md p-2 col-span-1 row-span-1 row-start-2 bg-accent h-full min-h-[34rem]">
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
            <p v-if="showRecursiveHistoryRecommendation" class="mt-1 text-xs text-yellow-500">
                Recommendation: if this destination should preserve restore history, enable Include Intermediate
                Snapshots.
            </p>
            <div name="send-opt-include-intermediates" class="flex flex-row items-center gap-2 mt-2">
                <label class="block text-sm leading-6 text-default">Include Intermediate Snapshots</label>
                <input type="checkbox" v-model="includeIntermediateSnapshots" class="h-4 w-4 rounded" />
            </div>
            <p class="text-xs text-muted">
                Replicate every snapshot created since the last common snapshot. Disable to send only the newest
                snapshot state.
            </p>
            <p v-if="useExistingDest && includeIntermediatesApplicability === 'no-common-base'" class="text-xs text-yellow-500">
                No common base detected for this destination right now, so this option will not affect the current run.
                It will apply automatically once a common snapshot exists.
            </p>
            <p v-if="useExistingDest && includeIntermediatesApplicability === 'empty-destination'" class="text-xs text-yellow-500">
                Destination has no snapshots yet, so there is no incremental chain for intermediate snapshots to apply to on this run.
            </p>
            <p v-if="useExistingDest && includeIntermediatesApplicability === 'applicable-untagged-base'" class="text-xs text-yellow-500">
                This task owns no snapshots on the destination yet. It will replicate incrementally from a snapshot the
                two datasets already share.
            </p>
            <p class="mt-1 text-xs text-muted">
                Encryption note: for recursive hierarchies with encrypted datasets, choose an explicit encryption
                strategy (raw stream to preserve source encryption, or non-raw behavior) and avoid mixing raw and
                non-raw incremental chains.
            </p>
            <p v-if="showRecursiveOverwriteWarning" class="mt-1 text-xs text-red-400">
                Warning: Recursive send combined with overwrite behavior (<code>zfs receive -F</code>) can remove
                destination snapshots and child datasets that do not exist on the source.
            </p>
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
                    ]" placeholder="Name is CustomName + Timestamp" />
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
            <div v-if="transferMethod === 'mbuffer'" class="grid grid-cols-2 mt-2">
                <div name="send-opt-mbuffer-block" class="col-span-1">
                    <label class="block text-sm leading-6 text-default">mBuffer Block Size</label>
                    <input :disabled="remoteFieldsDisabled" type="number" v-model="mbufferBlockSize" min="1"
                        class="mt-0.5 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default"
                        placeholder="256" />
                </div>
                <div name="send-opt-mbuffer-block" class="col-span-1">
                    <div name="send-opt-mbuffer-block-unit">
                        <label class="block text-sm leading-6 text-default">mBuffer Block Unit</label>
                        <select :disabled="remoteFieldsDisabled" v-model="mbufferBlockUnit"
                            class="text-default bg-default mt-0.5 block w-full input-textlike sm:text-sm sm:leading-6">
                            <option value="b">b</option>
                            <option value="k">k</option>
                            <option value="M">M</option>
                            <option value="G">G</option>
                        </select>
                    </div>
                </div>
            </div>
            <p v-if="transferMethod === 'mbuffer'" class="mt-1 text-xs text-muted">
                Block size maps to <code>mbuffer -s</code>; memory size maps to <code>mbuffer -m</code>.
            </p>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, Ref, onMounted, watch, inject, computed } from 'vue';
import { ExclamationCircleIcon, ChevronDoubleRightIcon, ArrowPathIcon, EyeIcon, EyeSlashIcon } from '@heroicons/vue/24/outline';
import { Switch } from '@headlessui/vue';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import SimpleFormCard from '../../simple/SimpleFormCard.vue';
import { useWireShieldInstalled, WIRESHIELD_MISSING_MESSAGE } from '../../../composables/useWireShieldInstalled';
import {
    ParameterNode,
    ZfsDatasetParameter,
    IntParameter,
    StringParameter,
    BoolParameter,
    SelectionOption,
    SelectionParameter
} from '../../../models/Parameters';
import {
    getPoolData,
    getDatasetData,
    testSSH,
    testOrSetupSSH,
    testNetcat,
    getSshCiphers,
    mostRecentCommonSnapshot,
    listSnapshots,
    datasetUsedBytes,
    filterTaskSnapshots,
    filterDatasetSnapshots,
    ZfsSnap,
    destAheadOfCommon,
    validateHostname
} from '../../../composables/utility';
import { SSH_CIPHER_OPTIONS } from '../../../models/SshCiphers';
import { pushNotification, Notification } from '@45drives/houston-common-ui';

interface ZfsRepTaskParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
    simple?: boolean;
}

const props = defineProps<ZfsRepTaskParamsProps>();
const taskForEditing = inject<Ref<TaskInstanceType | null>>('task-for-editing', ref(null));
const draftTaskName = inject<Ref<string>>('task-name-draft', ref(''));

function sanitizeTaskName(name: string): string {
    let out = (name || '').replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '');
    if (out.startsWith('_')) out = `task${out}`;
    return out;
}

const effectiveTaskName = computed(() => {
    const explicit = props.task?.name || taskForEditing.value?.name || draftTaskName.value || '';
    return sanitizeTaskName(explicit);
});

const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const injectedVpnHost = inject<import('vue').Ref<string | null>>('vpnHost', ref(null));
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

// SSH key auto-setup state
const sshSetupNeeded = ref(false);
const sshSetupPassword = ref('');
const settingUpSSH = ref(false);
const sshSetupError = ref('');
const sshSetupDetail = ref('');
const sshSetupLog = ref('');
const showSshSetupLog = ref(false);
const showSshSetupPassword = ref(false);
const autoTestingSSH = ref(false);

// Pools/datasets can't be trusted until the SSH gate resolves
const destSelectionBlocked = computed(() => sshSetupNeeded.value || autoTestingSSH.value);

const directionSwitched = ref(false);
const allowOverwrite = ref(false);
const resumeFailAllowOverwrite = ref(false);
const resumeStallTimeout = ref(3600);
const forceFullSend = ref(false);

// --- Mutual exclusivity constraints ---
// Force Full Send requires Allow Overwrite (it uses -F and destroys snapshots)
watch(forceFullSend, (val) => {
    if (val) {
        allowOverwrite.value = true;
        resumeFailAllowOverwrite.value = false;
    }
});
// Disabling Allow Overwrite disables options that depend on it
watch(allowOverwrite, (val) => {
    if (!val) {
        forceFullSend.value = false;
        resumeFailAllowOverwrite.value = false;
    }
});
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
const sendCompressed = ref(true);
const sendRecursive = ref(false);
const includeIntermediateSnapshots = ref(false);
const mbufferSize = ref(1);
const mbufferUnit = ref('G');
const mbufferBlockSize = ref(256);
const mbufferBlockUnit = ref('k');
const mbufferCallbackHost = ref('');
const useCustomName = ref(false);
const customName = ref('');
const customNameErrorTag = ref(false);

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

/* ---------------- SSH cipher selection ---------------- */

const sshCipherOptions = SSH_CIPHER_OPTIONS;
const sshCipher = ref('');
const localSshCiphers = ref<string[]>([]);
const remoteSshCiphers = ref<string[]>([]);
const sshCipherProbeError = ref('');

const selectedSshCipherDetail = computed(() =>
    sshCipherOptions.find(option => option.value === sshCipher.value)?.detail ?? ''
);

const sshCipherUnsupportedLocally = computed(() =>
    !!sshCipher.value && localSshCiphers.value.length > 0 && !localSshCiphers.value.includes(sshCipher.value)
);

const sshCipherUnsupportedRemotely = computed(() =>
    !!sshCipher.value && remoteSshCiphers.value.length > 0 && !remoteSshCiphers.value.includes(sshCipher.value)
);

// The bulk stream only rides the SSH channel for the 'ssh' method; netcat and mbuffer
// move data over a plain socket, so the cipher there covers control traffic only.
const sshCipherAffectsThroughput = computed(() => transferMethod.value === 'ssh');

async function refreshSshCipherAvailability() {
    const host = destHost.value.trim();
    const result = await getSshCiphers(host, (destUser.value || 'root').trim(), destPort.value);
    localSshCiphers.value = result.local;
    remoteSshCiphers.value = result.remote;
    sshCipherProbeError.value = host ? result.remoteError : '';
}

const errorList = inject<Ref<string[]>>('errors')!;

const sshReady = ref(false);
const includeIntermediatesApplicability = ref<'unknown' | 'applicable' | 'applicable-untagged-base' | 'no-common-base' | 'empty-destination'>('unknown');
// Matches EMPTY_DEST_MAX_BYTES in the replication script.
const EMPTY_DEST_MAX_BYTES = 1024 * 1024;
const emptyDestState = ref<'unknown' | 'empty' | 'occupied'>('unknown');

const canEvaluateIncludeIntermediates = computed(() => {
    if (!useExistingDest.value) return false;
    if (!sourcePool.value || !sourceDataset.value || !destPool.value || !destDataset.value) return false;
    if (isPull.value && !destHost.value) return false;
    return true;
});

const showRecursiveHistoryRecommendation = computed(() => {
    return sendRecursive.value && !includeIntermediateSnapshots.value;
});

const showRecursiveOverwriteWarning = computed(() => {
    return useExistingDest.value && sendRecursive.value && (allowOverwrite.value || forceFullSend.value);
});

/* ---------------- Direction-aware labels + behavior ---------------- */

const isPull = computed(() => directionSwitched.value);

const remoteEndpointLabel = computed(() => (isPull.value ? 'Remote Source' : 'Remote Target'));
const sourceCardLabel = computed(() => (isPull.value ? 'Remote Source Location' : 'Source Location'));
const targetCardLabel = computed(() => (isPull.value ? 'Local Target Location' : 'Target Location'));

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
    if (!on) {
        includeIntermediatesApplicability.value = 'unknown';
        allowOverwrite.value = false;
        resumeFailAllowOverwrite.value = false;
        resumeStallTimeout.value = 3600;
        forceFullSend.value = false;
        destDatasetErrorTag.value = false;
    }
});

watch(
    [
        useExistingDest,
        canEvaluateIncludeIntermediates,
        sourcePool,
        sourceDataset,
        destPool,
        destDataset,
        destHost,
        destUser,
        destPort,
        transferMethod,
        directionSwitched,
        useCustomName,
        customName,
    ],
    async () => {
        if (!useExistingDest.value) {
            includeIntermediatesApplicability.value = 'unknown';
            return;
        }
        if (!canEvaluateIncludeIntermediates.value) {
            includeIntermediatesApplicability.value = 'unknown';
            return;
        }
        await checkDestDatasetContents();
    }
);

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

    // Clearing the host also drops the WireShield value and the one-time SSH setup gate
    if (injectedVpnHost.value) injectedVpnHost.value = null;
    try { localStorage.removeItem('scheduler-vpn-host'); } catch { /* ignore */ }
    sshSetupNeeded.value = false;
    sshSetupPassword.value = '';
    sshSetupError.value = '';
    settingUpSSH.value = false;
    testingSSH.value = false;
    autoTestingSSH.value = false;
    sshReady.value = false;
    destHostErrorTag.value = false;

    if (isPull.value) {
        sourcePool.value = '';
        sourceDataset.value = '';
        sourcePools.value = [];
        sourceDatasets.value = [];
    } else {
        destPool.value = '';
        destDataset.value = '';
        destPools.value = [];
        destDatasets.value = [];
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

watch(transferMethod, (newValue) => {
    if ((newValue === 'netcat' || newValue === 'mbuffer') && destPort.value === 22) {
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

        const resumeStallTimeoutParam = sendOptionsParams.find(p => p.key === 'resumeStallTimeout');
        resumeStallTimeout.value = resumeStallTimeoutParam ? Number(resumeStallTimeoutParam.value) || 3600 : 3600;

        const forceFullSendParam = sendOptionsParams.find(p => p.key === 'forceFullSend');
        forceFullSend.value = forceFullSendParam ? !!forceFullSendParam.value : false;

        const useExistingDestParam = sendOptionsParams.find(p => p.key === 'useExistingDest');
        useExistingDest.value = useExistingDestParam ? !!useExistingDestParam.value : false;

        const sshCipherParam = sendOptionsParams.find(p => p.key === 'sshCipher');
        sshCipher.value = sshCipherParam ? String(sshCipherParam.value || '') : '';

        sendCompressed.value = sendOptionsParams.find(p => p.key === 'compressed_flag')!.value;
        sendRaw.value = sendOptionsParams.find(p => p.key === 'raw_flag')!.value;
        sendRecursive.value = sendOptionsParams.find(p => p.key === 'recursive_flag')!.value;
        const includeIntermediatesParam = sendOptionsParams.find(p => p.key === 'includeIntermediateSnapshots');
        includeIntermediateSnapshots.value = includeIntermediatesParam ? !!includeIntermediatesParam.value : true;
        mbufferSize.value = sendOptionsParams.find(p => p.key === 'mbufferSize')!.value;
        mbufferUnit.value = sendOptionsParams.find(p => p.key === 'mbufferUnit')!.value;
        const mbufferBlockSizeParam = sendOptionsParams.find(p => p.key === 'mbufferBlockSize');
        mbufferBlockSize.value = mbufferBlockSizeParam ? Number(mbufferBlockSizeParam.value) || 256 : 256;
        const mbufferBlockUnitParam = sendOptionsParams.find(p => p.key === 'mbufferBlockUnit');
        mbufferBlockUnit.value = mbufferBlockUnitParam ? String(mbufferBlockUnitParam.value || 'k') : 'k';
        const mbufferCallbackHostParam = sendOptionsParams.find(p => p.key === 'mbufferCallbackHost');
        mbufferCallbackHost.value = mbufferCallbackHostParam ? String(mbufferCallbackHostParam.value || '') : '';
        useCustomName.value = sendOptionsParams.find(p => p.key === 'customName_flag')!.value;
        customName.value = sendOptionsParams.find(p => p.key === 'customName')!.value;

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

        initialParameters.value = JSON.parse(JSON.stringify(formSnapshot()));

        loading.value = false;
    } else {
        await getSourcePools();
        await getTargetPools();
    }
}

/* ---------------- Change detection ---------------- */

// Baseline and current state must come from the same builder — a key set or ordering
// mismatch between the two makes the JSON comparison report a change every time.
function formSnapshot() {
    return {
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
        includeIntermediateSnapshots: includeIntermediateSnapshots.value,
        mbufferSize: mbufferSize.value,
        mbufferUnit: mbufferUnit.value,
        mbufferBlockSize: mbufferBlockSize.value,
        mbufferBlockUnit: mbufferBlockUnit.value,
        mbufferCallbackHost: mbufferCallbackHost.value,
        useCustomName: useCustomName.value,
        customName: customName.value,
        transferMethod: transferMethod.value,
        allowOverwrite: allowOverwrite.value,
        resumeFailAllowOverwrite: resumeFailAllowOverwrite.value,
        resumeStallTimeout: resumeStallTimeout.value,
        useExistingDest: useExistingDest.value,
        forceFullSend: forceFullSend.value,
    };
}

function hasChanges() {
    return JSON.stringify(formSnapshot()) !== JSON.stringify(initialParameters.value);
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
    const wrapped = function (...args: any[]) {
        if (timerId) clearTimeout(timerId);
        timerId = setTimeout(() => func(...args), delay);
    };
    wrapped.cancel = () => {
        if (timerId) clearTimeout(timerId);
        timerId = undefined;
    };
    return wrapped;
}

const IPV4_RE = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;
const FQDN_RE = /^(?=.{1,253}$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))+$/;

// While typing we only probe hosts that already look complete; partial input like "h" or
// "192.168." would otherwise trigger a failed SSH lookup on every keystroke.
function hostLooksComplete(host: string) {
    const h = host.trim();
    if (!h) return false;
    if (/^[\d.]+$/.test(h)) return IPV4_RE.test(h);
    return FQDN_RE.test(h);
}

let lastProbedHost = '';

const handleDestHostChange = async () => {
    lastProbedHost = destHost.value.trim();
    if (isPull.value) {
        // Pull mode: host is the source — only refresh source pools
        await getSourcePools();
        sourcePool.value = '';
        sourceDataset.value = '';
    } else {
        // Push mode: host is the target — only refresh target pools
        await getTargetPools();
        destPool.value = '';
        destDataset.value = '';
    }
    await refreshSshCipherAvailability();
};

const debouncedInner = debounce(handleDestHostChange, 800);

const debouncedDestHostChange = () => {
    const h = destHost.value.trim();
    if (!hostLooksComplete(h) || h === lastProbedHost) {
        debouncedInner.cancel();
        return;
    }
    debouncedInner();
};

// Blur/Enter commits whatever the user typed, including single-label hostnames.
const commitDestHostChange = async () => {
    debouncedInner.cancel();
    const h = destHost.value.trim();
    if (!h || h === lastProbedHost) return;
    await handleDestHostChange();
};

/* ---------------- Direction-aware list loading ---------------- */

const getSourcePools = async () => {
    loadingSourcePools.value = true;
    try {
        if (sourceIsRemote.value) {
            if (!destHost.value) {
                sourcePools.value = [];
                return;
            }
            const portToUse = (transferMethod.value === 'netcat' || transferMethod.value === 'mbuffer') ? '22' : String(destPort.value);
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
            const portToUse = (transferMethod.value === 'netcat' || transferMethod.value === 'mbuffer') ? '22' : String(destPort.value);
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
        let result;
        if (targetIsRemote.value) {
            const portToUse = (transferMethod.value === 'netcat' || transferMethod.value === 'mbuffer') ? '22' : String(destPort.value);
            result = await getPoolData(destHost.value, portToUse, destUser.value);
        } else {
            result = await getPoolData();
        }
        destPools.value = result ?? [];
        if (!result || (Array.isArray(result) && result.length === 0)) {
            if (targetIsRemote.value && destHost.value) {
                pushNotification(new Notification(
                    'Could not load remote pools',
                    `Failed to retrieve ZFS pools from ${destHost.value}. Check that passwordless SSH is configured and ZFS is installed on the target.`,
                    'warning',
                    8000
                ));
            }
        }
    } catch (err) {
        destPools.value = [];
        if (targetIsRemote.value && destHost.value) {
            pushNotification(new Notification(
                'Connection Failed',
                `Could not connect to ${destHost.value}. Ensure the server is reachable and SSH is configured.`,
                'error',
                8000
            ));
        }
    } finally {
        loadingDestPools.value = false;
    }
};

const getTargetDatasets = async () => {
    loadingDestDatasets.value = true;
    try {
        if (targetIsRemote.value) {
            const portToUse = (transferMethod.value === 'netcat' || transferMethod.value === 'mbuffer') ? '22' : String(destPort.value);
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

// If transfer method changes, adjust port default (netcat uses a data port, not SSH port)
watch(transferMethod, (newValue) => {
    if ((newValue === 'netcat' || newValue === 'mbuffer') && destPort.value === 22) {
        destPort.value = 31337;
    }
});

/* ---------------- Validation ---------------- */

function validateHost() {
    if ((isPull.value || props.simple) && destHost.value === "") {
        errorList.value.push("A destination server address is required.");
        destHostErrorTag.value = true;
        return;
    }

    if (destHost.value !== "") {
        if (destHost.value.length < 1 || destHost.value.length > 253) {
            errorList.value.push("Hostname must be between 1 and 253 characters in length.");
            destHostErrorTag.value = true;
        }
        if (!validateHostname(destHost.value)) {
            errorList.value.push("Hostname must only contain ASCII letters (a-z, case-insensitive), digits (0-9), and hyphens ('-'), with no trailing dot.");
            destHostErrorTag.value = true;
        }
    }
}

function validatePort() {
    if (destPort.value == 22 && (transferMethod.value == 'netcat' || transferMethod.value == 'mbuffer') && destHost.value != '') {
        errorList.value.push("Port 22 is not allowed for Netcat or mBuffer transfer. Please choose a different data port.");
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

function normalizeDatasetNameForPool(poolName: string, datasetName: string): string {
    const pool = (poolName || '').trim();
    let ds = (datasetName || '').trim();
    if (!ds) return ds;
    ds = ds.replace(/^\/+/, '').replace(/\/+$/, '');
    if (!pool) return ds;
    if (ds === pool) return '';
    if (ds.startsWith(`${pool}/`)) return ds.slice(pool.length + 1);
    return ds;
}

// Mirrors join_zfs_path() in the replication script: the dataset selector already
// returns pool-qualified names, so blind concatenation yields pool/pool/dataset.
function joinZfsPath(poolName: string, datasetName: string): string {
    const pool = (poolName || '').trim();
    const ds = (datasetName || '').trim().replace(/^\/+/, '').replace(/\/+$/, '');
    if (!pool) return ds;
    if (!ds) return pool;
    if (ds === pool || ds.startsWith(`${pool}/`)) return ds;
    return `${pool}/${ds}`;
}

function datasetExistsInPool(poolName: string, datasetName: string, datasets: string[]): boolean {
    const raw = (datasetName || '').trim();
    const normalized = normalizeDatasetNameForPool(poolName, raw);
    if (!raw) return false;

    return datasets.some((existing) => {
        const existingRaw = (existing || '').trim();
        if (!existingRaw) return false;
        const existingNormalized = normalizeDatasetNameForPool(poolName, existingRaw);
        return existingRaw === raw || existingRaw === normalized || existingNormalized === raw || existingNormalized === normalized;
    });
}

async function validateDestination() {
    if (destPool.value === '') {
        errorList.value.push("Destination pool is needed.");
        destPoolErrorTag.value = true;
    } else if (!doesItExist(destPool.value, destPools.value)) {
        errorList.value.push("Destination pool does not exist.");
        customDestPoolErrorTag.value = true;
    }

    // Refresh the dataset inventory so "new dataset" checks are authoritative.
    if (destPool.value) {
        try {
            await getTargetDatasets();
        } catch (err) {
            console.error('validateDestination:getTargetDatasets', err);
            errorList.value.push("Failed to refresh destination datasets for validation.");
            destDatasetErrorTag.value = true;
            return;
        }
    }

    if (useExistingDest.value) {
        if (destDataset.value === '') {
            errorList.value.push("Destination dataset is needed.");
            destDatasetErrorTag.value = true;
            return;
        }
        if (!datasetExistsInPool(destPool.value, destDataset.value, destDatasets.value)) {
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
    if (datasetExistsInPool(destPool.value, destDataset.value, destDatasets.value)) {
        errorList.value.push("That dataset already exists. Choose 'Existing Dataset' or use a new path.");
        customDestDatasetErrorTag.value = true;
        return;
    }
}

/* ---------------- Direction-aware preflight check ---------------- */

async function checkDestDatasetContents() {
    if (!useExistingDest.value) return;

    try {
        includeIntermediatesApplicability.value = 'unknown';
        emptyDestState.value = 'unknown';
        const srcFs = joinZfsPath(sourcePool.value, sourceDataset.value);
        const dstFs = joinZfsPath(destPool.value, destDataset.value);

        const portToUse = (transferMethod.value === "netcat" || transferMethod.value === "mbuffer") ? "22" : String(destPort.value);

        let srcSnaps: ZfsSnap[] = [];
        let dstSnaps: ZfsSnap[] = [];

        if (isPull.value) {
            if (!destHost.value) {
                errorList.value.push("Host is required for pull replication.");
                destHostErrorTag.value = true;
                destDatasetErrorTag.value = true;
                return;
            }
            [srcSnaps, dstSnaps] = await Promise.all([
                listSnapshots(srcFs, destUser.value, destHost.value, portToUse),
                listSnapshots(dstFs),
            ]);
        } else {
            [srcSnaps, dstSnaps] = await Promise.all([
                listSnapshots(srcFs),
                destHost.value
                    ? listSnapshots(dstFs, destUser.value, destHost.value, portToUse)
                    : listSnapshots(dstFs),
            ]);
        }

        const taskName = effectiveTaskName.value;
        const customScope = useCustomName.value ? customName.value : '';

        // Mirrors _plan_send(): any snapshot shared by both sides is a valid incremental
        // base, task-owned or not.
        const srcRoot = filterDatasetSnapshots(srcSnaps, srcFs);
        const dstRoot = filterDatasetSnapshots(dstSnaps, dstFs);
        srcSnaps = srcRoot;
        dstSnaps = dstRoot;

        if (!dstSnaps.length) {
            includeIntermediatesApplicability.value = 'empty-destination';
            const used = isPull.value || !destHost.value
                ? await datasetUsedBytes(dstFs)
                : await datasetUsedBytes(dstFs, destUser.value, destHost.value, portToUse);
            if (used === null) {
                emptyDestState.value = 'unknown';
                destDatasetErrorTag.value = false;
                return;
            }
            if (used > EMPTY_DEST_MAX_BYTES) {
                emptyDestState.value = 'occupied';
                if (!allowOverwrite.value) {
                    errorList.value.push("Destination has no snapshots but already contains data. A first send must overwrite it: enable 'Allow overwrite', or pick an empty/new destination.");
                    destDatasetErrorTag.value = true;
                    return;
                }
                destDatasetErrorTag.value = false;
                return;
            }
            emptyDestState.value = 'empty';
            destDatasetErrorTag.value = false;
            return;
        }

        emptyDestState.value = 'unknown';

        const common = mostRecentCommonSnapshot(srcSnaps, dstSnaps);

        if (!common) {
            includeIntermediatesApplicability.value = 'no-common-base';
            if (allowOverwrite.value) {
                destDatasetErrorTag.value = false;
                return;
            }
            errorList.value.push("No common snapshot found. Enable 'Allow overwrite' or choose an empty/new destination.");
            destDatasetErrorTag.value = true;
            return;
        }

        includeIntermediatesApplicability.value = taskName && !filterTaskSnapshots(dstRoot, taskName, customScope).length
            ? 'applicable-untagged-base'
            : 'applicable';

        const diverged = destAheadOfCommon(srcSnaps, dstSnaps, common);
        if (diverged && !allowOverwrite.value) {
            errorList.value.push("Destination has newer snapshots than the common base. Enable 'Allow overwrite' to roll back, or pick a new destination.");
            destDatasetErrorTag.value = true;
            return;
        }

        destDatasetErrorTag.value = false;
    } catch (err) {
        console.error("checkDestDatasetContents:", err);
        includeIntermediatesApplicability.value = 'unknown';
        emptyDestState.value = 'unknown';
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
    await validateDestination();
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
    if (tm !== 'netcat' && tm !== 'ssh' && tm !== 'local' && tm !== 'mbuffer') tm = 'ssh';

    const newParams = new ParameterNode("ZFS Replication Task Config", "zfsRepConfig")
        .addChild(new ZfsDatasetParameter('Source Dataset', 'sourceDataset', '', 0, '', sourcePool.value, sourceDataset.value))
        .addChild(new ZfsDatasetParameter('Destination Dataset', 'destDataset', destHost.value, destPort.value, destUser.value, destPool.value, destDataset.value))
        .addChild(new SelectionParameter('Direction', 'direction', transferDirection.value))
        .addChild(new ParameterNode('Send Options', 'sendOptions')
            .addChild(new BoolParameter('Compressed', 'compressed_flag', sendCompressed.value))
            .addChild(new BoolParameter('Raw', 'raw_flag', sendRaw.value))
            .addChild(new BoolParameter('Recursive', 'recursive_flag', sendRecursive.value))
            .addChild(new BoolParameter('Include Intermediate Snapshots', 'includeIntermediateSnapshots', includeIntermediateSnapshots.value))
            .addChild(new IntParameter('MBuffer Size', 'mbufferSize', mbufferSize.value))
            .addChild(new StringParameter('MBuffer Unit', 'mbufferUnit', mbufferUnit.value))
            .addChild(new IntParameter('MBuffer Block Size', 'mbufferBlockSize', mbufferBlockSize.value))
            .addChild(new StringParameter('MBuffer Block Unit', 'mbufferBlockUnit', mbufferBlockUnit.value))
            .addChild(new StringParameter('MBuffer Callback Host', 'mbufferCallbackHost', mbufferCallbackHost.value))
            .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', useCustomName.value))
            .addChild(new StringParameter('Custom Name', 'customName', customName.value))
            .addChild(new StringParameter('Transfer Method', 'transferMethod', tm))
            .addChild(new StringParameter('SSH Cipher', 'sshCipher', sshCipher.value))
            .addChild(new BoolParameter('Allow Overwrite', 'allowOverwrite', allowOverwrite.value))
            .addChild(new BoolParameter('Resume Fail Allow Overwrite', 'resumeFailAllowOverwrite', resumeFailAllowOverwrite.value))
            .addChild(new IntParameter('Resume Stall Timeout', 'resumeStallTimeout', resumeStallTimeout.value))
            .addChild(new BoolParameter('Use Existing Destination', 'useExistingDest', useExistingDest.value))
            .addChild(new BoolParameter('Force Full Send', 'forceFullSend', forceFullSend.value))
        );

    parameters.value = newParams;
}

/* ---------------- WireShield ---------------- */

const emit = defineEmits<{ 'open-wireshield': [] }>();

const { wireShieldMissing } = useWireShieldInstalled();
const wireShieldMissingMessage = WIRESHIELD_MISSING_MESSAGE;

function openWireShield() {
    if (wireShieldMissing.value) return;
    setParams(); // sync current form values to the shared parameters ref
    emit('open-wireshield');
}

/* ---------------- Test buttons ---------------- */

async function handleTestSSH() {
    if (transferMethod.value !== 'ssh' && transferMethod.value !== 'mbuffer') return;

    testingSSH.value = true;
    try {
        const host = destHost.value.trim();
        const user = (destUser.value || 'root').trim();

        // In pull mode host is required; in push mode blank host is allowed (local).
        if (isPull.value && !host) {
            pushNotification(new Notification(
                'Host Required',
                'Host is required for pull replication.',
                'error',
                6000
            ));
            sshReady.value = false;
            return;
        }

        // Quick test — if passwordless SSH already works, we're done
        const ok = host ? await testSSH(`${user}@${host}`) : true;
        if (ok) {
            pushNotification(new Notification('Connection Successful!', 'Passwordless SSH connection established.', 'success', 6000));
            sshReady.value = true;
            sshSetupNeeded.value = false;
            if (host) await getTargetPools();
            return;
        }

        // SSH failed — show the password setup prompt instead of silently attempting
        sshSetupNeeded.value = true;
        sshReady.value = false;
    } finally {
        testingSSH.value = false;
    }
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
    if (props.simple) {
        // Simple mode: always push, always SSH, sensible defaults
        directionSwitched.value = false;
        transferMethod.value = 'ssh';
        destUser.value = 'root';
        destPort.value = 22;
    }
    await initializeData();
    await refreshSshCipherAvailability();

    // Apply VPN host from WireShield if provided
    if (injectedVpnHost.value) {
        destHost.value = injectedVpnHost.value;
        await autoTestAndSetupSSH();
    }
});

const debouncedCipherRefresh = debounce(refreshSshCipherAvailability, 800);
watch([destUser, destPort], () => {
    if (!destHost.value.trim()) return;
    debouncedCipherRefresh();
});

// Watch for vpnHost arriving after mount (e.g., from storage event while iframe was hidden)
watch(() => injectedVpnHost.value, async (newHost) => {
    if (newHost) {
        destHost.value = newHost;
        await autoTestAndSetupSSH();
    }
});

// Auto-test SSH when VPN host is set; show password prompt if it fails
async function autoTestAndSetupSSH() {
    const host = destHost.value?.trim();
    if (!host) return;
    const user = (destUser.value || 'root').trim();
    
    // Reset testing state in case it was stuck from a previous hang
    testingSSH.value = true;
    autoTestingSSH.value = true;

    try {
        const ok = await testSSH(`${user}@${host}`);
        if (ok) {
            sshSetupNeeded.value = false;
            await getTargetPools();
        } else {
            sshSetupNeeded.value = true;
        }
    } catch {
        sshSetupNeeded.value = true;
    } finally {
        testingSSH.value = false;
        autoTestingSSH.value = false;
    }
}

// Handle one-time SSH key setup with password
async function handleSSHKeySetup() {
    settingUpSSH.value = true;
    sshSetupError.value = '';
    sshSetupDetail.value = '';
    sshSetupLog.value = '';
    showSshSetupLog.value = false;
    try {
        const res = await testOrSetupSSH({
            host: destHost.value.trim(),
            user: (destUser.value || 'root').trim(),
            port: destPort.value || 22,
            password: sshSetupPassword.value,
            onEvent: ({ type, title, message }) => {
                pushNotification(new Notification(title, message, type, 8000));
            }
        });
        if (res.success) {
            sshSetupNeeded.value = false;
            sshSetupError.value = '';
            sshSetupPassword.value = '';
            await getTargetPools();
        } else {
            sshSetupError.value = res.message || 'SSH setup failed. Check the password and try again.';
            sshSetupDetail.value = res.detail || '';
            sshSetupLog.value = formatSshDiagnostics(res.details);
        }
    } catch (err: any) {
        sshSetupError.value = err?.message || 'Unexpected error during SSH setup.';
    } finally {
        settingUpSSH.value = false;
    }
}

// Flatten the helper script's step list into something a support tech can read
function formatSshDiagnostics(data: any): string {
    if (!data) return '';
    const lines: string[] = [];
    if (data.reason) lines.push(`reason: ${data.reason}`);
    if (data.local_user) lines.push(`running as: ${data.local_user} (keys in ${data.key_dir})`);
    if (data.sshpass_available === false) lines.push('sshpass: not installed (used SSH_ASKPASS fallback)');
    for (const s of data.steps || []) {
        lines.push(`[${s.ok ? 'ok' : 'fail'}] ${s.step}${s.detail ? ` — ${s.detail}` : ''}`);
    }
    return lines.join('\n');
}

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges,
    setParams,
    initializing: loading
});
</script>
