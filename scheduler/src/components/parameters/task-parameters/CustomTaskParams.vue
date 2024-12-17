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
        Provide a script file path
      </label>
      <label class="mt-1 block text-sm leading-6 text-default" >
        <input type="radio" value="command" v-model="inputType"/>
        Provide a command
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

const initialParameters = ref({});

const errorList = inject<Ref<string[]>>('errors')!;

function isValidFilePath(filePath) {
    console.log("File Path: ", filePath);

    // Check for empty path
    if (filePath === '') {
        return false;
    }

    // Check for invalid characters typically not allowed in file paths
    if (/[:<>?*"|]/.test(filePath)) {
        return false; // Invalid characters for file paths on most systems
    }

    // Check for path starting with a space or ending with a space
    if (/^[ ]|[ ]$/.test(filePath)) {
        return false; // Cannot start or end with a space
    }

    // Check for valid directory structure
    // Valid characters: alphanumeric, slashes, dots, underscores, and hyphens
    if (!/^([a-zA-Z0-9_.-]+([/\\][a-zA-Z0-9_.-]+)*)*$/.test(filePath)) {
        return false; // Invalid characters
    }

    // Check for consecutive slashes
    if (filePath.includes('//') || filePath.includes('\\\\')) {
        return false; 
    }

    // Additional check for root directory (not allowed in some cases)
    if (filePath === '/' || filePath === '\\') {
        return false;
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
function doesItExist(thisName: string, list: string[]) {
    if (list.includes(thisName)) {
        return true;
    } else {
        return false;
    }
}

function validateParams() {
    validateCustomTask();

    if (errorList.value.length == 0) {
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
            errorList.value.push("File path is invalid.");
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


function clearErrorTags() {
    scriptPathErrorTag.value = false;
    errorList.value = [];
}

function setParams() {
    const newParams = new ParameterNode("Custom Task Config", "customConfig")
    .addChild(new BoolParameter("FilePath","filePath",inputType.value === 'script'))
        .addChild(new BoolParameter("Command","command",inputType.value === 'command'))
        .addChild(new StringParameter('Path', 'path', scriptPath.value))
        .addChild(new StringParameter('Command', 'Command', oneLineCommand.value))

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