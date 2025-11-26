<template>
    <CardContainer class="w-full h-full p-2 text-default">
        <template #title>
            <div class="flex items-center gap-2">
                Cloud Accounts
                <span v-if="panel === 'create'" class="text-xs text-muted">• Add New</span>
                <span v-else-if="panel === 'edit'" class="text-xs text-muted">• Manage</span>
                <img v-if="selectedProvider" :src="getProviderLogo(selectedProvider, undefined)" class="w-5 h-5" />
            </div>
        </template>
        <div>
            <div v-if="loading" class="flex items-center justify-center py-12">
                <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                    :fillColor="'fill-gray-500'" />
            </div>

            <div v-else class="grid grid-cols-12 gap-3">
                <!-- LEFT: list + actions -->
                <SimpleFormCard class="col-span-12 lg:col-span-4 p-3 rounded-md border border-default"
                    title="Your accounts">
                    <div class="flex gap-2 mb-2">
                        <input v-model="query" type="text" class="input-textlike w-full"
                            placeholder="Search accounts…" />
                        <button class="btn btn-primary" @click="startCreate">Add</button>
                    </div>

                    <ul role="list" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2">
                        <li v-for="r in filteredRemotes" :key="r.name">
                            <button class="btn w-full flex items-center justify-between"
                                :style="getButtonStyles(false, undefined, r)" @click="openEdit(r)" :title="r.name">
                                <div class="flex items-center gap-2">
                                    <span class="rounded-full bg-white w-5 h-5 grid place-items-center">
                                        <img :src="getProviderLogo(undefined, r)" class="w-4 h-4" />
                                    </span>
                                    <span class="truncate">{{ r.name }}</span>
                                </div>
                                <span class="text-xs opacity-80">{{ r.provider?.name ?? r.type }}</span>
                            </button>
                        </li>
                    </ul>
                </SimpleFormCard>

                <!-- RIGHT: Create / Edit panel -->
                <div class="col-span-12 lg:col-span-8 space-y-3">
                    <!-- Empty state -->
                    <SimpleFormCard v-if="panel === 'idle'" title="Get started"
                        class="p-3 rounded-md border border-default">
                        <p class="text-sm text-muted">Select an account on the left to manage it, or click <b>Add</b> to
                            create a new one.</p>
                    </SimpleFormCard>

                    <!-- CREATE (Simple first, Advanced collapsible) -->
                    <div v-else-if="panel === 'create'" class="space-y-3">
                        <!-- Simple: OAuth-first -->
                        <SimpleFormCard title="Choose a provider" description="These work with a quick sign-in."
                            class="p-3 rounded-md border border-default">
                            <div class="grid sm:grid-cols-3 gap-2">
                                <button v-for="p in oauthProviders" :key="p.type"
                                    class="btn w-full flex items-center justify-center gap-2"
                                    :class="selectedProvider?.type === p.type ? 'btn-primary' : 'btn-secondary'"
                                    :style="getButtonStyles(false, p)" @click="selectProvider(p)">
                                    <span class="rounded-full bg-white w-5 h-5 grid place-items-center">
                                        <img :src="getProviderLogo(p, undefined)" class="w-4 h-4" />
                                    </span>
                                    {{ p.name }}
                                </button>
                            </div>

                            <details class="mt-3">
                                <summary class="text-sm cursor-pointer">Advanced: more providers</summary>
                                <div class="grid sm:grid-cols-3 gap-2 mt-2">
                                    <button v-for="p in nonOauthProviders" :key="p.type"
                                        class="btn w-full flex items-center justify-center gap-2"
                                        :class="selectedProvider?.type === p.type ? 'btn-primary' : 'btn-secondary'"
                                        :style="getButtonStyles(false, p)" @click="selectProvider(p)">
                                        <span class="rounded-full bg-white w-5 h-5 grid place-items-center">
                                            <img :src="getProviderLogo(p, undefined)" class="w-4 h-4" />
                                        </span>
                                        {{ p.name }}
                                    </button>
                                </div>
                            </details>
                        </SimpleFormCard>

                        <SimpleFormCard v-if="selectedProvider"
                            :title="`Connect your account -> ${selectedProvider.name}`" :description="oauthBlurb"
                            class="p-3 rounded-md border border-default">
                            <template #header-right>
                                <div class="button-group-row">
                                    <button v-if="selectedProvider.providerParams.oAuthSupported && !oAuthenticated"
                                        class="btn btn-secondary" @click="oAuthBtn(selectedProvider)">
                                        Authenticate with {{ selectedProvider.name }}
                                    </button>
                                    <button v-else-if="selectedProvider.providerParams.oAuthSupported && oAuthenticated"
                                        class="btn btn-danger" @click="clearOAuth">
                                        Reset OAuth
                                    </button>
                                </div>
                            </template>
                            <!-- Policy links for OAuth providers -->
                            <div v-if="selectedProvider?.providerParams.oAuthSupported" class="mt-2 text-sm">
                                <a href="https://cloud-sync.45d.io/privacy" target="_blank" rel="noopener noreferrer"
                                    class="underline hover:opacity-80">Privacy Policy</a>
                                <span class="mx-2">•</span>
                                <a href="https://cloud-sync.45d.io/tos" target="_blank" rel="noopener noreferrer"
                                    class="underline hover:opacity-80">Terms of Service</a>
                            </div>

                            <!-- Advanced/manual fields tucked away -->
                            <details class="mt-2">
                                <summary class="text-sm cursor-pointer">Advanced parameters</summary>
                                <div class="grid sm:grid-cols-2 gap-2 mt-2">
                                    <div v-for="([key, schema]) in providerParameters" :key="String(key)">
                                        <label class="block text-xs text-default">{{ key }}</label>

                                        <!-- S3: render 'provider' as a select -->
                                        <template v-if="selectedProvider?.type === 's3' && key === 'provider'">
                                            <select v-model="providerValues.provider"
                                                class="input-textlike w-full mt-1">
                                                <option v-for="opt in (schema.allowedValues || s3ProviderOptions)"
                                                    :key="opt" :value="opt">
                                                    {{ opt }}
                                                </option>
                                            </select>
                                        </template>

                                        <!-- All other fields use the schema type -->
                                        <template v-else>
                                            <input v-if="schema.type === 'string'" v-model="providerValues[key]"
                                                class="input-textlike w-full mt-1" type="text" />

                                            <input v-else-if="schema.type === 'bool'" v-model="providerValues[key]"
                                                type="checkbox" class="h-4 w-4 mt-1" />

                                            <input v-else-if="schema.type === 'int'"
                                                v-model.number="providerValues[key]" class="input-textlike w-full mt-1"
                                                type="number" />

                                            <select v-else-if="schema.type === 'select'" v-model="providerValues[key]"
                                                class="input-textlike w-full mt-1">
                                                <option v-for="opt in (schema.allowedValues || [])" :key="opt"
                                                    :value="opt">
                                                    {{ opt }}
                                                </option>
                                            </select>

                                            <textarea v-else-if="schema.type === 'object' && key !== 'token'"
                                                v-model="providerValues[key]" rows="3"
                                                class="input-textlike w-full mt-1" />

                                            <!-- pretty JSON binding for token -->
                                            <textarea v-else-if="schema.type === 'object' && key === 'token'"
                                                v-model="displayToken" rows="3" class="input-textlike w-full mt-1"
                                                placeholder="Filled by OAuth" />
                                        </template>
                                    </div>
                                </div>
                            </details>

                        </SimpleFormCard>

                        <SimpleFormCard v-if="selectedProvider" title="Name your account"
                            class="p-3 rounded-md border border-default">
                            <label class="block text-sm text-default">Account name</label>
                            <input v-model="remoteName" class="input-textlike w-full mt-1"
                                placeholder="e.g. Team-Drive, Marketing-Dropbox" />
                        </SimpleFormCard>
                    </div>

                    <!-- EDIT -->
                    <div v-else-if="panel === 'edit'" class="space-y-3">
                        <SimpleFormCard title="Account details" class="p-3 rounded-md border border-default">
                            <label class="block text-sm text-default">Account name</label>
                            <input v-model="edit.name" class="input-textlike w-full mt-1" :disabled="!editMode" />

                            <label class="block text-sm text-default mt-3">Provider</label>
                            <select v-model="edit.provider" class="input-textlike w-full mt-1" :disabled="!editMode">
                                <option :value="edit.provider">{{ edit.provider?.name }}</option>
                                <option v-for="p in allProviders" :key="p.type" :value="p">{{ p.name }}</option>
                            </select>
                        </SimpleFormCard>

                        <SimpleFormCard title="Authentication" class="p-3 rounded-md border border-default">
                            <template #header-right>
                                <div class="button-group-row">
                                    <button v-if="edit.provider?.providerParams.oAuthSupported"
                                        class="btn btn-secondary" @click="oAuthBtn(edit.provider)"
                                        :disabled="!editMode">
                                        Reconnect
                                    </button>
                                    <button v-if="edit.provider?.providerParams.oAuthSupported" class="btn btn-danger"
                                        @click="() => { oAuthenticated = false; setEditParam('token', '') }"
                                        :disabled="!editMode">
                                        Reset OAuth
                                    </button>
                                </div>
                            </template>
                            <!-- Policy links for OAuth providers -->
                            <div v-if="edit.provider?.providerParams.oAuthSupported" class="mb-2 text-sm">
                                <a href="https://cloud-sync.45d.io/privacy" target="_blank" rel="noopener noreferrer"
                                    class="underline hover:opacity-80">Privacy Policy</a>
                                <span class="mx-2">•</span>
                                <a href="https://cloud-sync.45d.io/tos" target="_blank" rel="noopener noreferrer"
                                    class="underline hover:opacity-80">Terms of Service</a>
                            </div>
                            <details>
                                <summary class="text-sm cursor-pointer">Show parameters</summary>
                                <div class="grid sm:grid-cols-2 gap-2 mt-2">
                                    <div v-for="(schema, key) in (edit.provider?.providerParams?.parameters || {})"
                                        :key="String(key)">
                                        <label class="block text-xs text-default">{{ key }}</label>

                                        <!-- S3 only: 'provider' select bound to flat authParams -->
                                        <template v-if="edit.provider?.type === 's3' && String(key) === 'provider'">
                                            <select v-model="edit.params[key]" class="input-textlike w-full mt-1"
                                                :disabled="!editMode">
                                                <option v-for="opt in (schema.allowedValues || s3ProviderOptions)"
                                                    :key="opt" :value="opt">{{ opt }}</option>
                                            </select>
                                        </template>

                                        <template v-else>
                                            <input v-if="schema.type === 'string'" v-model="edit.params[key]"
                                                class="input-textlike w-full mt-1" type="text" :disabled="!editMode" />
                                            <input v-else-if="schema.type === 'bool'" type="checkbox"
                                                v-model="edit.params[key]" class="h-4 w-4 mt-1" :disabled="!editMode" />
                                            <input v-else-if="schema.type === 'int'" v-model.number="edit.params[key]"
                                                class="input-textlike w-full mt-1" type="number"
                                                :disabled="!editMode" />
                                            <select v-else-if="schema.type === 'select'" v-model="edit.params[key]"
                                                class="input-textlike w-full mt-1" :disabled="!editMode">
                                                <option v-for="opt in (schema.allowedValues || [])" :key="opt"
                                                    :value="opt">{{ opt }}</option>
                                            </select>
                                            <textarea v-else-if="schema.type === 'object' && String(key) !== 'token'"
                                                v-model="edit.params[key]" class="input-textlike w-full mt-1" rows="3"
                                                :disabled="!editMode" />
                                            <!-- pretty JSON for token -->
                                            <textarea v-else-if="schema.type === 'object' && String(key) === 'token'"
                                                v-model="editDisplayToken" class="input-textlike w-full mt-1" rows="3"
                                                :disabled="!editMode" />
                                        </template>
                                    </div>
                                </div>
                            </details>
                        </SimpleFormCard>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="w-full flex items-center justify-between gap-2">
                <button class="btn btn-danger" @click="handleClose">Close</button>

                <!-- CREATE actions -->
                <div v-if="panel === 'create'" class="flex gap-2">
                    <button class="btn btn-secondary" @click="resetCreate" :disabled="creating">Clear</button>
                    <button class="btn btn-primary" @click="saveCreate" :disabled="creating || !canCreate">Save
                        Account</button>
                </div>

                <!-- EDIT actions -->
                <div v-else-if="panel === 'edit'" class="flex gap-2">
                    <button v-if="!editMode" class="btn btn-secondary" @click="editMode = true">Edit</button>
                    <button v-else class="btn btn-secondary" @click="cancelEdit">Cancel Edit</button>
                    <button class="btn btn-danger" @click="deleteRemote" :disabled="deleting">Delete</button>
                    <button class="btn btn-primary" @click="saveEdit" :disabled="!hasEdits || saving">Save
                        Changes</button>
                </div>
            </div>
        </template>
    </CardContainer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import SimpleFormCard from '../../components/simple/SimpleFormCard.vue'
import CustomLoadingSpinner from '../common/CustomLoadingSpinner.vue'
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, remoteManagerInjectionKey, rcloneRemotesInjectionKey } from '../../keys/injection-keys'
import { CloudSyncProvider, CloudSyncRemote, cloudSyncProviders, getProviderLogo, getButtonStyles } from '../../models/CloudSync'
import { pushNotification, Notification, CardContainer } from '@45drives/houston-common-ui'

/** props/emit */
const props = defineProps<{ isOpen: boolean }>()
// const emit = defineEmits(['close'])

const router = useRouter()
const route = useRoute()
/** injections */
const loading = injectWithCheck(loadingInjectionKey, 'loading not provided!')
const myRemoteManager = injectWithCheck(remoteManagerInjectionKey, 'remote manager not provided!')
const existingRemotes = injectWithCheck(rcloneRemotesInjectionKey, 'remotes not provided!')

/** local state */
const panel = ref<'idle' | 'create' | 'edit'>('idle')

type CloudAuthParameter = { parameters: Record<string, { value: any; type: string; allowedValues?: string[]; defaultValue?: any }> };

function toFlat(auth: CloudAuthParameter): Record<string, any> {
    const out: Record<string, any> = {};
    for (const [k, p] of Object.entries(auth?.parameters || {})) out[k] = p?.value;
    return out;
}

function toAuth(
    flat: Record<string, any>,
    provider: CloudSyncProvider
): CloudAuthParameter {
    const base = provider.providerParams.parameters; // schema
    const parameters: CloudAuthParameter['parameters'] = {};

    for (const [k, schema] of Object.entries(base)) {
        const v = flat[k] ?? (schema as any).value ?? (schema as any).defaultValue;
        parameters[k] = { ...(schema as any), value: v };
    }
    return { parameters };
}

/** LEFT list */
const query = ref('')
const filteredRemotes = computed(() =>
    existingRemotes.value.filter((r: CloudSyncRemote) =>
        r.name.toLowerCase().includes(query.value.trim().toLowerCase()))
)

/** Providers */
const oauthTypes = ['dropbox', 'drive', 'google cloud storage']
const s3ProviderOptions = ['AWS', 'Wasabi', 'MinIO', 'Ceph', 'Other'];
const allProviders = Object.values(cloudSyncProviders)
const oauthProviders = computed(() => allProviders.filter(p => oauthTypes.includes(p.type)))
const nonOauthProviders = computed(() => allProviders.filter(p => !oauthTypes.includes(p.type)))

/** CREATE state */
const selectedProvider = ref<CloudSyncProvider>()
const providerValues = reactive<any>({})
const remoteName = ref('')
const creating = ref(false)
const oAuthenticated = ref(false)
const editingRemote = ref<any>()

const providerParameters = computed(() =>
    selectedProvider.value ? Object.entries(selectedProvider.value.providerParams.parameters) : []
)

watch(selectedProvider, (p) => {
    Object.keys(providerValues).forEach(k => delete providerValues[k])
    if (p) {
        for (const [k, param] of Object.entries(p.providerParams.parameters)) {
            providerValues[k] = (param as any).value ?? (param as any).defaultValue
        }
        oAuthenticated.value = false
    }
})

const displayToken = computed({
    get: () => {
        const t = providerValues.token
        if (!t) return ''
        return typeof t === 'object' ? JSON.stringify(t, null, 2) : String(t)
    },
    set: (val: string) => {
        try { providerValues.token = JSON.parse(val) } catch { providerValues.token = val }
    }
})

/** EDIT state */
const selectedRemote = ref<CloudSyncRemote>()
const editMode = ref(false)
const edit = reactive<{ name?: string; provider?: CloudSyncProvider; params: any }>({ params: {} })
const saving = ref(false)
const deleting = ref(false)

type Baseline = {
    name: string
    providerType: string
    params: any              // plain JSON (no class instances)
}

const snapshot = (r: CloudSyncRemote) => ({
    name: r.name,
    providerType: r.provider?.type ?? r.type,
    params: JSON.parse(JSON.stringify(r.authParams)) as CloudAuthParameter
});

function setEditFromBaseline(baseline: ReturnType<typeof snapshot>) {
    edit.name = baseline.name;
    edit.provider = cloudSyncProviders[baseline.providerType];
    // FLATTEN here:
    edit.params = toFlat(baseline.params);
}

// <-- store the pristine values here
const baseline = ref<Baseline | null>(null)

watch(selectedRemote, (r) => {
    if (!r) { panel.value = 'idle'; return }
    panel.value = 'edit'
    editMode.value = false

    // snapshot + populate form from plain data
    const b = snapshot(r)
    baseline.value = b
    setEditFromBaseline(b)
})

const hasEdits = computed(() => {
    if (!baseline.value) return false

    if (edit.name !== baseline.value.name) return true
    if (edit.provider?.type !== baseline.value.providerType) return true

    const a = edit.params?.parameters || {}
    const b = baseline.value.params?.parameters || {}
    const keys = new Set([...Object.keys(a), ...Object.keys(b)])
    for (const k of keys) {
        if (JSON.stringify(a[k]?.value) !== JSON.stringify(b[k]?.value)) {
            return true
        }
    }
    return false
})

const editDisplayToken = computed({
    get: () => {
        const t = edit.params?.token;
        if (!t) return '';
        if (typeof t === 'string') { try { return JSON.stringify(JSON.parse(t), null, 2); } catch { return t; } }
        return JSON.stringify(t, null, 2);
    },
    set: (val: string) => {
        try { edit.params.token = JSON.parse(val); } catch { edit.params.token = val; }
    }
});

/** Common helpers */
function startCreate() {
    panel.value = 'create'
    query.value = ''             // clear filter when entering create
    selectedProvider.value = undefined
    remoteName.value = ''
    oAuthenticated.value = false
}

function selectProvider(p: CloudSyncProvider) {
    selectedProvider.value = p
}

const oauthBlurb = computed(() => selectedProvider.value?.providerParams.oAuthSupported
    ? 'Sign in to link your account. You can also expand Advanced to see parameters.'
    : 'This provider requires manual configuration. Expand Advanced to fill in parameters.'
)

function clearOAuth() {
    oAuthenticated.value = false
    providerValues.token = ''
}

const canCreate = computed(() =>
    !!remoteName.value.trim() && !!selectedProvider.value &&
    (!selectedProvider.value.providerParams.oAuthSupported || !!providerValues.token)
)

/** OAuth */
function oAuthBtn(p: CloudSyncProvider) {
    try {
        let suffix = ''
        if (p.type === 'dropbox') suffix = 'dropbox'
        else if (p.type === 'drive') suffix = 'drive'
        else if (p.type === 'google cloud storage') suffix = 'cloud'

        const url = `https://cloud-sync.45d.io/auth/${suffix}`
        const w = window.open(url, '_blank', 'width=500,height=900')
        if (!w) throw new Error('Popup blocked. Allow popups and try again.')

        const handler = async (evt: MessageEvent) => {
            if (evt.origin !== 'https://cloud-sync.45d.io') return
            const { accessToken, refreshToken, expiry, userId } = evt.data || {}
            if (accessToken && refreshToken && userId) {
                const token = { access_token: accessToken, refresh_token: refreshToken, expiry }
                providerValues.token = JSON.stringify(token)
                oAuthenticated.value = true
                pushNotification(new Notification('Authenticated', `Connected to ${p.name}`, 'success', 6000))
                window.removeEventListener('message', handler)
            } else {
                pushNotification(new Notification('Auth failed', 'Token data missing', 'error', 6000))
            }
        }
        window.addEventListener('message', handler)
    } catch (e: any) {
        pushNotification(new Notification('Authentication Error', e.message, 'error', 6000))
    }
}

/** Save new */
async function saveCreate() {
    if (!canCreate.value || !selectedProvider.value) return;
    creating.value = true;
    try {
        const flat = Object.fromEntries(Object.entries(providerValues)
            .filter(([_, v]) => v !== '' && v !== null && v !== undefined));

        const normalized = toAuth(flat, selectedProvider.value);

        // make token an object if it’s a JSON string
        const tv = normalized.parameters?.token?.value;
        if (typeof tv === 'string') { try { normalized.parameters.token.value = JSON.parse(tv); } catch { } }

        await myRemoteManager.createRemote(remoteName.value.trim(), selectedProvider.value.type, normalized);

        pushNotification(new Notification('Saved', 'Cloud account added', 'success', 6000));
        await myRemoteManager.getRemotes();
        query.value = '';
        panel.value = 'idle';
    } catch (e: any) {
        pushNotification(new Notification('Save Failed', e.message ?? 'Unknown error', 'error', 6000));
    } finally {
        creating.value = false;
    }
}


function resetCreate() {
    remoteName.value = ''
    selectedProvider.value = undefined
    Object.keys(providerValues).forEach(k => delete providerValues[k])
    oAuthenticated.value = false
    query.value = ''             // optional: also clear here
}

function openEdit(r: CloudSyncRemote) {
    // only set the ref; watcher will snapshot + populate
    selectedRemote.value = r
    console.log('editing:', selectedRemote.value)
    // enable edit mode immediately
    editMode.value = true
}

function cancelEdit() {
    if (!baseline.value) return
    setEditFromBaseline(baseline.value)  // restore original values
    editMode.value = false               // exit edit mode
}

async function saveEdit() {
    if (!selectedRemote.value || !hasEdits.value || saving.value) return
    try {
        saving.value = true

        const newName = (edit.name ?? '').trim()
        if (!newName) throw new Error('Account name is required.')

        // Narrow to a definite string (fallback to baseline or original)
        const providerType = edit.provider?.type ?? baseline.value?.providerType ?? selectedRemote.value!.type;


        if (!providerType) throw new Error('Provider type is required.')

        // UNFLATTEN back to CloudAuthParameter:
        const normalized = toAuth(edit.params, edit.provider!);

        // ensure token is an object if user pasted JSON
        const tv = normalized.parameters?.token?.value;
        if (typeof tv === 'string') { try { normalized.parameters.token.value = JSON.parse(tv); } catch { } }

        await myRemoteManager.editRemote(
            selectedRemote.value!.name,
            (edit.name ?? '').trim(),
            providerType,
            normalized // <-- has .parameters.<key>.value
        );

        await myRemoteManager.getRemotes()
        const updated = await myRemoteManager.getRemoteByName(newName)
        if (updated) {
            selectedRemote.value = updated
            baseline.value = snapshot(updated)
            setEditFromBaseline(baseline.value)
        }

        editMode.value = false
        pushNotification(new Notification('Updated', 'Changes saved', 'success', 6000))
    } catch (e: any) {
        pushNotification(new Notification('Save Failed', e.message ?? 'Unknown error', 'error', 6000))
    } finally {
        saving.value = false
    }
}

async function deleteRemote() {
    if (!selectedRemote.value) return
    const name = selectedRemote.value.name
    const ok = confirm(`Are you sure you want to delete "${name}"? This cannot be undone.`)
    if (!ok) return

    try {
        deleting.value = true
        await myRemoteManager.deleteRemote(name)
        pushNotification(new Notification('Deleted', `Removed ${name}`, 'success', 6000))
        selectedRemote.value = undefined
        panel.value = 'idle'
        await myRemoteManager.getRemotes()
    } catch (e: any) {
        pushNotification(new Notification('Delete Failed', e.message ?? 'Unknown error', 'error', 6000))
    } finally {
        deleting.value = false
    }
}
function setEditParam(key: string, val: any) {
    edit.params[key] = val;
}

function handleClose() {
    panel.value = 'idle'
    selectedRemote.value = undefined
    // emit('close')

    const ret = (route.query.returnTo as string) || '/simple/new'
    router.push(ret)
}
</script>
