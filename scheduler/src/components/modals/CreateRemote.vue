<template>
    <Modal @close="closeModal" :isOpen="showCreateRemote" :margin-top="'mt-24'" :width="'w-3/5'"
        :min-width="'min-w-3/5'" :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="false"
        :closeConfirm="closeBtn">
        <template v-slot:title>
            Create Rclone Remote
        </template>
        <template v-slot:content>
            <div>
                <div name="remote-name">
                    <div class="flex flex-row justify-between items-center">
                        <div class="flex flex-row justify-between items-center">
                            <label class="block text-sm leading-6 text-default">Remote Name</label>
                            <!-- <InfoTile class="ml-1"
                                title="Name can have letters, numbers, and underscores. Spaces will convert to underscores upon save." /> -->
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
                <div v-if="selectedProvider" class="">
                    <div v-if="selectedProvider.parameters.oAuthSupported" class="w-full mt-2">
                        <label for="use-oauth" class="block text-base leading-6 text-default mt-1">
                            <b>Authenticate with OAuth 2.0</b> - <i>Enter credentials in next window</i>
                        </label>
                        <button @click.stop="oAuthBtn(selectedProvider)"
                            class="flex flex-row items-center text-center h-fit w-full  btn btn-secondary text-default"
                            :style="{ backgroundColor: getProviderColor(selectedProvider) }">
                            <span class="flex-grow text-center mt-0.5">
                                Authenticate with {{selectedProvider.name}}
                            </span>
                            <div class="flex items-center justify-center h-6 w-6 bg-white rounded-full ml-2">
                                <img :src="getProviderLogo(selectedProvider)" alt="provider-logo"
                                    class="inline-block h-4" />
                            </div>
                        </button>
                    </div>
                    <div class="flex flex-row justify-between items-center text-center mt-2">
                        <label for="cloud-provider-parameters" class="block text-base leading-6 text-default mt-1">
                            <b>Manually Configure Parameters</b> - <i>Leave blank for default values where appropriate</i>
                        </label>
                        <!--  <div v-if="selectedProvider.parameters.oAuthSupported" class="">
                            <button @click.stop="oAuthBtn(selectedProvider)"
                                class="flex flex-row items-center text-center h-fit w-full  btn btn-secondary text-default"
                                :style="{ backgroundColor: getProviderColor(selectedProvider) }">
                                <span class="flex-grow text-center mt-0.5">
                                    Authenticate with OAuth
                                </span>
                                <div class="flex items-center justify-center h-6 w-6 bg-white rounded-full ml-2">
                                    <img :src="getProviderLogo(selectedProvider)" alt="provider-logo"
                                        class="inline-block h-4" />
                                </div>
                            </button>
                        </div> -->
                    </div>

                    <div v-for="([key, parameter], index) in basicParameters" :key="key" class="mt-4 text-default">
                        <label :for="String(key)" class="block text-sm font-medium text-default">{{ key }}</label>
                        <input v-if="parameter.type === 'string' && selectedProvider.type !== 's3'" type="text"
                            v-model="parameter.value" :id="String(key)" class="block w-full mt-1 input-textlike"
                            :placeholder="getPlaceholder(parameter)" />
                        <input v-if="parameter.type === 'string' && selectedProvider.type == 's3'" type="text"
                            v-model="parameter.value" :id="String(key)" disabled
                            class="block w-full mt-1 input-textlike" :placeholder="getPlaceholder(parameter)" />
                        <input v-else-if="parameter.type === 'bool'" type="checkbox" v-model="parameter.value"
                            :id="String(key)"
                            class="mt-1 w-4 h-4 text-success border-default rounded focus:ring-green-500 dark:focus:ring-green-600 dark:ring-offset-gray-800 focus:ring-2"
                            :placeholder="getPlaceholder(parameter)" />
                        <input v-else-if=" parameter.type==='int'" type=" number" v-model="parameter.value"
                            :id="String(key)" class="block w-full mt-1 input-textlike"
                            :placeholder="getPlaceholder(parameter)" />
                        <select v-else-if="parameter.type === 'select'" v-model="parameter.value" :id="String(key)"
                            class="block w-full mt-1 input-textlike">
                            <option v-for="option in parameter.allowedValues" :key="option" :value="option">
                                {{ option }}
                            </option>
                        </select>
                        <textarea v-else-if="parameter.type === 'object'" v-model="parameter.value" :id="String(key)"
                            class="block w-full mt-1 input-textlike"
                            :placeholder="getPlaceholder(parameter)"></textarea>
                    </div>

                    <!-- Disclosure for advanced parameters -->
                    <!-- <div class="bg-well rounded-md text-default">
                        <Disclosure v-slot="{ open }" :defaultOpen="false">
                            <DisclosureButton
                                class="bg-well mt-2 w-full justify-start text-center rounded-md flex flex-row">
                                <div class="m-1">
                                    <ChevronUpIcon class="h-7 w-7 text-default transition-all duration-200 transform"
                                        :class="{ 'rotate-90': !open, 'rotate-180': open, }" />
                                </div>
                                <div class="ml-3 mt-1.5">
                                    <span class="text-start whitespace-nowrap text-base text-default">
                                        <b>Advanced Config Parameters</b>
                                    </span>
                                </div>
                            </DisclosureButton>
                            <DisclosurePanel class="bg-well rounded-md p-2">
                                <div v-for="([key, parameter], index) in advancedParameters" :key="key" class="mt-4">
                                    <label :for="String(key)" class="block text-sm font-medium text-default">{{ key
                                        }}</label>
                                    <input v-if="parameter.type === 'string'" type="text" v-model="parameter.value"
                                        :id="String(key)" class="block w-full mt-1 input-textlike"
                                        :placeholder="getPlaceholder(parameter)" />
                                    <input v-else-if="parameter.type === 'bool'" type="checkbox"
                                        v-model="parameter.value" :id="String(key)"
                                        class="mt-1 w-4 h-4 text-success border-default rounded focus:ring-green-500 dark:focus:ring-green-600 dark:ring-offset-gray-800 focus:ring-2"
                                        :placeholder="getPlaceholder(parameter)" />
                                    <input v-else-if="parameter.type === 'int'" type="number" v-model="parameter.value"
                                        :id="String(key)" class="block w-full mt-1 input-textlike"
                                        :placeholder="getPlaceholder(parameter)" />
                                    <select v-else-if="parameter.type === 'select'" v-model="parameter.value"
                                        :id="String(key)" class="block w-full mt-1 input-textlike">
                                        <option v-for="option in parameter.allowedValues" :key="option" :value="option">
                                            {{ option }}
                                        </option>
                                    </select>
                                    <textarea v-else-if="parameter.type === 'object'" v-model="parameter.value"
                                        :id="String(key)" class="block w-full mt-1 input-textlike"
                                        :placeholder="getPlaceholder(parameter)"></textarea>
                                </div>
                            </DisclosurePanel>
                        </Disclosure>
                    </div> -->
                </div>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
                <div class="button-group-row w-full justify-between">
                    <div class="button-group-row">
                        <button @click.stop="closeBtn()" id="close-add-task-btn" name="close-add-task-btn"
                            class="mt-1 btn btn-danger h-fit w-full">Cancel</button>
                    </div>
                    <div class="button-group-row">
                        <button disabled v-if="creating" id="adding-task-btn" type="button"
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
                            Adding...
                        </button>
                        <button v-else-if="!creating && selectedProvider" id="add-task-btn"
                            class="btn btn-primary h-fit w-full" @click="createRemoteBtn">Save Remote</button>
                        <button v-else disabled id="add-task-btn-error" class="btn btn-primary h-fit w-full"
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
import { inject, provide, ref, Ref, watch, computed } from 'vue';
import { Menu, MenuButton, MenuItem, MenuItems, Switch, Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue';
import Modal from '../common/Modal.vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import { ExclamationCircleIcon, ChevronUpIcon } from '@heroicons/vue/24/outline';
import InfoTile from '../common/InfoTile.vue';
import { RemoteManager } from '../../models/RemoteManager';
import { CloudSyncProvider, CloudSyncRemote } from "../../models/CloudSync";
import { pushNotification, Notification } from 'houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey } from '../../keys/injection-keys';
import { cloudSyncProviders } from '../../models/CloudSync';
import { providerLogos } from '../../utils/providerLogos';

const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remote manager not provided!");
const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, "remotes not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");

const selectedProvider = ref<CloudSyncProvider>();
const remoteName = ref(''); 
const remoteNameErrorTag = ref('');
const creating = ref(false);

const basicParameters = computed(() => {
    if (!selectedProvider.value) return [];
    return Object.entries(selectedProvider.value.parameters.parameters)
        .filter(([_, parameter]) => !parameter.advanced);
});

const advancedParameters = computed(() => {
    if (!selectedProvider.value) return [];
    return Object.entries(selectedProvider.value.parameters.parameters)
        .filter(([_, parameter]) => parameter.advanced);
});

const getPlaceholder = (parameter) => {
    const defaultValue = parameter.defaultValue;

    // Check if the default value is an object and if it's an empty object
    // if (typeof defaultValue === 'object' && defaultValue !== null && Object.keys(defaultValue).length === 0) {
    //     return 'Default is empty string ("")'; // Return an empty string if it's an empty object
    // }

    // Check if the default value is a string and not empty
    if (typeof defaultValue === 'string' && defaultValue !== "") {
        return `Default is ${defaultValue}`;
    }

    // Check if the default value is a primitive (number, boolean)
    if (typeof defaultValue === 'number' || typeof defaultValue === 'boolean') {
        return `Default is ${defaultValue}`;
    }

    return 'Default is empty string ("")';
};

const createRemoteBtn = async () => {

}

function oAuthBtn(selectedProvider: CloudSyncProvider) {
    // console.log('selectedProvider:', selectedProvider.name); 
    const ngrokUrl = `https://seemingly-settling-stud.ngrok-free.app/auth/${selectedProvider.type}`;

    // Redirect the user to the ngrok URL to start the Google OAuth process
    // window.location.href = ngrokUrl;
    // window.open(ngrokUrl, '_blank');
    const authWindow = window.open(ngrokUrl, '_blank', 'width=500,height=700');

    /* // Listen for a message back from the auth window when authentication is done
    window.addEventListener('message', (event) => {
        if (event.origin !== 'https://seemingly-settling-stud.ngrok-free.app') return; // Ensure it's from your trusted origin
        if (event.data === 'authSuccess') {
            authWindow!.close();
            // Fetch and process the token if needed
            // const token = localStorage.getItem('oauthToken');
            const token = fetchToken();
            if (token) {
                // Use the token
                console.log('token retrieved:', token);
            }
        }
    }); */
    // Poll to check when the auth window is closed
    const checkAuthWindowClosed = setInterval(() => {
        if (authWindow && authWindow.closed) {
            clearInterval(checkAuthWindowClosed);
            console.log('Auth window closed');
            // Fetch the token after the window is closed
            fetchToken().then((token) => {
                if (token) {
                    console.log('Token retrieved after auth window closed:', token);
                    // Handle the token (e.g., store it, use it, etc.)
                }
            });
        }
    }, 500); // Check every 500ms if the window is closed
}


async function fetchToken() {
    try {
        const response = await fetch('/api/proxy-get-tokens', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin' // Ensure cookies are sent if using sessions
        });

        if (response.ok) {
            const data = await response.json();
            const token = data.token;
            console.log('token:', token);
            return token;
        } else {
            console.error('Token not available');
        }
    } catch (error) {
        console.error('Error fetching token:', error);
    }
}



// Function to fetch logo and color
function getProviderLogo(selectedProvider: CloudSyncProvider): string {
    if (selectedProvider.type === "s3") {
        return providerLogos[`${selectedProvider.type}-${selectedProvider.parameters.provider!}`]?.logo || "";
    } else {
        return providerLogos[selectedProvider.type]?.logo || "";
    }
}

function getProviderColor(selectedProvider: CloudSyncProvider): string {
    if (selectedProvider.type == "s3") {
        return providerLogos[`${selectedProvider.type}-${selectedProvider.parameters.provider!}`].mainColor;
    } else {
        return providerLogos[selectedProvider.type].mainColor || "#000000";
    }
}


const emit = defineEmits(['close']);
const showCreateRemote = inject<Ref<boolean>>('show-create-remote')!;

    console.log('REMOTES:', existingRemotes)!;

const errorList = ref<string[]>([]);

const closeModal = () => {
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
    await loadCloseConfirmationComponent();
    showCloseConfirmation.value = true;
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
</script>