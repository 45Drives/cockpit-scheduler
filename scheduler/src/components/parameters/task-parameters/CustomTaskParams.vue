<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                :fillColor="'fill-gray-500'" />
        </div>
    </div>

    <div v-else class="grid gap-2 my-2">
        <!-- Script path (optional) -->
        <div class="border border-default rounded-md p-2 bg-accent">
            <div class="flex flex-row justify-between items-center">
                <div class="flex items-center gap-1">
                    <label class="block text-sm font-medium leading-6 text-default">Script File Path</label>
                    <InfoTile class="ml-1"
                        title="Optional — point to an existing .sh, .bash, or .py script on the system. Its contents will load into the editor below. Leave empty to write a new command or script." />
                </div>
                <ExclamationCircleIcon v-if="scriptPathErrorTag" class="w-5 h-5 text-danger" />
            </div>
            <div class="flex items-center gap-2 mt-1">
                <div class="grow">
                    <PathAutoComplete v-model="scriptPath" :error="scriptPathErrorTag"
                        placeholder="(optional) Path to existing script file" />
                </div>
                <button v-if="scriptPath && !loadingScript" @click.stop="loadScriptFromPath" type="button"
                    class="btn btn-secondary h-fit whitespace-nowrap">Load</button>
                <span v-if="loadingScript" class="text-xs text-muted italic">Loading…</span>
            </div>
            <p v-if="scriptPath && scriptLoaded" class="text-xs text-success mt-1">Script loaded from file — edit below if needed.</p>
            <p v-if="loadScriptError" class="text-xs text-danger mt-1">{{ loadScriptError }}</p>
        </div>

        <!-- Command / Script editor (always visible) -->
        <div class="border border-default rounded-md p-2 bg-accent">
            <div class="flex flex-row justify-between items-center">
                <div class="flex items-center gap-1">
                    <label class="block text-sm font-medium leading-6 text-default">Command / Script</label>
                    <InfoTile class="ml-1"
                        title="Enter a single command or write a multi-line bash script. Multi-line scripts are saved as a script file and executed by the scheduler. Single-line commands are executed directly." />
                </div>
                <ExclamationCircleIcon v-if="commandErrorTag" class="w-5 h-5 text-danger" />
            </div>
            <textarea v-model="scriptContent" rows="8" :class="[
                'mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default font-mono',
                commandErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
            ]" placeholder="Enter command(s) — supports multiple lines&#10;#!/bin/bash&#10;echo 'Hello'&#10;date"></textarea>
            <p class="text-xs text-muted mt-1">Single-line commands are executed directly. Multi-line input is saved as a bash script.</p>
            <div class="flex justify-end mt-2">
                <button @click.stop="clearAll" type="button" class="btn btn-danger h-fit">Clear</button>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, inject } from 'vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import PathAutoComplete from '../../common/PathAutoComplete.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, ZfsDatasetParameter, IntParameter, StringParameter, BoolParameter } from '../../../models/Parameters';
import { server, unwrap, File } from '@45drives/houston-common-lib';

interface CustomTaskParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
}

const props = defineProps<CustomTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const errorList = inject<Ref<string[]>>('errors')!;

const scriptPath = ref('');
const scriptContent = ref('');
const scriptPathErrorTag = ref(false);
const commandErrorTag = ref(false);
const loadingScript = ref(false);
const scriptLoaded = ref(false);
const loadScriptError = ref('');
const wrapCommand = ref('');

// Track whether this task was originally using an external script path (not user_scripts)
const externalScriptPath = ref('');

const initialParameters = ref({});

const USER_SCRIPTS_DIR = '/opt/45drives/houston/scheduler/user_scripts/';

function clearAll() {
    scriptPath.value = '';
    scriptContent.value = '';
    externalScriptPath.value = '';
    scriptLoaded.value = false;
    loadScriptError.value = '';
    scriptPathErrorTag.value = false;
    commandErrorTag.value = false;
}

async function readScriptFile(path: string): Promise<string> {
    const scriptFile = new File(server, path);
    const raw = await unwrap(scriptFile.read({ superuser: 'try' }));
    return String(raw ?? '');
}

async function loadScriptFromPath() {
    if (!scriptPath.value) return;
    loadingScript.value = true;
    loadScriptError.value = '';
    scriptLoaded.value = false;
    try {
        let content = await readScriptFile(scriptPath.value);
        scriptContent.value = content;
        scriptLoaded.value = true;
        externalScriptPath.value = scriptPath.value;
    } catch (e: any) {
        loadScriptError.value = `Could not read file: ${e?.message || e}`;
        console.warn('Could not read script file:', e);
    } finally {
        loadingScript.value = false;
    }
}

const initializeParameters = async () => {
    if (props.task) {
        loading.value = true;
        const params = props.task.parameters.children;

        const commandValue = params.find(param => param.key === 'command')?.value || '';
        const filePathValue = params.find(param => param.key === 'filePath')?.value || '';

        if (filePathValue) {
            // Task has a file path — try to read and populate the editor
            try {
                let content = await readScriptFile(filePathValue);

                if (filePathValue.startsWith(USER_SCRIPTS_DIR)) {
                    // User script — strip shebang we added, show as editable content
                    if (content.startsWith('#!/bin/bash\n')) {
                        content = content.slice('#!/bin/bash\n'.length);
                    }
                    scriptContent.value = content;
                    scriptPath.value = filePathValue;
                    scriptLoaded.value = true;
                } else {
                    // External script — show path and load content
                    scriptPath.value = filePathValue;
                    scriptContent.value = content;
                    externalScriptPath.value = filePathValue;
                    scriptLoaded.value = true;
                }
            } catch (e) {
                // Can't read — just show the path
                console.warn('Could not read script file on edit:', e);
                scriptPath.value = filePathValue;
                scriptContent.value = '';
            }
        } else if (commandValue) {
            // Inline command — unwrap and show in editor
            scriptContent.value = unwrapCommand(commandValue);
            scriptPath.value = '';
        }

        initialParameters.value = {
            scriptContent: scriptContent.value,
            scriptPath: scriptPath.value,
        };

        loading.value = false;
    }
};

onMounted(initializeParameters);

function isValidFilePath(filePath: string): boolean {
    if (filePath === '') return false;
    filePath = filePath.trim();

    if (/[:<>?*"|]/.test(filePath)) {
        errorList.value.push("File path contains invalid characters.");
        return false;
    }
    if (/^[ ]|[ ]$/.test(filePath)) {
        errorList.value.push("File path cannot start or end with a space.");
        return false;
    }
    const validPathPattern = /^((\/[a-zA-Z0-9_.-]+)+|\.[a-zA-Z0-9_.-]+)$/;
    if (!validPathPattern.test(filePath)) {
        errorList.value.push("File path has an invalid structure.");
        return false;
    }
    if (filePath.includes('//')) {
        errorList.value.push("File path cannot contain consecutive slashes.");
        return false;
    }
    if (filePath === '/') {
        errorList.value.push("Root directory access is not allowed.");
        return false;
    }
    if (!filePath.endsWith('.py') && !filePath.endsWith('.sh') && !filePath.endsWith('.bash')) {
        errorList.value.push("File path must end with .py, .sh, or .bash.");
        return false;
    }
    return true;
}

function validateParams() {
    validateCustomTask();

    if (errorList.value.length === 0) {
        const content = scriptContent.value.trim();
        const isMultiLine = content.includes('\n');

        if (isMultiLine) {
            // Multi-line: store raw script, backend will write to user_scripts/
            wrapCommand.value = content;
        } else {
            // Single-line: wrap with bash -c
            wrapCommand.value = wrapCommandWithBash(content);
        }

        setParams();
    }
}

function validateCustomTask() {
    const hasPath = scriptPath.value.trim() !== '';
    const hasContent = scriptContent.value.trim() !== '';

    if (hasPath && !hasContent) {
        // Path provided but not loaded — validate the path
        if (!isValidFilePath(scriptPath.value)) {
            scriptPathErrorTag.value = true;
        }
    } else if (!hasContent) {
        errorList.value.push("A command or script is required.");
        commandErrorTag.value = true;
    }
}

function unwrapCommand(wrappedCommand: string): string {
    if (wrappedCommand.includes('\n')) {
        return wrappedCommand;
    }
    const prefix = '/bin/bash -c "';
    if (!wrappedCommand.startsWith(prefix) || !wrappedCommand.endsWith('"')) {
        return wrappedCommand;
    }
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
    const content = scriptContent.value.trim();
    const isMultiLine = content.includes('\n');
    const hasExternalPath = !!externalScriptPath.value && scriptPath.value === externalScriptPath.value;

    // If user loaded an external script and didn't modify, use the path directly
    const useFilePath = hasExternalPath && !isMultiLine;

    const newParams = new ParameterNode("Custom Task Config", "customTaskConfig")
        .addChild(new BoolParameter("FilePath_flag", "filePath_flag", useFilePath))
        .addChild(new BoolParameter("Command_flag", "command_flag", !useFilePath))
        .addChild(new StringParameter('FilePath', 'filePath', useFilePath ? scriptPath.value : ''))
        .addChild(new StringParameter('Command', 'command', wrapCommand.value));

    parameters.value = newParams;
}

function clearErrorTags() {
    scriptPathErrorTag.value = false;
    commandErrorTag.value = false;
    loadScriptError.value = '';
    errorList.value = [];
}

function hasChanges() {
    const currentParams = {
        scriptContent: scriptContent.value,
        scriptPath: scriptPath.value,
    };
    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});
</script>