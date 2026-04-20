<template>
    <Modal @close="closeModal" :isOpen="showLogView" :margin-top="'mt-10'" :width="'w-3/5'" :min-width="'min-w-3/5'"
        :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="true">
        <template v-slot:title>
            <div class="text-lg font-semibold text-default mb-4">
                <h3>Latest Task Exection Result for <span class="italic">{{ props.task.name }}</span></h3>
            </div>
        </template>
        <template v-slot:content>
            <div>
                <div class="max-w-5xl mx-auto p-4 bg-accent text-default shadow-md rounded-lg">
                    <div class="grid grid-cols-3 gap-2 items-center">
                        <div v-if="thisLogEntry !== undefined" class="col-span-2 mb-4">
                            <p class="text-sm font-medium">Last Executed at {{ thisLogEntry.startDate }}</p>
                            <p class="text-sm font-medium">Finished at {{ thisLogEntry.finishDate }}</p>
                            <p class="text-sm font-medium">Exit Code: {{ thisLogEntry.exitCode }}</p>
                            <div v-if="!taskIsActive && !viewMoreLogs" class="flex flex-col w-full text-nowrap">
                                <p class="text-muted text-sm font-bold">
                                    Log View Idle
                                </p>
                                <p class="text-muted text-xs mt-0.5">
                                    (Task is not active or scheduled)
                                </p>
                            </div>
                            <div v-else-if="viewMoreLogs" class="flex flex-col w-full text-nowrap">
                                <p class="text-red-500 text-sm font-bold animate-pulse">
                                    LOG VIEW PAUSED
                                </p>
                                <p class="text-muted text-xs mt-0.5">
                                    (Refresh or Disable 'Show All' to view most recent log in real-time)
                                </p>
                            </div>
                            <div v-else>
                                <p class="text-green-500 text-sm font-bold">
                                    Log View Live
                                </p>
                                <p class="text-muted text-xs mt-0.5">
                                    (Viewing most recent log. Enable 'Show All' to pause view and see past logs)
                                </p>
                            </div>

                        </div>
                        <div v-else class="col-span-2 mb-4">
                            <p class="text-sm font-medium">No Last Execution Detected</p>
                        </div>

                        <div class="col-span-1 flex flex-col items-center gap-4">
                            <!-- Smaller Button -->
                            <button class="btn btn-primary px-3 py-1 text-sm flex items-center gap-2"
                                @click="refreshLogs">
                                Refresh Logs
                                <ArrowPathIcon class="h-4 w-4" aria-hidden="true" />
                            </button>

                            <!-- Label + Switch (Side by Side) -->
                            <div class="flex items-center gap-2">
                                <label class="text-sm font-medium text-default whitespace-nowrap">Show All</label>
                                <Switch v-model="viewMoreLogs"
                                    :class="[viewMoreLogs ? 'bg-secondary' : 'bg-default', 'mt-0.5 relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-slate-600 focus:ring-offset-2']">
                                    <span class="sr-only">Use setting</span>
                                    <span
                                        :class="[viewMoreLogs ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none relative inline-block h-5 w-5 transform rounded-full bg-default shadow ring-0 transition duration-200 ease-in-out']">
                                        <span
                                            :class="[viewMoreLogs ? 'opacity-0 duration-100 ease-out' : 'opacity-100 duration-200 ease-in', 'absolute inset-0 flex h-full w-full items-center justify-center transition-opacity']"
                                            aria-hidden="true">
                                            <svg class="h-3 w-3 text-muted" fill="none" viewBox="0 0 12 12">
                                                <path d="M4 8l2-2m0 0l2-2M6 6L4 4m2 2l2 2" stroke="currentColor"
                                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                                            </svg>
                                        </span>
                                        <span
                                            :class="[viewMoreLogs ? 'opacity-100 duration-200 ease-in' : 'opacity-0 duration-100 ease-out', 'absolute inset-0 flex h-full w-full items-center justify-center transition-opacity']"
                                            aria-hidden="true">
                                            <svg class="h-3 w-3 text-primary" fill="currentColor" viewBox="0 0 12 12">
                                                <path
                                                    d="M3.707 5.293a1 1 0 00-1.414 1.414l1.414-1.414zM5 8l-.707.707a1 1 0 001.414 0L5 8zm4.707-3.293a1 1 0 00-1.414-1.414l1.414 1.414zm-7.414 2l2 2 1.414-1.414-2-2-1.414 1.414zm3.414 2l4-4-1.414-1.414-4 4 1.414 1.414z" />
                                            </svg>
                                        </span>
                                    </span>
                                </Switch>
                            </div>
                        </div>

                    </div>
                 
                    <div v-if="!loadingLogs" class="bg-plugin-header p-4 rounded-lg mt-1">
                        <ul v-if="thisLogEntry !== undefined" ref="logContainer" role="list"
                            class="divide-y divide-default h-96 overflow-y-scroll">
                            <li v-if="!viewMoreLogs && !loadingMoreLogs"
                                v-for="line, idx in (thisLogEntry.output).split('\n')" :key="idx"
                                class="m-1 block text-sm leading-6 text-default" :class="logColor(line)">
                                {{ line }}
                            </li>
                            <li v-if="viewMoreLogs && !loadingMoreLogs"
                                class="m-1 block text-sm leading-6 text-default bold italic text-center bg-default">
                                All Logs
                            </li>
                            <li v-if="viewMoreLogs && !loadingMoreLogs"
                                v-for="line, idx in allLogsForThisTask.split('\n')" :key="idx"
                                class="m-1 block text-sm leading-6 text-default" :class="logColor(line)">
                                {{ line }}
                            </li>
                            <!-- <li v-if="viewMoreLogs && !loadingMoreLogs"
                                class="m-1 block text-sm leading-6 text-default bold italic text-center bg-default">
                                Most Recent Log</li>
                            <li v-if="viewMoreLogs && !loadingMoreLogs"
                                v-for="line, idx in (thisLogEntry.output).split('\n')" :key="idx"
                                class="m-1 block text-sm leading-6 text-default" :class="logColor(line)">
                                {{ line }}
                            </li> -->
                            <li v-if="loadingMoreLogs" class="flex items-center justify-center">
                                <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                                    :fillColor="'fill-gray-500'" />
                            </li>
                        </ul>
                    </div>
                    <div v-else class="bg-plugin-header p-4 rounded-lg mt-1">
                        <div class="flex items-center justify-center">
                            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                                :fillColor="'fill-gray-500'" />
                        </div>
                    </div>
                </div>
                <div class="button-group-row items-center justify-around mt-2">
                    <!-- Debug Log Button -->
                    <button class="btn btn-secondary px-3 py-1 text-sm flex items-center gap-2 h-fit"
                        @click="toggleDebugLog" :disabled="loadingDebugLog">
                        {{ showDebugLog ? 'Hide' : 'View' }} Debug Log
                        <svg v-if="loadingDebugLog" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg"
                            fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4">
                            </circle>
                            <path class="opacity-75" fill="currentColor"
                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                        </svg>
                    </button>

                    <!-- Clean Logs Button -->
                    <button class="btn btn-danger px-3 py-1 text-sm flex items-center gap-2 h-fit"
                        @click="cleanTaskLogs" :disabled="cleaningLogs">
                        {{ cleaningLogs ? 'Cleaning...' : 'Clean Debug Log' }}
                        <svg v-if="cleaningLogs" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg"
                            fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4">
                            </circle>
                            <path class="opacity-75" fill="currentColor"
                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                        </svg>
                    </button>
                </div>
                <!-- Debug Log Section -->
                <div v-if="showDebugLog" class="mt-2 bg-plugin-header p-4 rounded-lg">
                    <h4 class="text-sm font-semibold text-default mb-2">Debug Log</h4>
                    <div class="h-64 overflow-y-scroll bg-accent rounded p-2">
                        <pre class="text-xs text-muted whitespace-pre-wrap break-words">{{ debugLogContent }}</pre>
                    </div>
                </div>

            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
                <div class="button-group-row w-full justify-between">
                    <button @click.stop="closeModal" id="close-view-logs-btn" name="close-view-logs-btn"
                        class="btn btn-danger h-fit w-full">Close</button>
                </div>
            </div>
        </template>
    </Modal>

    <div v-if="showCleanConfirmation">
        <component :is="cleanConfirmationComponent" @close="showCleanConfirmation = false"
            :showFlag="showCleanConfirmation" :title="'Clean Debug Log'"
            :message="'Are you sure you want to clean the debug log for this task?'"
            :confirmYes="confirmCleanLogs" :confirmNo="cancelCleanLogs" :operation="'cleaning'"
            :operating="cleaningLogs" />
    </div>

</template>
<script setup lang="ts">
import { inject, ref, Ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue';
import { ArrowPathIcon } from '@heroicons/vue/24/outline';
import { Switch } from '@headlessui/vue';
import Modal from '../../components/common/Modal.vue';
import CustomLoadingSpinner from '../../components/common/CustomLoadingSpinner.vue';
import { injectWithCheck } from '../../composables/utility'
import { logInjectionKey } from '../../keys/injection-keys';
import { pushNotification, Notification } from '@45drives/houston-common-ui';

interface LogViewProps {
    idKey: string;
    task: TaskInstanceType;
}

const props = defineProps<LogViewProps>();
const emit = defineEmits(['close']);
const showLogView = inject<Ref<boolean>>('show-log-view')!;
const myTaskLog = injectWithCheck(logInjectionKey, "log not provided!");
const loadingLogs = ref(false);
const loadingMoreLogs = ref(false);
const taskInstance = ref(props.task);
const thisLogEntry = ref<TaskExecutionResultType>();
const viewMoreLogs = ref(false);
const allLogsForThisTask = ref('');
const pollInterval = ref();
const showDebugLog = ref(false);
const debugLogContent = ref('');
const loadingDebugLog = ref(false);
const cleaningLogs = ref(false);
const showCleanConfirmation = ref(false);
const cleanConfirmationComponent = ref();

const taskIsActive = computed(() => props.task.schedule.enabled);

const closeModal = () => {
    showLogView.value = false;
    emit('close');
}

function logColor(line: string) {
    if (line.includes('systemd')) {
        if (line.includes('Failed') || line.includes('FAILURE') || line.includes('Stopped') || line.includes('error') || line.includes('Error') || line.includes('ERROR') || line.includes('Exception')) {
            return 'text-danger';
        } else if (line.includes('Succeeded') || line.includes('Starting') || line.includes('Started')) {
            return 'text-success';
        } else if (line.includes('restart') || line.includes('too quickly')) {
            return 'text-warning';
        }
    } else if (line.includes('python')) {
        return 'text-default';
    } else {
        return 'text-muted';
    }
}

async function toggleDebugLog() {
    if (showDebugLog.value) {
        showDebugLog.value = false;
        return;
    }
    loadingDebugLog.value = true;
    try {
        debugLogContent.value = await myTaskLog.getDebugLog(taskInstance.value);
    } catch (e) {
        debugLogContent.value = `Failed to read debug log: ${e}`;
    } finally {
        loadingDebugLog.value = false;
        showDebugLog.value = true;
    }
}

async function cleanTaskLogs() {
    const module = await import('../common/ConfirmationDialog.vue');
    cleanConfirmationComponent.value = module.default;
    showCleanConfirmation.value = true;
}

const confirmCleanLogs = async () => {
    cleaningLogs.value = true;
    try {
        const result = await myTaskLog.clearLogsForTask(taskInstance.value);
        if (result.success) {
            pushNotification(new Notification('Logs Cleaned', result.message, 'success', 5000));
            // Refresh the debug log view if it was open
            if (showDebugLog.value) {
                debugLogContent.value = await myTaskLog.getDebugLog(taskInstance.value);
            }
        } else {
            pushNotification(new Notification('Clean Failed', result.message, 'error', 5000));
        }
    } catch (e) {
        pushNotification(new Notification('Clean Failed', String(e), 'error', 5000));
    } finally {
        cleaningLogs.value = false;
        showCleanConfirmation.value = false;
    }
};

const cancelCleanLogs = async () => {
    showCleanConfirmation.value = false;
};

async function refreshLogs() {
    loadingLogs.value = true;
    loadingMoreLogs.value = true;
    await preserveScrollPosition(async () => {
        try {
            // Always refresh the latest execution labels and log
            const latestLog = await myTaskLog.getLatestEntryFor(taskInstance.value);
            if (latestLog) {
                thisLogEntry.value = latestLog;
            }

            // If viewing all logs, also refresh previous logs
            if (viewMoreLogs.value) {
                // Show ALL logs for this unit (all runs)
                const logs = await myTaskLog.getEntriesFor(taskInstance.value);
                if (logs) {
                    allLogsForThisTask.value = logs;
                }
            }

        } catch (error) {
            console.error("Failed to refresh logs:", error);
        } finally {
            loadingLogs.value = false;
            loadingMoreLogs.value = false;
        }
    });
}


const fetchLatestLog = async () => {
    if (viewMoreLogs.value) {
        return; // Do not fetch latest logs when viewing all logs
    }

    loadingLogs.value = true;
    try {
        const latestLog = await myTaskLog.getLatestEntryFor(taskInstance.value);
        if (latestLog) {
            thisLogEntry.value = latestLog;
        }
    } catch (error) {
        console.error("Failed to fetch logs:", error);
    } finally {
        loadingLogs.value = false;
    }
};

const fetchAllLogs = async () => {
    if (!viewMoreLogs.value) {
        return; // Only fetch all logs when explicitly enabled
    }

    loadingMoreLogs.value = true;
    try {
        const logs = await myTaskLog.getEntriesFor(taskInstance.value);
        if (logs) {
            allLogsForThisTask.value = logs;
        }
    } catch (error) {
        console.error("Failed to fetch logs:", error);
    } finally {
        loadingMoreLogs.value = false;
    }
};

const logContainer = ref<HTMLElement | null>(null);

const preserveScrollPosition = async (fetchFunction: () => Promise<void>) => {
    if (!logContainer.value) return;

    const previousScrollHeight = logContainer.value.scrollHeight;
    const previousScrollTop = logContainer.value.scrollTop;

    await fetchFunction();

    nextTick(() => {
        if (logContainer.value) {
            logContainer.value.scrollTop = previousScrollTop + (logContainer.value.scrollHeight - previousScrollHeight);
        }
    });
};


const startPolling = () => {
    stopPolling(); // Ensure no duplicate intervals

    if (!taskIsActive.value) return; // Don't poll for inactive tasks

    pollInterval.value = setInterval(() => {
        if (!viewMoreLogs.value) {
            fetchLatestLog(); // Keep polling latest logs
        }
    }, 30000);
};

const stopPolling = () => {
    if (pollInterval.value) {
        clearInterval(pollInterval.value);
        pollInterval.value = null;
    }
};

watch(viewMoreLogs, async (newVal) => {
    if (newVal) {
        stopPolling(); // Stop polling when viewing all logs
        await preserveScrollPosition(refreshLogs); // Use the better refresh logic
    } else {
        if (taskIsActive.value) {
            startPolling(); // Resume polling when viewing only the latest log (and task is active)
        }
        refreshLogs(); // Ensure latest logs are refreshed when switching back
    }
});
onMounted(() => {
    fetchLatestLog();
    if (taskIsActive.value) {
        startPolling();
    }
});

onUnmounted(() => {
    stopPolling();
});

</script>