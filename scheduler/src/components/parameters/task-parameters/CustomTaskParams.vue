<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                :fillColor="'fill-gray-500'" />
        </div>
    </div>

    <div v-else  >
    <div class="grid grid-flow-cols grid-cols-2 my-2 gap-2"> 
      <label class="mt-1 block text-sm leading-6 text-default">
        <input  type="radio" value="script" v-model="inputType" />
        Script file path
      </label>
      <label class="mt-1 block text-sm leading-6 text-default" >
        <input type="radio" value="command" v-model="inputType"/>
        Custom command
      </label>
    </div>
    <div class="grid grid-flow-cols my-2 gap-2">
        <div v-if="inputType === 'script'">
        <div name="custom-data" class="border border-default rounded-md p-2 col-span-2 bg-accent">
            <div name="path">
                <div class="flex flex-row justify-between items-center">
                    <label class="mt-1 block text-sm leading-6 text-default">Path</label>
                    <!-- <input type="text" v-model="scriptPath" placeholder="Enter script file path" class="mt-1 mb-2 col-span-1 block text-base leading-6 text-default"/> -->
                    <ExclamationCircleIcon v-if="scriptPathErrorTag" class="mt-1 w-5 h-5 text-danger" />
                </div>
                <div>
                    <input type="text" v-model="scriptPath"
                        :class="['mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default',
                        scriptPathErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]"
                        placeholder="Specify Script File Path" 
                        @input="clearCommandIfPathInput"/>
                </div> 
            </div>
        </div>
    </div>
    <div v-if="inputType === 'command'" class="border border-default rounded-md p-2 col-span-2 bg-accent">
      <label for="oneLineCommand" class="mt-1 block text-sm leading-6 text-default">Command</label>
      <input v-model="oneLineCommand" @input="clearPathIfCommandInput" :class="['mt-1 block w-full text-default input-textlike sm:text-sm sm:leading-6 bg-default', 
             commandErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                        ]"placeholder="Enter your command"/>
      <p v-if="commandError" class="error">{{ commandError }}</p>
    </div>
</div>

    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, watch, inject } from 'vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import { ParameterNode, ZfsDatasetParameter, IntParameter, StringParameter, BoolParameter } from '../../../models/Parameters';

interface CustomTaskParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
}

const props = defineProps<CustomTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const scriptPath = ref(''); 
const scriptPathErrorTag = ref(false);
const inputType = ref('script'); // Default to script input
const commandError = ref('');
const oneLineCommand = ref('');
const commandErrorTag = ref(false);
const wrapCommand = ref('')

const initialParameters = ref({});

const errorList = inject<Ref<string[]>>('errors')!;


const initializeParameters = () => {
      if (props.task) {
        loading.value = true;
        const params = props.task.parameters.children;

        // Safely retrieve the command, path, and input type
        oneLineCommand.value = params.find(param => param.key === 'command')?.value || '';
        
        oneLineCommand.value = unwrapCommand(oneLineCommand.value);
        scriptPath.value = params.find(param => param.key === 'filePath')?.value || '';
        if (scriptPath.value !== '') { 
        inputType.value = 'script'; 
    } else if (oneLineCommand.value !== '') { 
        inputType.value = 'command'; 
    }
        // Store initial parameters
        initialParameters.value = {
          oneLineCommand: oneLineCommand.value,
        inputType: inputType.value,
          scriptPath: scriptPath.value,
        };
        
        loading.value = false;
      }
    };

    onMounted(initializeParameters);

    function isValidFilePath(filePath) {
    console.log("File Path: ", filePath);

    // Check for empty path
    if (filePath === '') {
        return false;
    }

    // Trim leading and trailing spaces
    filePath = filePath.trim();

    // Check for invalid characters typically not allowed in file paths
    // For Unix-like systems, ':', '?', '*', '"', and '|' are invalid.
    if (/[:<>?*"|]/.test(filePath)) {
        errorList.value.push("File path contains invalid characters.");

        return false; // Invalid characters for file paths on most systems
    }

    // Check for path starting or ending with a space
    if (/^[ ]|[ ]$/.test(filePath)) {
        errorList.value.push("File path cannot start or end with a space.");
        return false; // Cannot start or end with a space
    }
    const validPathPattern = /^((\/[a-zA-Z0-9_.-]+)+|\.[a-zA-Z0-9_.-]+)$/; 
    if (!validPathPattern.test(filePath)) {
        errorList.value.push("File path has an invalid structure.");
        return false; // Invalid characters or structure
    }

    // Check for consecutive slashes
    if (filePath.includes('//')) {
        errorList.value.push("File path cannot contain consecutive slashes.");
        return false; 
    }

    if (filePath === '/') {
        errorList.value.push("Root directory access is not allowed.");
        return false; 
    }

    // Check if the file ends with .py, .sh, or .bash
    if (!filePath.endsWith('.py') && !filePath.endsWith('.sh') && !filePath.endsWith('.bash')) {
        errorList.value.push("File path must end with .py, .sh, or .bash.");
        return false; // Must end with .py, .sh, or .bash
    }

    // If everything is valid
    return true; // Path is valid
}


const clearCommandIfPathInput = () => {
  if (scriptPath.value) {
    oneLineCommand.value = ''; // Clear the command input
  }
};

const clearPathIfCommandInput = () => {
  if (oneLineCommand.value) {
    scriptPath.value = ''; // Clear the script path input
  }
};


function validateParams() {
    validateCustomTask();

    if (errorList.value.length == 0) {
        if (oneLineCommand.value !== '') {
            // Append /bin/bash -c " to the command and remove any trailing quotes
            wrapCommand.value =  wrapCommandWithBash(oneLineCommand.value)
        }
        setParams();
    }
}


function validateCustomTask(){
    if(inputType.value === 'script' ){
        if (scriptPath.value === '') {
            errorList.value.push("Script File path is needed.");
            scriptPathErrorTag.value = true;
        }
    else{
        if(!isValidFilePath(scriptPath.value)){
            scriptPathErrorTag.value = true;
        }
    }
    }else if(inputType.value === 'command'){ 
        if (oneLineCommand.value === '') {
            errorList.value.push("Command is needed.");
            commandErrorTag.value = true;
        }
    }

}
function unwrapCommand(wrappedCommand) {
    // Check if the command starts with /bin/bash -c "
    const prefix = '/bin/bash -c "';
    if (!wrappedCommand.startsWith(prefix)) {
        return wrappedCommand; // Return as-is if it doesn't match
    }

    // Extract the command part
    const commandPart = wrappedCommand.slice(prefix.length, -1); // Remove the ending quote

    // Unescape the command
    const unescapedCommand = commandPart
        .replace(/\\'/g, "'")  // Unescape single quotes
        .replace(/\\"/g, '"')   // Unescape double quotes
        .replace(/\\`/g, '`')   // Unescape backticks
        .replace(/\\\\/g, '\\'); // Unescape backslashes

    return unescapedCommand;
}

function clearErrorTags() {
    scriptPathErrorTag.value = false;
    errorList.value = [];
}
function wrapCommandWithBash(userCommand) {
    // Escape backslashes, single quotes, double quotes, and backticks
    const escapedCommand = userCommand
        .replace(/\\/g, '\\\\') // Escape backslashes
        .replace(/'/g, "'\\''") // Escape single quotes
        .replace(/"/g, '\\"')    // Escape double quotes
        .replace(/`/g, '\\`');   // Escape backticks

    // Construct the final command
    const finalCommand = `/bin/bash -c "${escapedCommand}"`;

    return finalCommand;
}

function setParams() {
    const newParams = new ParameterNode("Custom Task Config", "customTaskConfig")
    .addChild(new BoolParameter("FilePath_flag","filePath_flag",inputType.value === 'script'))
        .addChild(new BoolParameter("Command_flag","command_flag",inputType.value === 'command'))
        .addChild(new StringParameter('FilePath', 'filePath', scriptPath.value))
        .addChild(new StringParameter('Command', 'command', wrapCommand.value))

    parameters.value = newParams;
    console.log('newParams:', newParams);
}

function hasChanges() {
    const currentParams = {
    };

    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}
defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});
</script>