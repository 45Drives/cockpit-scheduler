<template>
    <Modal @close="closeModal" :isOpen="showSettings" :margin-top="'mt-10'" :width="'w-3/5'" :min-width="'min-w-3/5'"
        :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="true">
        <template v-slot:title>
            <div class="text-lg font-semibold text-default">
                <h3>Scheduler Settings</h3>
            </div>
        </template>
        <template v-slot:content>
            <div class="space-y-6">

                <!-- Log Maintenance Section -->
                <div class="border border-default rounded-md p-4 bg-accent">
                    <h4 class="text-sm font-semibold text-default mb-3">Log Maintenance</h4>
                    <p class="text-xs text-muted mb-3">
                        Clean up debug log files used by scheduler tasks. Journal logs (systemd) are managed system-wide.
                    </p>
                    <div class="flex flex-col gap-3">
                        <div class="flex items-center gap-3">
                            <button class="btn btn-danger h-fit" @click="vacuumAllLogs" :disabled="vacuuming">
                                {{ vacuuming ? 'Cleaning...' : 'Clean All Debug Logs' }}
                            </button>
                            <span class="text-xs text-muted">Truncates all scheduler debug log files in /tmp/</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <div class="flex items-center gap-2">
                                <label class="text-sm text-default whitespace-nowrap">Vacuum journal older than</label>
                                <input type="number" v-model.number="vacuumDays" min="1" max="365"
                                    class="w-20 text-default input-textlike bg-default" placeholder="7" />
                                <span class="text-sm text-default">days</span>
                            </div>
                            <button class="btn btn-secondary h-fit" @click="vacuumJournal" :disabled="vacuumingJournal">
                                {{ vacuumingJournal ? 'Vacuuming...' : 'Vacuum Journal' }}
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Backup & Restore Section -->
                <div class="border border-default rounded-md p-4 bg-accent">
                    <h4 class="text-sm font-semibold text-default mb-3">Backup & Restore</h4>
                    <p class="text-xs text-muted mb-3">
                        Export all task configurations to a JSON file for backup. Import a previously exported backup to restore tasks.
                        Existing tasks with the same name will be skipped during import.
                    </p>
                    <div class="flex flex-col gap-3">
                        <div class="flex items-center gap-3">
                            <button class="btn btn-primary h-fit inline-flex items-center gap-2" @click="exportTasks" :disabled="busy">
                                <svg v-if="exporting" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                </svg>
                                {{ exporting ? 'Exporting...' : 'Export All Tasks' }}
                            </button>
                            <span class="text-xs text-muted">Download task configurations as a JSON backup file</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <label class="btn btn-secondary h-fit inline-flex items-center gap-2" :class="{ 'opacity-50 pointer-events-none': busy }">
                                <svg v-if="importing" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                </svg>
                                {{ importing ? 'Importing...' : 'Import Tasks' }}
                                <input type="file" accept=".json" class="hidden" @change="handleImportFile"
                                    :disabled="busy" ref="fileInput" />
                            </label>
                            <span class="text-xs text-muted">Upload a JSON backup file to restore task configurations</span>
                        </div>
                        <div v-if="importResult" class="border border-default rounded-md p-3 bg-well text-sm">
                            <p v-if="importResult.imported.length" class="text-success">
                                Imported: {{ importResult.imported.join(', ') }}
                            </p>
                            <p v-if="importResult.renamed.length" class="text-blue-500">
                                Renamed (config differs): {{ importResult.renamed.join(', ') }}
                            </p>
                            <p v-if="importResult.skipped.length" class="text-warning">
                                Skipped (identical): {{ importResult.skipped.join(', ') }}
                            </p>
                            <p v-if="importResult.errors.length" class="text-danger">
                                Errors: {{ importResult.errors.join('; ') }}
                            </p>
                        </div>
                    </div>
                </div>

            </div>
        </template>
        <template v-slot:footer>
            <div class="w-full">
                <div class="button-group-row w-full justify-between">
                    <button @click.stop="closeModal" class="btn btn-danger h-fit">Close</button>
                </div>
            </div>
        </template>
    </Modal>

    <div v-if="showVacuumConfirmation">
        <component :is="confirmationComponent" @close="showVacuumConfirmation = false"
            :showFlag="showVacuumConfirmation" :title="confirmationTitle"
            :message="confirmationMessage"
            :confirmYes="confirmationYes" :confirmNo="confirmationNo" :operation="confirmationOperation"
            :operating="confirmationOperating" />
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import Modal from '../common/Modal.vue';
import { pushNotification, Notification } from '@45drives/houston-common-ui';
import { injectWithCheck } from '../../composables/utility';
import { schedulerInjectionKey, loadingInjectionKey } from '../../keys/injection-keys';
import { TaskExecutionLog } from '../../models/TaskLog';

interface SchedulerSettingsProps {
    showSettings: boolean;
}

const props = defineProps<SchedulerSettingsProps>();
const emit = defineEmits(['close', 'update:showSettings']);

const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");
const myTaskLog = new TaskExecutionLog([]);
const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");

const vacuuming = ref(false);
const vacuumingJournal = ref(false);
const vacuumDays = ref(7);
const exporting = ref(false);
const importing = ref(false);
const importResult = ref<{ imported: string[]; skipped: string[]; renamed: string[]; errors: string[] } | null>(null);
const fileInput = ref<HTMLInputElement>();
const busy = computed(() => exporting.value || importing.value);

const showVacuumConfirmation = ref(false);
const confirmationComponent = ref();
const confirmationTitle = ref('');
const confirmationMessage = ref('');
const confirmationYes = ref<() => Promise<void>>(async () => {});
const confirmationNo = ref<() => Promise<void>>(async () => {});
const confirmationOperation = ref('');
const confirmationOperating = computed(() => vacuuming.value || vacuumingJournal.value);

function closeModal() {
    emit('update:showSettings', false);
    emit('close');
}

async function showConfirmation(title: string, message: string, operation: string, onConfirm: () => Promise<void>) {
    const module = await import('../common/ConfirmationDialog.vue');
    confirmationComponent.value = module.default;
    confirmationTitle.value = title;
    confirmationMessage.value = message;
    confirmationOperation.value = operation;
    confirmationYes.value = onConfirm;
    confirmationNo.value = async () => { showVacuumConfirmation.value = false; };
    showVacuumConfirmation.value = true;
}

async function vacuumAllLogs() {
    await showConfirmation(
        'Clean All Debug Logs',
        'Are you sure you want to truncate all scheduler debug log files?',
        'cleaning',
        async () => {
            vacuuming.value = true;
            try {
                const result = await myTaskLog.vacuumAllSchedulerLogs(0);
                if (result.success) {
                    pushNotification(new Notification('Logs Cleaned', result.message, 'success', 5000));
                } else {
                    pushNotification(new Notification('Clean Failed', result.message, 'error', 5000));
                }
            } finally {
                vacuuming.value = false;
                showVacuumConfirmation.value = false;
            }
        }
    );
}

async function vacuumJournal() {
    if (vacuumDays.value < 1) {
        pushNotification(new Notification('Invalid Input', 'Days must be at least 1.', 'error', 4000));
        return;
    }
    await showConfirmation(
        'Vacuum Journal',
        `Are you sure you want to vacuum journal entries older than ${vacuumDays.value} day(s)?`,
        'vacuuming',
        async () => {
            vacuumingJournal.value = true;
            try {
                const result = await myTaskLog.vacuumAllSchedulerLogs(vacuumDays.value);
                if (result.success) {
                    pushNotification(new Notification('Journal Vacuumed', result.message, 'success', 5000));
                } else {
                    pushNotification(new Notification('Vacuum Failed', result.message, 'error', 5000));
                }
            } finally {
                vacuumingJournal.value = false;
                showVacuumConfirmation.value = false;
            }
        }
    );
}

async function exportTasks() {
    exporting.value = true;
    try {
        const json = await myScheduler.exportTasks();
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const date = new Date().toISOString().slice(0, 10);
        a.download = `scheduler-backup-${date}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        pushNotification(new Notification('Export Complete', `Exported ${myScheduler.taskInstances.length} task(s).`, 'success', 5000));
    } catch (e) {
        pushNotification(new Notification('Export Failed', String(e), 'error', 5000));
    } finally {
        exporting.value = false;
    }
}

async function handleImportFile(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    importing.value = true;
    importResult.value = null;

    try {
        const text = await file.text();
        const result = await myScheduler.importTasks(text);
        importResult.value = result;

        if (result.imported.length > 0) {
            pushNotification(new Notification('Import Complete', `Imported ${result.imported.length} task(s).`, 'success', 5000));
            loading.value = true;
            try { await myScheduler.loadTaskInstances(); } finally { loading.value = false; }
        }

        if (result.errors.length > 0) {
            pushNotification(new Notification('Import Errors', result.errors.join('; '), 'error', 8000));
        }
    } catch (e) {
        pushNotification(new Notification('Import Failed', String(e), 'error', 5000));
    } finally {
        importing.value = false;
        // Reset file input so the same file can be selected again
        if (fileInput.value) fileInput.value.value = '';
    }
}
</script>
