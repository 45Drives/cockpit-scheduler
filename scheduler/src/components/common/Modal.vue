<template>
	<TransitionRoot as="template" :show="open">
	  <Dialog as="div" class="fixed inset-0 z-10 overflow-y-auto" @close="props.closeOnBackgroundClick && closeModal()" :initialFocus="closeButtonRef">
		<TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
		  <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
		</TransitionChild>
  
		<div class="fixed inset-0 z-10 overflow-y-auto" @click="props.closeOnBackgroundClick && closeModal()">
		  <div :class="['flex', props.marginTop, 'items-start', 'justify-center', 'p-4', 'text-center']" @click.stop>
			<TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95" enter-to="opacity-100 translate-y-0 sm:scale-100" leave="ease-in duration-200" leave-from="opacity-100 translate-y-0 sm:scale-100" leave-to="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95">
			  <DialogPanel :class="[props.width, props.minWidth, (props.height ? props.height : 'h-fit'), (props.minHeight ? props.minHeight : 'min-h-96'), 'relative', 'overflow-visible', 'rounded-lg', 'bg-default', 'px-4', 'pb-4', 'pt-5', 'text-left', 'shadow-xl', 'transition-all']">
				
				<div class="absolute right-0 top-0 pr-4 pt-4">
				  <button ref="closeButtonRef" type="button" class="rounded-md bg-default text-default" @click="props.closeConfirm ? props.closeConfirm() : closeModal()">
					<span class="sr-only">Close</span>
					<XMarkIcon class="h-5 w-5" aria-hidden="true" />
				  </button>
				</div>
  
				<div class="sm:flex items-center">
				  <div class="w-full mt-3 text-left sm:mt-0">
					
					<DialogTitle as="h3" class="text-base font-semibold leading-6 text-default" tabindex="-1">
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
  import { XMarkIcon } from '@heroicons/vue/24/outline'
  
  interface ModalProps {
	isOpen: boolean;
	marginTop: string;
	width: string;
	minWidth: string;
	height?: string;
	minHeight?: string;
	closeOnBackgroundClick: boolean;
	closeConfirm?: () => Promise<void>;
  }
  
  const props = defineProps<ModalProps>();
  
  const open = ref(props.isOpen);
  const closeModal = () => {
	  emit('close');
  }
  
  const emit = defineEmits(['close']);
  const closeButtonRef = ref<HTMLElement | null>(null);
  
  </script>
  