<template>
    <Modal @close="closeModal" :isOpen="showManageRemotes" :margin-top="'mt-14'" :width="'w-6/12'"
        :min-width="'min-w-3/5'" :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="false"
        :closeConfirm="closeBtn">
        <template v-slot:title>
            Manage Rclone Remotes
        </template>
        <template v-slot:content>
            <div v-if="loading" class="flex items-center justify-center">
                <CustomLoadingSpinner :width="'w-32'" :height="'h-32'" :baseColor="'text-gray-200'"
                    :fillColor="'fill-gray-500'" />
            </div>
            <!-- <div v-else-if="existingRemotes.length === 0"
                class="my-2 py-4 min-w-full min-h-full items-center text-center bg-well">
                <h2>No Remotes Found</h2>
            </div> -->
            <div v-else class="text-default">
                <div id="remotes-list" class="border-2 p-2 border-default rounded-md bg-well">
                    <h2 class="text-base font-medium text-default">Select Remote</h2>
                    <ul role="list" class="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2 sm:gap-2 lg:grid-cols-4">
                        <li v-if="existingRemotes.length > 0" v-for="remote in existingRemotes" :key="remote.name"
                            class="col-span-1 flex rounded-md shadow-sm">
                            <button @click.stop="selectRemoteBtn(remote)" @mouseenter="handleMouseEnter(remote.name)"
                                @mouseleave="handleMouseLeave(remote.name)"
                                class="flex flex-row items-center text-center h-fit w-full mt-1 btn text-default"
                                :style="getButtonStyles(isHovered(remote.name), undefined, remote)"
                                :title="remote.name">
                                <div class="rounded-full bg-white w-5 h-5">
                                    <img :src="getProviderLogo(undefined, remote)" alt="provider-logo"
                                        class="inline-block w-4 h-4" />
                                </div>
                                <div class="flex-grow px-2 py-2 text-sm" :class="truncateText">
                                    {{ remote.name }}
                                </div>
                            </button>
                        </li>
                        <li v-else>
                            <button @click.stop="selectRemoteBtn(dummyRemote)"
                                @mouseenter="handleMouseEnter(dummyRemote.name)"
                                @mouseleave="handleMouseLeave(dummyRemote.name)"
                                class="flex flex-row items-center text-center h-fit w-full mt-1 btn text-default"
                                :style="getButtonStyles(isHovered(dummyRemote.name), undefined, dummyRemote)"
                                :title="dummyRemote.name">
                                <div class="rounded-full bg-white w-5 h-5">
                                    <img :src="getProviderLogo(undefined, dummyRemote)" alt="provider-logo"
                                        class="inline-block w-4 h-4" />
                                </div>
                                <div class="flex-grow px-2 py-2 text-sm" :class="truncateText">
                                    {{ dummyRemote.name }}
                                </div>
                            </button>
                        </li>
                    </ul>
                </div>
                <div v-if="!selectedRemote" class="mt-4 border rounded-md border-default p-2 bg-well">
                    Please select a remote.
                </div>
                <div v-if="selectedRemote" class="mt-2 border rounded-md border-default p-2 bg-well">
                    <div name="remote-name">
                        <div class="flex flex-row justify-between items-center">
                            <div class="flex flex-row justify-between items-center">
                                <label class="block text-sm leading-6 text-default">Remote Name</label>
                                <InfoTile v-if="editMode" class="ml-1"
                                    title="Name can have letters, numbers, underscore (_), hyphen (-), period (.), plus (+), asperand (@), and spaces. Cannot start with - or space, or end with space." />
                            </div>
                            <ExclamationCircleIcon v-if="remoteNameErrorTag" class="mt-1 w-5 h-5 text-danger" />
                        </div>
                        <input v-if="editMode" type="text" v-model="loadedEditableRemoteName" :class="[
                            'my-1 block w-full input-textlike bg-default text-default',
                            remoteNameErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]" placeholder="New Remote" title="" />
                        <input v-else disabled type="text" v-model="loadedEditableRemoteName"
                            class="my-1 block w-full input-textlike bg-default text-default" />
                    </div>
                    <div name="cloud-provider" v-if="Object.keys(cloudSyncProviders).length > 0">
                        <label for="cloud-provider-selection" class="block text-sm leading-6 text-default">
                            Cloud Provider</label>
                        <select v-if="editMode" id="cloud-provider-selection" v-model="loadedEditableRemoteProvider"
                            name="cloud-provider-selection"
                            class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                            <option :value="undefined">Select Cloud Provider</option>
                            <option v-for="([key, provider], idx) in Object.entries(cloudSyncProviders)" :key="key"
                                :value="provider">
                                {{ provider.name }}
                            </option>
                        </select>
                        <select v-else id="cloud-provider-selection" v-model="loadedEditableRemoteProvider"
                            name="cloud-provider-selection" disabled
                            class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                            <option :value="loadedEditableRemoteProvider">
                                {{ loadedEditableRemoteProvider!.name }}
                            </option>
                        </select>
                    </div>
                    <div v-if="!editMode && selectedRemote.provider" class=grid grid-cols-2>
                        <div v-for="(parameter, key) in loadedEditableRemoteParams.value.parameters" :key="String(key)"
                            class="mt-1 text-default">
                            <label :for="String(key)" class="block text-sm font-medium text-default">{{ key }}</label>
                            <input disabled
                                v-if="parameter.type === 'string' && (loadedEditableRemoteProvider!.type !== 's3' || String(key) !== 'provider')"
                                type="text" v-model="parameter.value" :id="String(key)"
                                class="block w-full mt-1 input-textlike"
                                :placeholder="parameter.defaultValue == '' ? 'Default is empty string' : `Default is '${parameter.defaultValue}'`" />

                            <input disabled v-else-if="parameter.type === 'bool'" type="checkbox"
                                v-model="parameter.value" :id="String(key)"
                                class="-mt-1 w-4 h-4 text-success border-default rounded focus:ring-green-500" />

                            <input disabled v-else-if="parameter.type === 'int'" type="number" v-model="parameter.value"
                                :id="String(key)" class="block w-full mt-1 input-textlike"
                                :placeholder="parameter.defaultValue == '' ? 'Default is empty string' : `Default is '${parameter.defaultValue}'`" />

                            <select disabled v-else-if="parameter.type === 'select'" v-model="parameter.value"
                                :id="String(key)" class="block w-full mt-1 input-textlike">
                                <option v-for="option in parameter.allowedValues" :key="option" :value="option">
                                    {{ option }}
                                </option>
                            </select>

                            <textarea disabled v-else-if="parameter.type === 'object' && String(key) !== 'token'"
                                v-model="parameter.value" rows="4" :id="String(key)"
                                class="block w-full mt-1 input-textlike"
                                :placeholder='`Default is empty object`'></textarea>
                            <textarea disabled v-else-if="parameter.type === 'object' && String(key) === 'token'"
                                v-model="displayValue" rows="4" :id="String(key)" 
                                class="block w-full mt-1 input-textlike"
                                :placeholder='`Default is empty object`'></textarea>
                        </div>
                    </div>
                    <div v-if="editMode && selectedRemote.provider" class="grid grid-cols-2">
                        <div v-if="loadedEditableRemoteParams.value.oAuthSupported" class="col-span-2 w-full mt-2">
                            <label for="use-oauth" class="block text-base leading-6 text-default mt-1 border-b-2 mb-2">
                                <b>Authenticate with OAuth 2.0</b> - <i class="text-sm">Enter credentials in next
                                    window</i>
                            </label>
                            <div class="button-group-row justify-between">
                                <button @click.stop="oAuthBtn(loadedEditableRemoteProvider! as CloudSyncProvider)"
                                    @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave"
                                    class="flex flex-row items-center text-center h-fit w-full mt-1 btn btn-secondary text-default"
                                    :style="getButtonStyles(isHovered(loadedEditableRemoteParams.name), loadedEditableRemoteProvider! as CloudSyncProvider, undefined)">
                                    <span class="flex-grow text-center mt-0.5">
                                        Authenticate with {{ (loadedEditableRemoteProvider! as CloudSyncProvider).name
                                        }}
                                    </span>
                                    <div class="flex items-center justify-center h-6 w-6 bg-white rounded-full ml-2">
                                        <img :src="getProviderLogo(loadedEditableRemoteProvider! as CloudSyncProvider, undefined)"
                                            alt="provider-logo" class="inline-block w-4 h-4" />
                                    </div>
                                </button>
                                <button v-if="oAuthenticated" @click.stop="clearOAuthBtn()"
                                    class="flex flex-row items-center text-center h-fit w-full mt-1 btn btn-danger text-default">
                                    <span class="flex-grow text-center mt-0.5">
                                        Reset OAuth Data
                                    </span>
                                </button>
                                <button v-if="!oAuthenticated" @click.stop="clearOAuthBtn()" disabled
                                    class="flex flex-row items-center text-center h-fit w-full mt-1 btn btn-danger text-default">
                                    <span class="flex-grow text-center mt-0.5">
                                        Reset OAuth Data
                                    </span>
                                </button>
                            </div>

                        </div>
                        <div v-if="loadedEditableRemoteParams.value.oAuthSupported"
                            class="w-full col-span-2 text-default text-center items-center mt-3">
                            --- OR ---
                        </div>
                        <div class="col-span-2 w-full mt-2">
                            <div class="block text-base leading-6 text-default border-b-2 mb-2">
                                <b>Manually Configure Parameters</b> - <i class="text-sm">Blank fields will be left out
                                    of
                                    config or set with defaults (if applicable)</i>
                            </div>
                            <div v-for="(parameter, key) in loadedEditableRemoteParams.value.parameters"
                                :key="String(key)" class="mt-1 text-default">
                                <!-- find way to skip rendering for 'provider' label -->
                                <label :for="String(key)" class="block text-sm font-medium text-default">
                                    {{ key }}</label>
                                <input
                                    v-if="parameter.type === 'string' && (loadedEditableRemoteProvider!.type !== 's3' || String(key) !== 'provider')"
                                    type="text" v-model="parameter.value" :id="String(key)"
                                    class="block w-full mt-1 input-textlike"
                                    :placeholder="parameter.defaultValue == '' ? 'Default is empty string' : `Default is '${parameter.defaultValue}'`" />

                                <input v-else-if="parameter.type === 'bool'" type="checkbox" v-model="parameter.value"
                                    :id="String(key)"
                                    class="-mt-1 w-4 h-4 text-success border-default rounded focus:ring-green-500" />

                                <input v-else-if="parameter.type === 'int'" type="number" v-model="parameter.value"
                                    :id="String(key)" class="block w-full mt-1 input-textlike"
                                    :placeholder="parameter.defaultValue == '' ? 'Default is empty string' : `Default is '${parameter.defaultValue}'`" />

                                <select v-else-if="parameter.type === 'select'" v-model="parameter.value"
                                    :id="String(key)" class="block w-full mt-1 input-textlike">
                                    <option v-for="option in parameter.allowedValues" :key="option" :value="option">
                                        {{ option }}
                                    </option>
                                </select>

                                <textarea v-else-if="parameter.type === 'object' && String(key) !== 'token'"
                                    v-model="parameter.value" rows="4" :id="String(key)"
                                    class="block w-full mt-1 input-textlike"
                                    :placeholder='`Default is empty object`'></textarea>
                                <textarea v-else-if="parameter.type === 'object' && String(key) === 'token'"
                                    v-model="displayValue" rows="4" :id="String(key)"
                                    class="block w-full mt-1 input-textlike"
                                    :placeholder='`Default is empty object`'></textarea>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full flex flex-row gap-2 items-center">
                <!-- Cancel Button on the far left -->
                <button @click.stop="closeBtn()" id="close-add-task-btn" name="close-add-task-btn"
                    class="btn btn-danger h-fit flex-none">Close</button>

                <!-- Delete and Edit Buttons in the middle -->
                <div v-if="selectedRemote" class="flex flex-row gap-2 flex-grow justify-center">
                    <button id="delete-remote-btn" type="button" @click.stop="deleteRemoteBtn()"
                        class="btn btn-danger h-fit w-full">Delete Remote</button>
                    <button v-if="editMode" id="edit-remote-btn" type="button" @click.stop="editRemoteBtn()"
                        class="btn btn-secondary h-fit w-full">Cancel Edit</button>
                    <button v-if="!editMode" id="edit-remote-btn" type="button" @click.stop="editRemoteBtn()"
                        class="btn btn-secondary h-fit w-full">Edit Remote</button>
                </div>

                <!-- Save Button on the far right -->
                <div v-if="selectedRemote && editMode" class="flex-none">
                    <button v-if="saving" id="adding-task-btn" type="button" class="btn btn-primary h-fit" disabled>
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
                        Saving...
                    </button>
                    <button v-if="!saving" id="add-task-btn" class="btn btn-primary h-fit" @click="saveEditedRemoteBtn">
                        Save Changes
                    </button>
                    <!-- <button v-if="saving" disabled id="add-task-btn-error" class="btn btn-primary h-fit w-full"
                        @click="saveEditedRemoteBtn">Save Remote</button> -->
                </div>
            </div>
        </template>
    </Modal>
    <div v-if="showCloseConfirmation">
        <component :is="closeConfirmationComponent" @close="updateShowCloseConfirmation" dropboxAuthParams
            :showFlag="showCloseConfirmation" :title="'Cancel Edit Remote'"
            :message="'Are you sure? The currently edited remote configuration will be lost.'"
            :confirmYes="confirmCancel" :confirmNo="cancelCancel" :operation="'canceling'"
            :operating="cancelingManageRemotes" />
    </div>

    <div v-if="showDeleteRemotePrompt">
        <component :is="deleteRemoteDialog" @close="updateShowDeleteRemotePrompt" :showFlag="showDeleteRemotePrompt"
            :title="'Delete Remote'" :message="'Are you sure you want to delete this remote?'"
            :confirmYes="deleteRemoteYes" :confirmNo="deleteRemoteNo" :operating="deleting" :operation="'deleting'" />
    </div>
</template>
<script setup lang="ts">
import { inject, ref, Ref, watch, computed, reactive, onMounted } from 'vue';
import Modal from '../common/Modal.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import InfoTile from '../common/InfoTile.vue';
import CustomLoadingSpinner from "../common/CustomLoadingSpinner.vue";
import { CloudAuthParameter, CloudSyncParameter, CloudSyncProvider, CloudSyncRemote, cloudSyncProviders, getButtonStyles, getProviderLogo } from "../../models/CloudSync";
import { pushNotification, Notification } from 'houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey, truncateTextInjectionKey } from '../../keys/injection-keys';

const truncateText = injectWithCheck(truncateTextInjectionKey, "truncateText not provided!");
const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remote manager not provided!");
const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, "remotes not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");

const emit = defineEmits(['close']);
const showManageRemotes = inject<Ref<boolean>>('show-manage-remotes')!;

console.log('REMOTES:', existingRemotes)!;


// Create dummy CloudSyncRemote instance for dev
const dummyDropboxProvider: CloudSyncProvider = cloudSyncProviders["dropbox"];
const dummyDropboxAuthParams: CloudAuthParameter = {
    parameters: {
        token: { value: "", type: "object", defaultValue: "" },
        client_id: { value: "dropbox-client-id", type: "string", defaultValue: "" },
        client_secret: { value: "dropbox-client-secret", type: "string", defaultValue: "" },
    },
    oAuthSupported: true,
};
const dummyCloudSyncRemote = new CloudSyncRemote(
    "dummyRemote",          // Name of the remote
    "dropbox",              // Type of remote, matching the provider type
    dummyDropboxAuthParams,      // Authentication parameters for Dropbox
    dummyDropboxProvider         // The Dropbox provider instance
);
const dummyRemote = ref(dummyCloudSyncRemote);

onMounted(async () => {
    await loadRemotes();
});

async function loadRemotes() {
    loading.value = true;
    await myRemoteManager.getRemotes();
    loading.value = false;
}

const selectedRemote = ref<CloudSyncRemote>();
const loadedEditableRemoteName = ref<string>();
const loadedEditableRemoteProvider = ref<CloudSyncProvider>();
const loadedEditableRemoteParams = reactive<any>({});
const editMode = ref(false);

watch(selectedRemote, (newlySelectedRemote) => {
    if (newlySelectedRemote) {
        populateValues(newlySelectedRemote);
    }
});

watch(loadedEditableRemoteProvider, (newlySelectedProvider) => {
    if (newlySelectedProvider) {
        resetProviderParams(newlySelectedProvider);
    }
});

function resetProviderParams(newSelection) {
    if (newSelection !== selectedRemote.value!.provider) {
        pushNotification(new Notification('Provider Changed', `Cloud provider has been changed, parameters have been reset.`, 'warning', 8000));
        loadedEditableRemoteParams.value = JSON.parse(JSON.stringify(newSelection!.providerParams));
    } 
    // else if (newSelection === selectedRemote.value!.provider) {
    //     pushNotification(new Notification('Provider Changed', `Cloud provider parameters set back to previous configuration.`, 'info', 8000));
    //     loadedEditableRemoteParams.value = JSON.parse(JSON.stringify(selectedRemote.value!.authParams));
    // }
}

function clearValues() {
    loadedEditableRemoteName.value = '';
    loadedEditableRemoteProvider.value = undefined;
    loadedEditableRemoteParams.value = {};
    console.log('clearedRemoteName:', loadedEditableRemoteName.value);
    console.log('clearedRemoteProvider:', loadedEditableRemoteProvider.value);
    console.log('clearedRemoteParams', loadedEditableRemoteParams);
}

function populateValues(selectedRemote: CloudSyncRemote) {
    clearValues();
    console.log('selectedRemote:', selectedRemote);
    loadedEditableRemoteName.value = selectedRemote.name;
    loadedEditableRemoteProvider.value = selectedRemote.provider;

    if (selectedRemote && selectedRemote.authParams) {
        // Deep copy only the authParams object from selectedRemote to loadedEditableRemoteParams
        loadedEditableRemoteParams.value = JSON.parse(JSON.stringify(selectedRemote.authParams));
    } else {
        console.error("authParams is undefined in selectedRemote");
    }

    console.log('loadedEditableRemoteName:', loadedEditableRemoteName.value);
    console.log('loadedEditableRemoteProvider:', loadedEditableRemoteProvider.value);
    console.log('loadedEditableRemoteParams', loadedEditableRemoteParams);
}


const remoteNameErrorTag = ref('');
const saving = ref(false);
const oAuthenticated = ref(false);

const errorList = ref<string[]>([]);

const closeModal = () => {
    editMode.value = false;
    showManageRemotes.value = false;
    emit('close');
}

const cancelingManageRemotes = ref(false);
const showCloseConfirmation = ref(false);
const closeConfirmationComponent = ref();

/* Generic loading function for Confirmation Dialogs */
async function loadConfirmationDialog(dialogRef) {
    const module = await import('../common/ConfirmationDialog.vue');
    dialogRef.value = module.default;
}


const closeBtn = async () => {
    if (selectedRemote.value && editMode.value) {
        await loadConfirmationDialog(closeConfirmationComponent);
        showCloseConfirmation.value = true;
    } else {
        closeModal();
    }
};

const updateShowCloseConfirmation = (newVal) => {
    showCloseConfirmation.value = newVal;
}

const confirmCancel: ConfirmationCallback = async () => {
    closeModal();
}

const cancelCancel: ConfirmationCallback = async () => {
    updateShowCloseConfirmation(false);
}


function selectRemoteBtn(remote) {
    editMode.value = false
    selectedRemote.value = remote;
}

function editRemoteBtn() {
    editMode.value = !editMode.value;
}

const hasChanges = ref(false);

function checkForChanges() {
    // Check if the name or provider has changed
    if (
        loadedEditableRemoteName.value !== selectedRemote.value?.name ||
        loadedEditableRemoteProvider.value?.type !== selectedRemote.value?.provider?.type
    ) {
        hasChanges.value = true;
        return;
    }

    // Check if any parameter values have changed
    for (const [key, parameter] of Object.entries(loadedEditableRemoteParams.value.parameters as Record<string, CloudSyncParameter>)) {
        const originalParameter = selectedRemote.value?.authParams.parameters[key];

        if (!originalParameter || parameter.value !== originalParameter.value) {
            hasChanges.value = true;
            return;
        }
    }

    // If no changes were found, set hasChanges to false
    hasChanges.value = false;
}


watch([loadedEditableRemoteName, loadedEditableRemoteProvider, loadedEditableRemoteParams], checkForChanges, { deep: true });

async function saveEditedRemoteBtn() {
    if (!hasChanges) {
        pushNotification(new Notification('No Changes Detected', `No fields have been changed, save not completed.`, 'info', 8000));
    } else {
        saving.value = true;
        await myRemoteManager.editRemote(selectedRemote.value!.name, loadedEditableRemoteName.value!, loadedEditableRemoteProvider.value!.type, loadedEditableRemoteParams.value!);
        pushNotification(new Notification('Remote Updated', `Remote changes have been saved successfully.`, 'success', 8000));
        saving.value = false;
        editMode.value = false;
        loadRemotes();
    }
}

function deleteRemoteBtn() {
    showDeleteRemoteDialog();
}

const showDeleteRemotePrompt = ref(false);
const deleteRemoteDialog = ref();
const deleting = ref(false);

async function showDeleteRemoteDialog() {
    await loadConfirmationDialog(deleteRemoteDialog);
    showDeleteRemotePrompt.value = true;
}

const deleteRemoteYes: ConfirmationCallback = async () => {
    deleting.value = true;
    const remoteName = selectedRemote.value!.name;
    await myRemoteManager.deleteRemote(remoteName);
    loading.value = true;
    await myRemoteManager.getRemotes();
    pushNotification(new Notification('Remote Deleted', `Remote ${remoteName} has been deleted successfully.`, 'success', 8000));
    loading.value = false;
    // clearValues();
    editMode.value = false;
    selectedRemote.value = undefined;
    deleting.value = false;
    updateShowDeleteRemotePrompt(false);
}
const deleteRemoteNo: ConfirmationCallback = async () => {
    updateShowDeleteRemotePrompt(false);
}
const updateShowDeleteRemotePrompt = (newVal) => {
    showDeleteRemotePrompt.value = newVal;
}


function clearOAuthBtn() {
    oAuthenticated.value = false;
    loadedEditableRemoteParams.token = "";
}

// Computed property with token existence check
const displayValue = computed({
    get: () => {
        if (loadedEditableRemoteProvider.value) {
            const token = loadedEditableRemoteParams.value.parameters.token.value;
            if (!token) {
                return ''; // Return empty or a placeholder if token is missing
            }
            // Convert token to JSON string for display if it’s an object
            return typeof token === 'object'
                ? JSON.stringify(token, null, 2)
                : token;
        }
    },
    set: (newValue: string) => {
        if (loadedEditableRemoteProvider.value) {
            try {
                // Parse JSON and update token if valid in loadedEditableRemoteParams
                loadedEditableRemoteParams.value.parameters.token.value = JSON.parse(newValue);
            } catch {
                // If parsing fails, keep as string in loadedEditableRemoteParams
                loadedEditableRemoteParams.value.parameters.token.value = newValue;
            }
        }
    }
});

const accessToken = ref<string | null>(null);
const refreshToken = ref<string | null>(null);
const userId = ref<string | null>(null);
const tokenExpiry = ref<string | null>(null);

function oAuthBtn(selectedProvider: CloudSyncProvider) {
    try {
        let providerAuthUrlSuffix;

        switch (selectedProvider.type) {
            case 'dropbox':
                providerAuthUrlSuffix = 'dropbox';
                break;
            case 'drive':
                providerAuthUrlSuffix = 'drive';
                break;
            case 'google cloud storage':
                providerAuthUrlSuffix = 'cloud';
                break;
            case 'onedrive':
                providerAuthUrlSuffix = 'onedrive';
                break;
            default:
                providerAuthUrlSuffix = '';
                break;

        }

        const ngrokUrl = `https://seemingly-settling-stud.ngrok-free.app/auth/${providerAuthUrlSuffix}`;
        const authWindow = window.open(ngrokUrl, '_blank', 'width=500,height=900');

        if (!authWindow) {
            throw new Error('Failed to open authentication window. Please check your popup settings.');
        }

        const handleAuthMessage = async (event) => {
            try {
                if (event.origin !== 'https://seemingly-settling-stud.ngrok-free.app') return;

                const { accessToken: token, refreshToken: refresh, userId: id } = event.data;

                // Log the received token data
                // console.log('OAuth response received:', event.data);

                if (token && refresh && id) {
                    accessToken.value = token;
                    refreshToken.value = refresh;
                    userId.value = id;

                    const expiry = await getTokenExpiry();
                    if (expiry) {
                        tokenExpiry.value = expiry;
                    }

                    const fullToken = {
                        "access_token": accessToken.value,
                        "expiry": tokenExpiry.value,
                        "refresh_token": refreshToken.value
                    };

                    // Log the assembled full token
                    // console.log('Assembled full token:', fullToken);

                    oAuthenticated.value = true;
                    loadedEditableRemoteParams.value.parameters.token.value = typeof fullToken === 'string' ? JSON.parse(fullToken) : fullToken;

                    pushNotification(new Notification('Authentication Successful', `Token updated successfully`, 'success', 8000));

                    // Remove the event listener after it has been handled
                    window.removeEventListener('message', handleAuthMessage);
                } else {
                    throw new Error('Authentication failed. Token data is missing or incomplete.');
                }
            } catch (error: any) {
                console.error('Error during authentication:', error);
                oAuthenticated.value = false;
                pushNotification(new Notification('Authentication Failed', `${error.message}`, 'error', 8000));
            }
        };

        // Attach the event listener once
        window.addEventListener('message', handleAuthMessage);
    } catch (error: any) {
        console.error('Error initializing OAuth:', error);
        pushNotification(new Notification('Authentication Error', `${error.message}`, 'error', 8000));
    }
}

async function getTokenExpiry(): Promise<string> {
    // Assume a standard 1-hour lifespan for Google access tokens
    const currentTime = new Date();
    return new Date(currentTime.getTime() + 3600 * 1000).toISOString();
}

const hoverStates = reactive({});

function handleMouseEnter(remoteName) {
    hoverStates[remoteName] = true;
}

function handleMouseLeave(remoteName) {
    hoverStates[remoteName] = false;
}

function isHovered(remoteName) {
    return hoverStates[remoteName] || false; // Default to false if undefined
}

</script>