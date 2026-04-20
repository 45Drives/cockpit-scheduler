<template>
    <Modal @close="closeModal" :isOpen="showCreateRemote" :margin-top="'mt-14'" :width="'w-6/12'"
        :min-width="'min-w-3/5'" :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="false"
        :closeConfirm="closeBtn">
        <template v-slot:title>
            <div class="items-center">
                Create Rclone Remote
                <img v-if="selectedProvider" :src="getProviderLogo(selectedProvider, undefined)" alt="provider-logo"
                    class="inline-block w-6 h-6 ml-2" />
            </div>
        </template>
        <template v-slot:content>
            <div>
                <div name="remote-name">
                    <div class="flex flex-row justify-between items-center">
                        <div class="flex flex-row justify-between items-center">
                            <label class="block text-sm leading-6 text-default">Remote Name</label>
                            <InfoTile class="ml-1"
                                title="Name can have letters, numbers, underscore (_), hyphen (-), period (.), plus (+), asperand (@), and spaces. Cannot start with - or space, or end with space." />
                        </div>
                        <ExclamationCircleIcon v-if="remoteNameErrorTag" class="mt-1 w-5 h-5 text-danger" />
                    </div>
                    <input type="text" v-model="remoteName" :class="[
                        'my-1 block w-full input-textlike bg-default text-default',
                        remoteNameErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                    ]" placeholder="New Remote" title="" />
                </div>
                <div name="cloud-provider" v-if="Object.keys(cloudSyncProviders).length > 0">
                    <label for="cloud-provider-selection" class="block text-sm leading-6 text-default">Cloud
                        Provider</label>
                    <select id="cloud-provider-selection" v-model="selectedProvider" name="cloud-provider-selection"
                        class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option :value="undefined">Select Cloud Provider</option>
                        <option v-for="([key, provider], idx) in Object.entries(cloudSyncProviders)" :key="key"
                            :value="provider">
                            {{ provider.name }}
                        </option>
                    </select>
                </div>
                <div v-if="selectedProvider" class="grid grid-cols-2">
                    <div v-if="selectedProvider.providerParams.oAuthSupported" class="col-span-2 w-full mt-2">
                        <label for="use-oauth" class="block text-base leading-6 text-default mt-1 border-b-2 mb-2">
                            <b>Authenticate with OAuth 2.0</b> - <i class="text-sm">Enter credentials in next window</i>
                        </label>
                        <div class="button-group-row justify-between">
                            <button @click.stop="oAuthBtn(selectedProvider)" @mouseenter="handleMouseEnter"
                                @mouseleave="handleMouseLeave"
                                class="flex flex-row items-center text-center h-fit w-full mt-1 btn text-white"
                                :style="getButtonStyles(isHovered, selectedProvider, undefined)">
                                <span class="flex-grow text-center mt-0.5">
                                    Authenticate with {{ selectedProvider.name }}
                                </span>
                                <div class="flex items-center justify-center h-6 w-6 bg-white rounded-full ml-2">
                                    <img :src="getProviderLogo(selectedProvider, undefined)" alt="provider-logo"
                                        class="inline-block w-4 h-4" />
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

                    <div v-if="selectedProvider.providerParams.oAuthSupported"
                        class="w-full col-span-2 text-default items-center mt-3 flex flex-row">
                        <div class="flex-grow text-left">
                            <a :href="privacyPolicyUrl" target="_blank" rel="noopener noreferrer"
                                class="underline text-blue-500 hover:text-blue-700">
                                Privacy Policy
                            </a>
                            <a :href="termsOfServiceUrl" target="_blank" rel="noopener noreferrer"
                                class="ml-4 underline text-blue-500 hover:text-blue-700">
                                Terms of Service
                            </a>
                        </div>
                    </div>
                    <div class="col-span-2 w-full mt-2">
                        <div class="block text-base leading-6 text-default border-b-2 mb-2">
                            <b>Manually Configure Parameters</b> - <i class="text-sm">Blank fields will be left out of
                                config or set with defaults (if applicable)</i>
                        </div>

                        <!-- Loading rclone options -->
                        <div v-if="rcloneProviders.loading.value" class="flex items-center gap-2 my-2">
                            <svg class="animate-spin h-4 w-4 text-muted" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            <span class="text-sm text-muted">Loading provider options from rclone…</span>
                        </div>

                        <!-- Token display for OAuth providers -->
                        <div v-if="selectedProvider.providerParams.oAuthSupported" class="mt-1 text-default">
                            <label class="block text-sm font-medium text-default">token</label>
                            <textarea v-model="displayValue" rows="4"
                                class="block w-full mt-1 input-textlike"
                                :placeholder='`Automatically retrieved with OAuth. (Default is empty object)`'></textarea>
                        </div>

                        <!-- All rclone options rendered via RcloneOptionField -->
                        <div v-for="opt in dynamicBasicOptions" :key="'dyn-' + opt.name" class="mt-2 text-default">
                            <RcloneOptionField :option="opt" v-model="dynamicValues[opt.name]" />
                        </div>

                        <!-- Advanced rclone options in a disclosure -->
                        <Disclosure v-if="dynamicAdvancedOptions.length > 0" v-slot="{ open }" class="mt-3">
                            <DisclosureButton class="bg-default w-full justify-start text-center rounded-md flex flex-row">
                                <div class="m-1">
                                    <ChevronUpIcon class="h-6 w-6 text-default transition-all duration-200 transform"
                                        :class="{ 'rotate-90': !open, 'rotate-180': open }" />
                                </div>
                                <div class="ml-2 mt-1">
                                    <span class="text-sm text-default">Advanced Options ({{ dynamicAdvancedOptions.length }})</span>
                                </div>
                            </DisclosureButton>
                            <DisclosurePanel>
                                <div class="bg-default p-3 rounded-b-md -mt-1">
                                    <div v-for="opt in dynamicAdvancedOptions" :key="'adv-' + opt.name" class="mt-2 text-default">
                                        <RcloneOptionField :option="opt" v-model="dynamicValues[opt.name]" />
                                    </div>
                                </div>
                            </DisclosurePanel>
                        </Disclosure>
                    </div>
                </div>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
                <div class="button-group-row w-full justify-between">
                    <div class="button-group-row">
                        <button @click.stop="closeBtn()" id="close-create-remote-btn" name="close-create-remote-btn"
                            class="btn btn-danger h-fit w-full">Cancel</button>
                    </div>
                    <div class="button-group-row">
                        <button disabled v-if="creating" id="creating-task-btn" type="button"
                            class="btn btn-primary h-fit w-full">
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
                            Saving...
                        </button>
                        <button v-else-if="!creating && selectedProvider" id="create-remote-btn"
                            class="btn btn-primary h-fit w-full" @click="createRemoteBtn">Save Remote</button>
                        <button v-else disabled id="create-remote-btn-error" class="btn btn-primary h-fit w-full"
                            @click="createRemoteBtn">Save Remote</button>
                    </div>
                </div>
            </div>
        </template>
    </Modal>
    <div v-if="showCloseConfirmation">
        <component :is="closeConfirmationComponent" @close="updateShowCloseConfirmation"
            :showFlag="showCloseConfirmation" :title="'Cancel Create Remote'"
            :message="'Are you sure? This remote configuration will be lost.'" :confirmYes="confirmCancel"
            :confirmNo="cancelCancel" :operation="'canceling'" :operating="cancelingAddRemote" />
    </div>
</template>
<script setup lang="ts">
import { inject, ref, Ref, watch, computed, reactive, onMounted } from 'vue';
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue';
import Modal from '../common/Modal.vue';
import { ExclamationCircleIcon, ChevronUpIcon } from '@heroicons/vue/24/outline';
import InfoTile from '../common/InfoTile.vue';
import RcloneOptionField from '../common/RcloneOptionField.vue';
import { pushNotification, Notification } from '@45drives/houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey, truncateTextInjectionKey } from '../../keys/injection-keys';
import { CloudSyncProvider, cloudSyncProviders, getButtonStyles, getProviderLogo } from "../../models/CloudSync";
import { useRcloneProviders, type RcloneOption } from '../../composables/useRcloneProviders';

const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remote manager not provided!");
const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, "remotes not provided!");

const selectedProvider = ref<CloudSyncProvider>();
const providerValues = reactive<any>({});
const dynamicValues = reactive<Record<string, any>>({});

const remoteName = ref('');
const remoteNameErrorTag = ref('');
const creating = ref(false);
const oAuthenticated = ref(false);
const emit = defineEmits(['close']);
const showCreateRemote = inject<Ref<boolean>>('show-create-remote')!;

console.log('EXISTING REMOTES:', existingRemotes)!;

const privacyPolicyUrl = ref('https://cloud-sync.45d.io/privacy');
const termsOfServiceUrl = ref('https://cloud-sync.45d.io/tos');

// Dynamic rclone provider options
const rcloneProviders = useRcloneProviders();
onMounted(() => { rcloneProviders.load(); });

// Map CloudSync.ts type values to rclone's actual Prefix keys
const typeToRclonePrefix: Record<string, string> = {
    'google cloud storage': 'gcs',
};

function getRcloneTypeKey(provider: CloudSyncProvider | undefined): string {
    if (!provider) return '';
    if (provider.type === 's3') return 's3';
    return typeToRclonePrefix[provider.type] ?? provider.type;
}

// Get the S3 sub-provider name (e.g. "AWS", "Wasabi", "Ceph") for filtering provider-specific options
function getSubProvider(provider: CloudSyncProvider | undefined): string | undefined {
    if (!provider || provider.type !== 's3') return undefined;
    return provider.providerParams.parameters.provider?.value as string | undefined;
}

// Hidden fields that are handled specially (token via OAuth, provider set by selection)
const hiddenFields = new Set(['token', 'provider']);

// All basic rclone options for the selected provider
const dynamicBasicOptions = computed<RcloneOption[]>(() => {
    const typeKey = getRcloneTypeKey(selectedProvider.value);
    if (!typeKey) return [];
    const sub = getSubProvider(selectedProvider.value);
    return rcloneProviders.getBasicOptions(typeKey, sub)
        .filter(o => !hiddenFields.has(o.name));
});

// All advanced rclone options for the selected provider
const dynamicAdvancedOptions = computed<RcloneOption[]>(() => {
    const typeKey = getRcloneTypeKey(selectedProvider.value);
    if (!typeKey) return [];
    const sub = getSubProvider(selectedProvider.value);
    return rcloneProviders.getAdvancedOptions(typeKey, sub)
        .filter(o => !hiddenFields.has(o.name));
});

watch(selectedProvider, (newlySelectedProvider) => {
    if (newlySelectedProvider) {
        Object.keys(providerValues).forEach((key) => delete providerValues[key]); // Clear previous values
        Object.keys(dynamicValues).forEach((key) => delete dynamicValues[key]); // Clear dynamic values

        // Set provider value for S3 types (hidden field)
        if (newlySelectedProvider.type === 's3') {
            providerValues.provider = newlySelectedProvider.providerParams.parameters.provider?.value ?? '';
        }

        // Initialize ALL option values from rclone defaults, using CloudSync.ts defaults where available
        const typeKey = getRcloneTypeKey(newlySelectedProvider);
        const sub = getSubProvider(newlySelectedProvider);
        if (typeKey) {
            const staticDefaults = newlySelectedProvider.providerParams.parameters;
            const allOpts = rcloneProviders.getProviderOptions(typeKey, sub);
            for (const opt of allOpts) {
                if (opt.name === 'token') continue;
                if (opt.name === 'provider') continue;
                // Use CloudSync.ts default if available, otherwise rclone default
                const staticParam = staticDefaults[opt.name];
                if (staticParam !== undefined) {
                    dynamicValues[opt.name] = staticParam.value ?? staticParam.defaultValue ?? (opt.type === 'bool' ? false : '');
                } else if (opt.type === 'bool') {
                    dynamicValues[opt.name] = opt.default ?? false;
                } else {
                    dynamicValues[opt.name] = opt.default ?? '';
                }
            }
        }
    }
});

const closeModal = () => {
    oAuthenticated.value = false;

    providerValues.token = "" ;
    Object.keys(dynamicValues).forEach((key) => delete dynamicValues[key]);
    showCreateRemote.value = false;
    emit('close');
}

const cancelingAddRemote = ref(false);
const showCloseConfirmation = ref(false);
const closeConfirmationComponent = ref();
async function loadCloseConfirmationComponent() {
    const module = await import('../common/ConfirmationDialog.vue');
    closeConfirmationComponent.value = module.default;
}

const closeBtn = async () => {
    if (!selectedProvider.value) {
        closeModal();
    } else {
        await loadCloseConfirmationComponent();
        showCloseConfirmation.value = true;
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

const providerParameters = computed(() => {
    if (!selectedProvider.value) return [];
    return Object.entries(selectedProvider.value.providerParams.parameters);
});


// Computed property with token existence check
const displayValue = computed({
    get: () => {
        if (selectedProvider.value) {
            const token = providerValues.token; // Use providerValues instead of selectedProvider
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
        if (selectedProvider.value) {
            try {
                // Parse JSON and update token if valid in providerValues
                providerValues.token = JSON.parse(newValue);
            } catch {
                // If parsing fails, keep as string in providerValues
                providerValues.token = newValue;
            }
        }
    }
});

const createRemoteBtn = async () => {
    try {
        if (!remoteName.value) {
            throw Error('Remote name required');
        }
        if (!selectedProvider.value) {
            throw Error('No provider selected');
        }

        if (providerValues.token) {
            // Validate that token is JSON
            const tokenParam = providerValues.token;
            if (typeof tokenParam === 'string') {
                try {
                    providerValues.token = JSON.parse(tokenParam); // Convert to JSON if necessary
                } catch {
                    throw new Error('Token parameter is invalid JSON.');
                }
            }
        }

        creating.value = true;
        // Collect all non-empty option values
        const allParams = Object.fromEntries(
            Object.entries(dynamicValues).filter(([key, value]) => {
                return value !== null && value !== undefined && value !== '' && value !== false;
            })
        );
        // Add special fields from providerValues (provider for S3, token for OAuth)
        const specialParams = Object.fromEntries(
            Object.entries(providerValues).filter(([key, value]) => {
                return value !== null && value !== undefined && value !== '';
            })
        );
        const parametersToSave = { ...allParams, ...specialParams };
        const newRemote = await myRemoteManager.createRemote(remoteName.value, selectedProvider.value.type, parametersToSave);
        pushNotification(new Notification('Save Successful', `Remote saved successfully`, 'success', 6000));
        creating.value = false;
        showCreateRemote.value = false;

    } catch (error: any) {
        console.error('Error during save:', error);
        pushNotification(new Notification('Save Failed', `${error.message}`, 'error', 6000));
    }
}

function clearOAuthBtn() {
    oAuthenticated.value = false;
    providerValues.token = "";
}

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
            default:
                providerAuthUrlSuffix = '';
                break;
        }

        const middlewareUrl = `https://cloud-sync.45d.io/auth/${providerAuthUrlSuffix}`;
        const authWindow = window.open(middlewareUrl, '_blank', 'width=500,height=900');

        if (!authWindow) {
            throw new Error('Failed to open authentication window. Please check your popup settings.');
        }

        const handleAuthMessage = async (event) => {
            try {
                if (event.origin !== 'https://cloud-sync.45d.io') return;
                const { accessToken: token, refreshToken: refresh, expiry: expiry, userId: id } = event.data;

                if (token && refresh && id) {
                    accessToken.value = token;
                    refreshToken.value = refresh;
                    tokenExpiry.value = expiry;
                    userId.value = id;

                    const fullToken = {
                        "access_token": accessToken.value,
                        "expiry": tokenExpiry.value,
                        "refresh_token": refreshToken.value
                    };

                    oAuthenticated.value = true;
                    providerValues.token = JSON.stringify(fullToken);

                    pushNotification(new Notification('Authentication Successful', `Token updated successfully`, 'success', 6000));

                    // Remove the event listener after it has been handled
                    window.removeEventListener('message', handleAuthMessage);
                } else {
                    throw new Error('Authentication failed. Token data is missing or incomplete.');
                }
            } catch (error: any) {
                console.error('Error during authentication:', error);
                oAuthenticated.value = false;
                pushNotification(new Notification('Authentication Failed', `${error.message}`, 'error', 6000));
            }
        };

        // Attach the event listener once
        window.addEventListener('message', handleAuthMessage);
    } catch (error: any) {
        console.error('Error initializing OAuth:', error);
        pushNotification(new Notification('Authentication Error', `${error.message}`, 'error', 6000));
    }
}

const isHovered = ref(false);

function handleMouseEnter() {
    isHovered.value = true;
}

function handleMouseLeave() {
    isHovered.value = false;
}
</script>