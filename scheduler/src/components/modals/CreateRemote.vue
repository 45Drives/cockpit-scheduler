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
                <div name="cloud-prvider" v-if="Object.keys(cloudSyncProviders).length > 0">
                    <label for="cloud-prvider-selection" class="block text-sm leading-6 text-default">Task
                        Template</label>
                    <select id="cloud-prvider-selection" v-model="selectedProvider" name="cloud-prvider-selection"
                        class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                        <option :value="undefined">Select Cloud Provider</option>
                        <option v-for="([key, provider], idx) in Object.entries(cloudSyncProviders)" :key="key"
                            :value="provider">
                            {{ provider.name }}
                        </option>
                    </select>
                </div>
                <div v-if="selectedProvider">
                    <!-- <ParameterInput ref="parameterInputComponent" :selectedProvider="selectedProvider" /> -->
                </div>
            </div>
        </template>
        <template v-slot:footer>
            <!-- <div class="w-full">
                <div class="button-group-row w-full justify-between">
                    <div class="button-group-row">
                        <button @click.stop="closeBtn()" id="close-add-task-btn" name="close-add-task-btn"
                            class="mt-1 btn btn-danger h-fit w-full">Close</button>
                    </div>
                    <div class="button-group-row">
                        <button disabled v-if="adding" id="adding-task-btn" type="button"
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
                        <button v-else-if="!adding && selectedTemplate" id="add-task-btn"
                            class="btn btn-primary h-fit w-full" @click="addTaskBtn">Add Task</button>
                        <button v-else disabled id="add-task-btn-error" class="btn btn-primary h-fit w-full"
                            @click="addTaskBtn">Add Task</button>
                    </div>
                </div>
            </div> -->
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
import { inject, provide, ref, Ref, watch } from 'vue';
import Modal from '../common/Modal.vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import InfoTile from '../common/InfoTile.vue';
import { RemoteManager } from '../../models/RemoteManager';
import { CloudSyncProvider, CloudSyncRemote } from "../../models/CloudSync";
import { pushNotification, Notification } from 'houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey } from '../../keys/injection-keys';
import { cloudSyncProviders } from '../../models/CloudSync';

const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remote manager not provided!");
const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, "remotes not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");

const selectedProvider = ref<CloudSyncProvider>();
const remoteName = ref(''); 
const remoteNameErrorTag = ref('');


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