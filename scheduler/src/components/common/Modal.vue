<template>
	<TransitionRoot as="template" :show="open">
		<Dialog as="div" class="relative z-10" @close="props.closeOnBackgroundClick && closeModal()">
			<TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
				<div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
			</TransitionChild>

			<div class="fixed inset-0 z-10 overflow-y-auto" @click="props.closeOnBackgroundClick && closeModal()">
				<div :class="['flex', props.marginTop, 'items-start', 'justify-center', 'p-4', 'text-center']" @click.stop>
					<TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95" enter-to="opacity-100 translate-y-0 sm:scale-100" leave="ease-in duration-200" leave-from="opacity-100 translate-y-0 sm:scale-100" leave-to="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95">
						<DialogPanel :class="[props.width, props.minWidth, 'h-fit', 'min-h-96', 'overflow-visible', 'rounded-lg', 'bg-default', 'px-4', 'pb-4', 'pt-5', 'text-left', 'shadow-xl', 'transition-all']">
							
							<!-- <div class="absolute right-0 top-0 hidden pr-4 pt-4 sm:block">
								<button type="button" class="rounded-md bg-default text-default" @click="open = false">
									<span class="sr-only">Close</span>
									<XMarkIcon class="h-6 w-6" aria-hidden="true" />
								</button>
							</div> -->

							<div class="sm:flex items-center">
								<div class="w-full mt-3 text-center sm:mt-0 sm:text-left">
									<DialogTitle as="h3" class="text-base font-semibold leading-6 text-default">
										<slot name="title"/>
									</DialogTitle>
									<div class="mt-2 w-full">
										<p class="text-sm text-muted">
											<slot name="content"/>
										</p>
									</div>
								</div>
							</div>
							<div class="w-full mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
								<slot name="footer"/>
							</div>
							
						</DialogPanel>
					</TransitionChild>
				</div>
			</div>

		</Dialog>
	</TransitionRoot>
</template>

<script setup lang="ts">
import { ref, defineProps } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'
// import { XMarkIcon } from '@heroicons/vue/24/outline'

interface ModalProps {
	isOpen: boolean;
	marginTop: string;
	width: string;
	minWidth: string;
	closeOnBackgroundClick: boolean;
}

const props = defineProps<ModalProps>();

// const open = ref(true)
const open = ref(props.isOpen);
const closeModal = () => {
    emit('close');
}

const emit = defineEmits(['close']);

// const handleBackgroundClick = (event) => {
//   // Ensure that the modal content is not the target of the click
//   if (event.target === event.currentTarget) {
//     closeModal;
//   }
// };

</script>