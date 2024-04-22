<template>
    <Modal :isOpen="showFlag" @close="closeModal()" :marginTop="'mt-60'" :width="'w-96'" :minWidth="'min-w-min'">
        <template v-slot:title>
            <legend class="flex justify-center">{{ props.title }}</legend>
        </template>
        <template v-slot:content>
            <div class="grid grid-flow-row mt-3 text-center">
                <p class="text-default">{{ props.message }}</p>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full grid grid-rows-1">
                <div class="button-group-row justify-around">
                    <button @click="confirmNo" id="confirmation-no" name="no-button" class="mt-1 btn btn-danger object-left justify-start h-fit w-full">No</button>
                    <button @click="confirmYes" id="confirmation-yes" name="yes-button" class="mt-1 btn btn-secondary object-right justify-end h-fit w-full">Yes</button>
                </div>
            </div>
        </template>
    </Modal>
</template>

<script setup lang="ts">
import { Switch } from '@headlessui/vue';
import { Ref, inject, ref, computed, watch} from 'vue';
import { upperCaseWord } from '../../composables/helpers';
import Modal from './Modal.vue';

interface ConfirmationDialogProps {
    title: string;
    message: string;
    confirmYes: ConfirmationCallback;
    confirmNo: ConfirmationCallback;
    showFlag: boolean;
}

const props = defineProps<ConfirmationDialogProps>();
const emit = defineEmits(['close']);

const showFlag = ref(props.showFlag);

const closeModal = () => {
    emit('close');
}

</script>