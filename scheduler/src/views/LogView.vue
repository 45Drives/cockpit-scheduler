<template>
     <Modal @close="closeModal" :isOpen="showLogView" :margin-top="'mt-10'" :width="'w-3/5'" :min-width="'min-w-3/5'" :close-on-background-click="true">
        <template v-slot:title>
            Execution Log{{ (props.task ? ` for ${taskInstance!.name}` : '') }}
        </template>
        <template v-slot:content>
            <div>
                <ul role="list" class="divide-y divide-default">
                    <li v-for="taskEntry, taskIdx in taskLogEntries" :key="taskIdx">

                    </li>
                </ul>
            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
				<div class="button-group-row w-full justify-between">
                    <button @click.stop="closeModal" id="close-edit-task-btn" name="close-edit-task-btn" class="btn btn-danger h-fit w-full">Close</button>      
				</div>
			</div>
        </template>
    </Modal>

</template>
<script setup lang="ts">
import { inject, provide, reactive, ref, Ref, computed, watch, onMounted } from 'vue';
import Modal from '../components/common/Modal.vue';
import { ExclamationCircleIcon, CheckCircleIcon } from '@heroicons/vue/24/outline';
import { Scheduler, TaskExecutionLog } from '../models/Classes';

interface LogViewProps {
    idKey: string;
    task?: TaskInstanceType;
}

const props = defineProps<LogViewProps>();
const emit = defineEmits(['close']);
const notifications = inject<Ref<any>>('notifications')!;
const showLogView = inject<Ref<boolean>>('show-log-view')!;
const myScheduler = inject<Scheduler>('scheduler')!;
const myTaskLog = inject<TaskExecutionLog>('log')!;
const loading = inject<Ref<boolean>>('loading')!;
const taskInstance = ref(props.task);
const taskLogEntries = ref<TaskExecutionResultType[]>([]);


const closeModal = () => {
    showLogView.value = false;
    emit('close');
}

onMounted(async () => {
    if (props.task !== undefined) {
        await myTaskLog.getLatestEntryFor(taskInstance.value);
    }
});
</script>