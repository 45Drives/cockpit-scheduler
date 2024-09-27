<template>
    <Modal @close="closeModal" :isOpen="showCreateRemote" :margin-top="'mt-24'" :width="'w-3/5'"
        :min-width="'min-w-3/5'" :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="false"
        :closeConfirm="closeBtn">
        <template v-slot:title>
            Create Rclone Remote
        </template>
        <template v-slot:content>
        </template>
        <template v-slot:footer>

        </template>
    </Modal>
    <div v-if="showCloseConfirmation">
        <component :is="closeConfirmationComponent" @close="updateShowCloseConfirmation"
            :showFlag="showCloseConfirmation" :title="'Cancel Create Remote'"
            :message="'Are you sure? This remote configuration will be lost.'" :confirmYes="confirmCancel"
            :confirmNo="cancelCancel" :operation="'canceling'" :operating="cancelingAddTask" />
    </div>
</template>
<script setup lang="ts">
import { inject, provide, ref, Ref, watch } from 'vue';
import Modal from '../common/Modal.vue';
import ParameterInput from '../parameters/ParameterInput.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import InfoTile from '../common/InfoTile.vue';
import { RemoteManager } from '../../models/RemoteManager';
import { CloudSyncRemote } from "../../models/CloudSync";
import { pushNotification, Notification } from 'houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey } from '../../keys/injection-keys';


const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, "remote manager not provided!");
const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, "remotes not provided!");
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");

const emit = defineEmits(['close']);
const showCreateRemote = inject<Ref<boolean>>('show-create-remote')!;

    console.log('REMOTES:', existingRemotes)!;

const errorList = ref<string[]>([]);

const closeModal = () => {
    showCreateRemote.value = false;
    emit('close');
}

const cancelingAddTask = ref(false);
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