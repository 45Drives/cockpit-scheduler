<template>
    <Modal @close="closeModal" :isOpen="true" :margin-top="'mt-10'" :width="'w-full max-w-2xl'" :min-width="'min-w-0'"
        :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="true">
        <template v-slot:title>
            <div class="text-lg font-semibold text-default">
                <h3>Settings</h3>
            </div>
        </template>

        <template v-slot:content>
            <div class="space-y-4 text-default">

                <!-- Retry on Failure -->
                <div class="border border-default rounded-md p-4 bg-accent">
                    <h4 class="text-sm font-semibold text-default mb-1">Retry on Failure</h4>
                    <p class="text-xs text-muted mb-3">
                        If a backup fails, it can automatically try again before giving up.
                    </p>
                    <div class="flex flex-col gap-3">
                        <div class="flex items-center gap-3">
                            <label class="text-sm whitespace-nowrap w-40">Wait before retrying</label>
                            <input type="number" v-model.number="retrySettings.restart_sec" min="1" max="300"
                                class="w-24 input-textlike text-sm bg-default text-default" />
                            <span class="text-sm text-muted">seconds</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <label class="text-sm whitespace-nowrap w-40">Total attempts</label>
                            <input type="number" v-model.number="retrySettings.start_limit_burst" min="1" max="10"
                                class="w-24 input-textlike text-sm bg-default text-default" />
                            <span class="text-sm text-muted">including the first run</span>
                        </div>
                        <div class="flex flex-wrap items-center gap-2 mt-1">
                            <button class="btn btn-primary h-fit" @click="saveRetrySettings" :disabled="savingRetry">
                                {{ savingRetry ? 'Saving…' : 'Save' }}
                            </button>
                            <button class="btn btn-secondary h-fit" @click="migrateRetrySettings" :disabled="migratingRetry">
                                {{ migratingRetry ? 'Applying…' : 'Apply to Existing Backups' }}
                            </button>
                        </div>
                        <p class="text-xs text-muted">
                            Saving affects new backups. Existing backups keep their current settings until you apply the change.
                        </p>
                        <p v-if="retryMigrateResult" class="text-xs text-success">{{ retryMigrateResult }}</p>
                    </div>
                </div>

                <!-- Email Notifications -->
                <div class="border border-default rounded-md p-4 bg-accent">
                    <h4 class="text-sm font-semibold text-default mb-1">Email Notifications</h4>

                    <template v-if="detectingAlerts">
                        <p class="text-xs text-muted">Checking…</p>
                    </template>

                    <template v-else-if="alertsInstalled">
                        <p class="text-xs text-muted mb-3">
                            Get an email when a backup fails or finishes. Recipients and alert levels are managed in Cockpit Alerts.
                        </p>
                        <button class="btn btn-primary h-fit" @click="openAlertsPage">Open Email Settings</button>
                    </template>

                    <template v-else>
                        <p class="text-xs text-muted mb-3">
                            Email notifications need the <strong>cockpit-alerts</strong> package. Install it to be notified when a backup fails.
                        </p>
                        <div class="flex flex-wrap items-center gap-3">
                            <button class="btn btn-primary h-fit" @click="installAlerts" :disabled="installingAlerts">
                                {{ installingAlerts ? 'Installing…' : 'Install Email Notifications' }}
                            </button>
                            <span v-if="installAlertsError" class="text-xs text-danger">{{ installAlertsError }}</span>
                        </div>
                    </template>
                </div>

                <!-- Status Refresh -->
                <div class="border border-default rounded-md p-4 bg-accent">
                    <h4 class="text-sm font-semibold text-default mb-1">Status Refresh</h4>
                    <p class="text-xs text-muted mb-3">
                        How often the backup list checks for updates. Slower refresh reduces load on the server.
                    </p>
                    <div class="flex flex-wrap items-center gap-2">
                        <button v-for="preset in pollPresets" :key="preset.id"
                            class="btn h-fit text-sm"
                            :class="activePreset === preset.id ? 'btn-primary' : 'btn-secondary'"
                            :disabled="savingPollSettings"
                            @click="savePollPreset(preset.id)">
                            {{ preset.label }}
                        </button>
                    </div>
                    <p class="text-xs text-muted mt-2">{{ activePresetDescription }}</p>
                </div>

            </div>
        </template>

        <template v-slot:footer>
            <div class="w-full">
                <div class="button-group-row w-full justify-between">
                    <button @click.stop="closeModal" class="btn btn-secondary h-fit">Close</button>
                </div>
            </div>
        </template>
    </Modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import Modal from '../common/Modal.vue';
import { pushNotification, Notification } from '@45drives/houston-common-ui';
import { runCommand } from '../../models/Scheduler';

const emit = defineEmits<{
    close: [];
    pollSettingsSaved: [{ statusPollMs: number; progressPollMs: number }];
}>();

const MIGRATE_SCRIPT = '/opt/45drives/houston/scheduler/scripts/migrate-retry-settings.py';

function closeModal() {
    emit('close');
}

/* ── Retry ── */
const retrySettings = ref({ restart_sec: 5, start_limit_burst: 3 });
const savingRetry = ref(false);
const migratingRetry = ref(false);
const retryMigrateResult = ref('');

/* ── Polling ── */
type PollPresetId = 'responsive' | 'balanced' | 'lowLoad';
const pollPresets: { id: PollPresetId; label: string; status: number; progress: number; description: string }[] = [
    { id: 'responsive', label: 'Fast', status: 5000, progress: 10000, description: 'Updates every 5 seconds. Best for watching a backup run.' },
    { id: 'balanced', label: 'Normal', status: 15000, progress: 30000, description: 'Updates every 15 seconds. Recommended for most setups.' },
    { id: 'lowLoad', label: 'Slow', status: 30000, progress: 60000, description: 'Updates every 30 seconds. Lightest load on the server.' },
];
const pollSettings = ref({ status_poll_ms: 5000, progress_poll_ms: 10000 });
const savingPollSettings = ref(false);

const activePreset = computed(() =>
    pollPresets.find(p => p.status === pollSettings.value.status_poll_ms)?.id ?? null
);
const activePresetDescription = computed(() =>
    pollPresets.find(p => p.id === activePreset.value)?.description
    ?? `Custom: updates every ${Math.round(pollSettings.value.status_poll_ms / 1000)} seconds.`
);

/* ── cockpit-alerts ── */
const alertsInstalled = ref(false);
const detectingAlerts = ref(true);
const installingAlerts = ref(false);
const installAlertsError = ref('');
const packageManager = ref<'dnf' | 'apt'>('dnf');

async function detectAlerts() {
    detectingAlerts.value = true;
    try {
        try {
            await runCommand(['test', '-d', '/usr/share/cockpit/alerts']);
            alertsInstalled.value = true;
            return;
        } catch { /* not found */ }
        try {
            await runCommand(['dnf', 'list', 'installed', 'cockpit-alerts']);
            alertsInstalled.value = true;
            return;
        } catch { /* not RPM or not installed */ }
        try {
            await runCommand(['dpkg', '-l', 'cockpit-alerts']);
            alertsInstalled.value = true;
            return;
        } catch { /* not installed */ }
        alertsInstalled.value = false;

        try {
            await runCommand(['which', 'apt']);
            packageManager.value = 'apt';
        } catch {
            packageManager.value = 'dnf';
        }
    } finally {
        detectingAlerts.value = false;
    }
}

function openAlertsPage() {
    const cockpit = (window as any).cockpit;
    if (cockpit?.jump) {
        cockpit.jump('/alerts');
    } else {
        window.open('/cockpit/@localhost/alerts/index.html', '_blank');
    }
}

async function installAlerts() {
    installingAlerts.value = true;
    installAlertsError.value = '';
    try {
        const cmd = packageManager.value === 'apt'
            ? ['apt', 'install', '-y', 'cockpit-alerts']
            : ['dnf', 'install', '-y', 'cockpit-alerts'];
        await runCommand(cmd, { superuser: 'require' });
        alertsInstalled.value = true;
        pushNotification(new Notification('Installed', 'Email notifications installed. Restart Cockpit to activate.', 'success', 5000));
    } catch (e: any) {
        installAlertsError.value = e?.message || String(e);
        pushNotification(new Notification('Install Failed', installAlertsError.value, 'error', 8000));
    } finally {
        installingAlerts.value = false;
    }
}

async function loadSettings() {
    try {
        const { stdout } = await runCommand(['python3', MIGRATE_SCRIPT, '--get'], { superuser: 'try' });
        const parsed = JSON.parse((stdout || '').trim());
        retrySettings.value = {
            restart_sec: Number(parsed?.restart_sec ?? retrySettings.value.restart_sec),
            start_limit_burst: Number(parsed?.start_limit_burst ?? retrySettings.value.start_limit_burst),
        };
        pollSettings.value = {
            status_poll_ms: Math.max(1000, Number(parsed?.ui_status_poll_ms ?? pollSettings.value.status_poll_ms)),
            progress_poll_ms: Math.max(1000, Number(parsed?.ui_progress_poll_ms ?? pollSettings.value.progress_poll_ms)),
        };
    } catch {
        // Use defaults silently
    }
}

async function saveRetrySettings() {
    savingRetry.value = true;
    retryMigrateResult.value = '';
    try {
        const payload = JSON.stringify(retrySettings.value);
        const { stdout } = await runCommand(['python3', MIGRATE_SCRIPT, '--set', payload], { superuser: 'require' });
        const result = JSON.parse(stdout.trim());
        if (result.success) {
            pushNotification(new Notification('Settings Saved', 'New backups will use these retry settings.', 'success', 4000));
        }
    } catch (e: any) {
        pushNotification(new Notification('Save Failed', e?.message || String(e), 'error', 5000));
    } finally {
        savingRetry.value = false;
    }
}

async function migrateRetrySettings() {
    migratingRetry.value = true;
    retryMigrateResult.value = '';
    try {
        const payload = JSON.stringify(retrySettings.value);
        await runCommand(['python3', MIGRATE_SCRIPT, '--set', payload], { superuser: 'require' });
        const { stdout } = await runCommand(['python3', MIGRATE_SCRIPT, '--migrate'], { superuser: 'require' });
        const result = JSON.parse(stdout.trim());
        if (result.success) {
            const count = Number(result?.patched ?? 0);
            retryMigrateResult.value = `Updated ${count} existing backup${count === 1 ? '' : 's'}.`;
            pushNotification(new Notification('Applied', retryMigrateResult.value, 'success', 4000));
        }
    } catch (e: any) {
        pushNotification(new Notification('Apply Failed', e?.message || String(e), 'error', 5000));
    } finally {
        migratingRetry.value = false;
    }
}

async function savePollPreset(id: PollPresetId) {
    const preset = pollPresets.find(p => p.id === id);
    if (!preset) return;

    savingPollSettings.value = true;
    try {
        const payload = JSON.stringify({
            ui_status_poll_ms: preset.status,
            ui_progress_poll_ms: preset.progress,
        });
        const { stdout } = await runCommand(['python3', MIGRATE_SCRIPT, '--set', payload], { superuser: 'require' });
        const result = JSON.parse(stdout.trim());
        if (result.success) {
            pollSettings.value = {
                status_poll_ms: Number(result?.settings?.ui_status_poll_ms ?? preset.status),
                progress_poll_ms: Number(result?.settings?.ui_progress_poll_ms ?? preset.progress),
            };
            emit('pollSettingsSaved', {
                statusPollMs: pollSettings.value.status_poll_ms,
                progressPollMs: pollSettings.value.progress_poll_ms,
            });
            pushNotification(new Notification('Settings Saved', `Status refresh set to ${preset.label}.`, 'success', 4000));
        }
    } catch (e: any) {
        pushNotification(new Notification('Save Failed', e?.message || String(e), 'error', 5000));
    } finally {
        savingPollSettings.value = false;
    }
}

onMounted(() => {
    detectAlerts();
    loadSettings();
});
</script>
