<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                :fillColor="'fill-gray-500'" />
        </div>
    </div>

    <div v-else class="grid gap-2 my-2">
        <!-- Execution Mode (shown when multiple scripts) -->
        <div v-if="scriptEntries.length > 1" class="border border-default rounded-md p-2 bg-accent">
            <div class="flex items-center gap-2">
                <label class="block text-sm font-medium leading-6 text-default">Execution Mode</label>
                <InfoTile class="ml-1"
                    title="Sequential: scripts run one after another — if one fails, the rest are skipped. Parallel: all scripts start at the same time." />
            </div>
            <div class="flex items-center gap-4 mt-1">
                <label class="flex items-center gap-1.5 text-sm text-default cursor-pointer">
                    <input type="radio" v-model="executionMode" value="sequential"
                        class="w-4 h-4 text-success border-default focus:ring-green-500" />
                    Sequential
                </label>
                <label class="flex items-center gap-1.5 text-sm text-default cursor-pointer">
                    <input type="radio" v-model="executionMode" value="parallel"
                        class="w-4 h-4 text-success border-default focus:ring-green-500" />
                    Parallel
                </label>
            </div>
            <p v-if="executionMode === 'sequential'" class="text-xs text-muted mt-1">Scripts will run in order. If any script fails, the remaining scripts will be skipped.</p>
            <p v-else class="text-xs text-amber-600 dark:text-amber-400 mt-1">⚠ All scripts will run simultaneously. This may impact system performance if scripts are resource-intensive.</p>
        </div>

        <!-- Script entries -->
        <div v-for="(entry, idx) in scriptEntries" :key="idx"
            class="border border-default rounded-md p-2 bg-accent">
            <div class="flex flex-row justify-between items-center mb-1">
                <div class="flex items-center gap-1">
                    <label class="block text-sm font-medium leading-6 text-default">
                        Script {{ scriptEntries.length > 1 ? `#${idx + 1}` : '' }}
                    </label>
                    <InfoTile v-if="idx === 0" class="ml-1"
                        title="Enter a command, write a multi-line script, or point to an existing script file. Use the (+) button below to add additional scripts that will run in sequence or parallel." />
                </div>
                <div class="flex items-center gap-1">
                    <ExclamationCircleIcon v-if="entry.errorTag" class="w-5 h-5 text-danger" />
                    <button v-if="scriptEntries.length > 1" @click.stop="removeEntry(idx)" type="button"
                        class="text-danger hover:text-red-700 dark:hover:text-red-400 p-0.5" title="Remove this script">
                        <XMarkIcon class="w-5 h-5" />
                    </button>
                </div>
            </div>

            <!-- Script file path (optional) -->
            <div class="flex items-center gap-2">
                <div class="grow">
                    <PathAutoComplete v-model="entry.filePath" :error="entry.pathErrorTag"
                        placeholder="(optional) Path to existing script file" />
                </div>
                <button v-if="entry.filePath && !entry.loadingScript" @click.stop="loadScriptForEntry(idx)" type="button"
                    class="btn btn-secondary h-fit whitespace-nowrap text-xs">Load</button>
                <span v-if="entry.loadingScript" class="text-xs text-muted italic">Loading…</span>
            </div>
            <p v-if="entry.filePath && entry.scriptLoaded" class="text-xs text-success mt-0.5">Loaded from file.</p>
            <p v-if="entry.loadError" class="text-xs text-danger mt-0.5">{{ entry.loadError }}</p>

            <!-- Command / Script editor -->
            <textarea v-model="entry.content" rows="5" :class="[
                'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default font-mono',
                entry.errorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
            ]" placeholder="Enter command or script&#10;#!/bin/bash&#10;echo 'Hello'"></textarea>
        </div>

        <!-- Add script (+) button -->
        <button @click.stop="addEntry" type="button"
            class="btn btn-secondary h-fit w-full flex items-center justify-center gap-1.5">
            <PlusIcon class="w-4 h-4" />
            Add Script
        </button>
        <p class="text-xs text-muted -mt-1">
            {{ scriptEntries.length > 1
                ? `${scriptEntries.length} scripts configured — they will run in ${executionMode} order.`
                : 'Add additional scripts to run multiple operations in a single task.' }}
        </p>

        <!-- Clear all -->
        <div class="flex justify-end">
            <button @click.stop="clearAll" type="button" class="btn btn-danger h-fit">Clear All</button>
        </div>
    </div>
</template>

<script setup lang="ts">

import { ref, reactive, Ref, onMounted, inject } from 'vue';
import { ExclamationCircleIcon, XMarkIcon, PlusIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import PathAutoComplete from '../../common/PathAutoComplete.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, ZfsDatasetParameter, IntParameter, StringParameter, BoolParameter } from '../../../models/Parameters';
import { server, unwrap, File } from '@45drives/houston-common-lib';

interface ScriptEntry {
    filePath: string;
    content: string;
    externalPath: string;  // original external path if loaded from file
    scriptLoaded: boolean;
    loadingScript: boolean;
    loadError: string;
    errorTag: boolean;
    pathErrorTag: boolean;
}

function createEmptyEntry(): ScriptEntry {
    return {
        filePath: '',
        content: '',
        externalPath: '',
        scriptLoaded: false,
        loadingScript: false,
        loadError: '',
        errorTag: false,
        pathErrorTag: false,
    };
}

interface CustomTaskParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
}

const props = defineProps<CustomTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const errorList = inject<Ref<string[]>>('errors')!;

const scriptEntries = reactive<ScriptEntry[]>([createEmptyEntry()]);
const executionMode = ref<'sequential' | 'parallel'>('sequential');

const initialParameters = ref({});

const USER_SCRIPTS_DIR = '/opt/45drives/houston/scheduler/user_scripts/';

function addEntry() {
    scriptEntries.push(createEmptyEntry());
}

function removeEntry(idx: number) {
    if (scriptEntries.length > 1) {
        scriptEntries.splice(idx, 1);
    }
}

function clearAll() {
    scriptEntries.splice(0, scriptEntries.length, createEmptyEntry());
    executionMode.value = 'sequential';
}

async function readScriptFile(path: string): Promise<string> {
    const scriptFile = new File(server, path);
    const raw = await unwrap(scriptFile.read({ superuser: 'try' }));
    return String(raw ?? '');
}

async function loadScriptForEntry(idx: number) {
    const entry = scriptEntries[idx];
    if (!entry.filePath) return;
    entry.loadingScript = true;
    entry.loadError = '';
    entry.scriptLoaded = false;
    try {
        let content = await readScriptFile(entry.filePath);
        entry.content = content;
        entry.scriptLoaded = true;
        entry.externalPath = entry.filePath;
    } catch (e: any) {
        entry.loadError = `Could not read file: ${e?.message || e}`;
    } finally {
        entry.loadingScript = false;
    }
}

const initializeParameters = async () => {
    if (props.task) {
        loading.value = true;
        const params = props.task.parameters.children;

        const scriptsValue = params.find(param => param.key === 'scripts')?.value || '';
        const execModeValue = params.find(param => param.key === 'executionMode')?.value || 'sequential';
        const commandValue = params.find(param => param.key === 'command')?.value || '';
        const filePathValue = params.find(param => param.key === 'filePath')?.value || '';

        if (scriptsValue) {
            // Multi-script mode: parse the JSON array
            try {
                const scripts = JSON.parse(scriptsValue);
                executionMode.value = execModeValue as 'sequential' | 'parallel';
                scriptEntries.splice(0, scriptEntries.length);

                for (const s of scripts) {
                    const entry = createEmptyEntry();
                    if (s.filePath) {
                        entry.filePath = s.filePath;
                        try {
                            let content = await readScriptFile(s.filePath);
                            if (s.filePath.startsWith(USER_SCRIPTS_DIR) && content.startsWith('#!/bin/bash\n')) {
                                content = content.slice('#!/bin/bash\n'.length);
                            }
                            entry.content = content;
                            entry.scriptLoaded = true;
                            entry.externalPath = s.filePath.startsWith(USER_SCRIPTS_DIR) ? '' : s.filePath;
                        } catch {
                            entry.content = '';
                        }
                    } else if (s.command) {
                        entry.content = unwrapCommand(s.command);
                    }
                    scriptEntries.push(entry);
                }

                if (scriptEntries.length === 0) {
                    scriptEntries.push(createEmptyEntry());
                }
            } catch {
                scriptEntries.splice(0, scriptEntries.length, createEmptyEntry());
            }
        } else if (filePathValue) {
            // Legacy single-file mode
            const entry = scriptEntries[0];
            try {
                let content = await readScriptFile(filePathValue);
                if (filePathValue.startsWith(USER_SCRIPTS_DIR) && content.startsWith('#!/bin/bash\n')) {
                    content = content.slice('#!/bin/bash\n'.length);
                }
                entry.filePath = filePathValue;
                entry.content = content;
                entry.scriptLoaded = true;
                entry.externalPath = filePathValue.startsWith(USER_SCRIPTS_DIR) ? '' : filePathValue;
            } catch {
                entry.filePath = filePathValue;
                entry.content = '';
            }
        } else if (commandValue) {
            // Legacy inline command
            scriptEntries[0].content = unwrapCommand(commandValue);
        }

        initialParameters.value = serializeForComparison();
        loading.value = false;
    }
};

onMounted(initializeParameters);

function isValidFilePath(filePath: string): boolean {
    filePath = filePath.trim();
    if (!filePath) return false;
    if (/[:<>?*"|]/.test(filePath)) return false;
    if (/^[ ]|[ ]$/.test(filePath)) return false;
    if (filePath.includes('//')) return false;
    if (filePath === '/') return false;
    if (!filePath.endsWith('.py') && !filePath.endsWith('.sh') && !filePath.endsWith('.bash')) return false;
    return true;
}

function validateParams() {
    clearErrorTags();
    let hasErrors = false;

    for (let i = 0; i < scriptEntries.length; i++) {
        const entry = scriptEntries[i];
        const hasPath = entry.filePath.trim() !== '';
        const hasContent = entry.content.trim() !== '';

        if (hasPath && !hasContent) {
            if (!isValidFilePath(entry.filePath)) {
                entry.pathErrorTag = true;
                errorList.value.push(`Script #${i + 1}: Invalid file path. Must end with .py, .sh, or .bash.`);
                hasErrors = true;
            }
        } else if (!hasContent) {
            entry.errorTag = true;
            errorList.value.push(`Script #${i + 1}: A command or script is required.`);
            hasErrors = true;
        }
    }

    if (!hasErrors) {
        setParams();
    }
}

function unwrapCommand(wrappedCommand: string): string {
    if (wrappedCommand.includes('\n')) return wrappedCommand;
    const prefix = '/bin/bash -c "';
    if (!wrappedCommand.startsWith(prefix) || !wrappedCommand.endsWith('"')) return wrappedCommand;
    const commandPart = wrappedCommand.slice(prefix.length, -1);
    return commandPart
        .replace(/\\\\/g, '\\')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\`/g, '`');
}

function wrapCommandWithBash(userCommand: string): string {
    const escapedCommand = userCommand
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"')
        .replace(/`/g, '\\`');
    return `/bin/bash -c "${escapedCommand}"`;
}

function setParams() {
    if (scriptEntries.length === 1) {
        // Single script: use legacy format for backward compatibility
        const entry = scriptEntries[0];
        const content = entry.content.trim();
        const isMultiLine = content.includes('\n');
        const hasExternalPath = !!entry.externalPath && entry.filePath === entry.externalPath;
        const useFilePath = hasExternalPath && !isMultiLine;

        let command = '';
        if (!useFilePath) {
            command = isMultiLine ? content : wrapCommandWithBash(content);
        }

        const newParams = new ParameterNode("Custom Task Config", "customTaskConfig")
            .addChild(new BoolParameter("FilePath_flag", "filePath_flag", useFilePath))
            .addChild(new BoolParameter("Command_flag", "command_flag", !useFilePath))
            .addChild(new StringParameter('FilePath', 'filePath', useFilePath ? entry.filePath : ''))
            .addChild(new StringParameter('Command', 'command', command))
            .addChild(new StringParameter('Scripts', 'scripts', ''))
            .addChild(new StringParameter('Execution Mode', 'executionMode', 'sequential'));

        parameters.value = newParams;
    } else {
        // Multi-script: serialize as JSON array
        const scripts: any[] = [];
        for (const entry of scriptEntries) {
            const content = entry.content.trim();
            const hasExternalPath = !!entry.externalPath && entry.filePath === entry.externalPath;

            if (hasExternalPath && !content.includes('\n')) {
                scripts.push({ filePath: entry.filePath });
            } else {
                scripts.push({ command: content });
            }
        }

        const newParams = new ParameterNode("Custom Task Config", "customTaskConfig")
            .addChild(new BoolParameter("FilePath_flag", "filePath_flag", false))
            .addChild(new BoolParameter("Command_flag", "command_flag", false))
            .addChild(new StringParameter('FilePath', 'filePath', ''))
            .addChild(new StringParameter('Command', 'command', ''))
            .addChild(new StringParameter('Scripts', 'scripts', JSON.stringify(scripts)))
            .addChild(new StringParameter('Execution Mode', 'executionMode', executionMode.value));

        parameters.value = newParams;
    }
}

function clearErrorTags() {
    for (const entry of scriptEntries) {
        entry.errorTag = false;
        entry.pathErrorTag = false;
        entry.loadError = '';
    }
    errorList.value = [];
}

function serializeForComparison() {
    return JSON.stringify({
        entries: scriptEntries.map(e => ({ content: e.content, filePath: e.filePath })),
        executionMode: executionMode.value,
    });
}

function hasChanges() {
    return serializeForComparison() !== JSON.stringify(initialParameters.value);
}

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});
</script>