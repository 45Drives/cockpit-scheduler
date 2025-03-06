<template>
    <div v-if="loading" class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">
        <div
            class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-2 bg-accent flex items-center justify-center">
            <CustomLoadingSpinner :width="'w-20'" :height="'h-20'" :baseColor="'text-gray-200'"
                :fillColor="'fill-gray-500'" />
        </div>
    </div>
    <div v-else class="grid grid-cols-2 grid-rows-2 my-2 gap-2 h-full grid-template-rows-custom">
        <!-- TOP -->
        <div class="border border-default rounded-md p-2 col-span-2 row-start-1 row-span-1 bg-accent">
            <label class="mt-1 mb-2 block text-base leading-6 text-default">Available Disks</label>
            <div name="disk-identifier">
                <label :for="'disk-identifier'" class="mt-1 block text-sm leading-6 text-default">
                    Disk Identifier
                    <InfoTile class="ml-1" title="Select the method to identify disks:
- Block Device: Uses the system device name (e.g., /dev/sda).
- Hardware Path: Identifies disks by their physical location on the hardware.
- Device Alias: A user-friendly alias for the device which corrosponds to the slot number the drive is plugged into.
  (set by 45Drives Tools - dalias)" />
                </label>
                <select :id="'disk-identifier'" v-model="selectedIdentifier" name="disk-identifier"
                    class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                    <option value="sd_path">Block Device</option>
                    <option value="phy_path">Hardware Path</option>
                    <option value="vdev_path">Device Alias</option>
                </select>
            </div>

            <div name="disk-selection">
                <label :for="'disk-selection'" class="mt-1 block text-sm leading-6 text-default">
                    Select Disks
                    <InfoTile class="ml-1" title="Select the disk(s) to be tested." />
                </label>
                <ul :id="'disk-selection'" role="list" class="grid grid-cols-6 grid-rows-2 gap-2"
                    :class="[diskSelectionError ? 'outline outline-1 outline-rose-500 dark:outline-rose-700 rounded-md' : '']">
                    <li v-for="(disk, diskIdx) in diskList" :key="diskIdx" class="my-1">
                        <button class="flex min-w-fit w-full h-full border border-default rounded-lg py-1 px-2"
                            :class="diskCardClass(getDiskIDName(diskList, selectedIdentifier, disk.name).diskPath)">
                            <label :for="`disk-${diskIdx}`" class="flex flex-col w-full text-sm gap-0.5">
                                <input :id="`disk-${diskIdx}`" v-model="selectedDisks" type="checkbox"
                                    :value="`${getDiskIDName(diskList, selectedIdentifier, disk.name).diskPath}`"
                                    :name="`disk-${disk.name}`"
                                    class="w-4 h-4 text-success bg-well border-default rounded focus:ring-green-500 dark:focus:ring-green-600 dark:ring-offset-gray-800 focus:ring-2" />
                                <p class="truncate text-sm font-medium text-default"
                                    :title="getDiskIDName(diskList, selectedIdentifier, disk.name).diskName">{{
                                        truncateName(getDiskIDName(diskList, selectedIdentifier, disk.name).diskName, 8) }}
                                </p>
                                <p class="truncate text-sm text-default" :title="disk.type">{{ disk.type }}</p>
                                <p class="truncate text-sm text-default" :title="disk.capacity">{{ disk.capacity }}</p>
                            </label>
                        </button>
                    </li>
                </ul>
            </div>
        </div>

        <!-- BOTTOM -->
        <div name="test-options"
            class="border border-default rounded-md p-2 col-span-2 row-span-1 row-start-2 bg-accent">
            <label class="mt-1 block text-base leading-6 text-default">Test Options</label>
            <div class="col-span-1">
                <label :for="'test-type'" class="mt-1 block text-sm leading-6 text-default">
                    Test Type
                    <InfoTile class="ml-1"
                        title="Select the type of S.M.A.R.T. test to run on the disk.
- Immediate Offline Test: A quick test that updates S.M.A.R.T. attributes and logs errors without interrupting normal operations.
- Short Test: A brief test that checks the major components of the disk, typically taking a few minutes.
- Long Test: A comprehensive test that thoroughly examines the entire disk surface and internal components, usually taking several hours.
- Conveyance Test: Specific to ATA drives, this test checks for any damage that may have occurred during transport. It typically completes in a few minutes." />
                </label>
                <select :id="'test-type'" v-model="selectedTestType" name="test-type"
                    class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6"
                    :class="[testTypeSelectionError ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : '']">
                    <option value="">Select a Test</option>
                    <option value="offline">Immediate Offline Test</option>
                    <option value="short">Short Test</option>
                    <option value="long">Long Test</option>
                    <option value="conveyance">Conveyance Test</option>
                </select>
            </div>

        </div>
    </div>
</template>

<script setup lang="ts">

import { ref, Ref, onMounted, inject, watch } from 'vue';
import CustomLoadingSpinner from '../../common/CustomLoadingSpinner.vue';
import InfoTile from '../../common/InfoTile.vue';
import { ParameterNode, StringParameter } from '../../../models/Parameters';
import { getDisks, getDiskIDName, truncateName } from '../../../composables/utility'

interface SmartTestTaskParamsProps {
    parameterSchema: ParameterNodeType;
    task?: TaskInstanceType;
}

const props = defineProps<SmartTestTaskParamsProps>();
const loading = ref(false);
const parameters = inject<Ref<any>>('parameters')!;
const initialParameters = ref({});

const diskList = ref<DiskData[]>([]);
const selectedIdentifier = ref('vdev_path');

const selectedDisks = ref<string[]>([]);
const selectedTestType = ref('');

const diskSelectionError = ref(false);
const testTypeSelectionError = ref(false);

const errorList = inject<Ref<string[]>>('errors')!;

async function initializeData() {
    loading.value = true;

    await getDisks(diskList);
  //  console.log('disks:', diskList)

    if (props.task) {
        const params = props.task.parameters.children;
        const storedDisks = params.find(p => p.key === 'disks')!.value;

        // Parse the stored comma-separated disk paths into an array and trim the extra quotes
        selectedDisks.value = storedDisks
            ? storedDisks.split(', ').map(disk => disk.replace(/^'|'$/g, ''))
            : [];
      //  console.log('selectedDisks:', selectedDisks.value);

        selectedTestType.value = params.find(p => p.key === 'testType')!.value;

        initialParameters.value = JSON.parse(JSON.stringify({
            selectedDisks: selectedDisks.value,
            selectedTestType: selectedTestType.value
        }));
    }

    loading.value = false;
}

function hasChanges() {
    const currentParams = {
        selectedDisks: selectedDisks.value,
        selectedTestType: selectedTestType.value
    };

    return JSON.stringify(currentParams) !== JSON.stringify(initialParameters.value);
}

//change color of disk when selected
const diskCardClass = (diskPath) => {
    const isSelected = selectedDisks.value.includes(diskPath);
    return isSelected ? 'bg-green-300 dark:bg-green-700' : 'bg-default';
};

watch(selectedIdentifier, (newVal, oldVal) => {
    if (newVal) {
        selectedDisks.value = [];
    }
});

function validateDisks() {
    if (selectedDisks.value.length == 0) {
        errorList.value.push("At least one disk is required.");
        diskSelectionError.value = true;
        return false;
    } else {
        return true;
    }
}

function validateTestType() {
    if (selectedTestType.value.length == 0) {
        errorList.value.push("A test type is required.");
        testTypeSelectionError.value = true;
        return false;
    } else {
        return true;
    }
}


function clearErrorTags() {
    diskSelectionError.value = false;
    testTypeSelectionError.value = false;
    errorList.value = [];
}

async function validateParams() {
    // clearErrorTags();
    validateDisks();
    validateTestType();

    if (errorList.value.length == 0) {
        setParams();
    }
}

function setParams() {
  //  console.log('selectedDisks:', selectedDisks.value);
    const diskSelectionString = selectedDisks.value.join(', ');

    const newParams = new ParameterNode("SMART Test Config", "smartTestConfig")
        .addChild(new StringParameter('Disks', 'disks', `'${diskSelectionString}'`))
        .addChild(new StringParameter('Test Type', 'testType', selectedTestType.value));

    parameters.value = newParams;
  //  console.log('newParams:', newParams);
}

onMounted(async () => {
    await initializeData();
});

defineExpose({
    validateParams,
    clearErrorTags,
    hasChanges
});
</script>

<style scoped>
    .grid-template-rows-custom {
        grid-template-rows: auto auto 1fr;
    }

    .grid-row-span-1 {
        grid-row: 1 / span 1;
    }
</style>