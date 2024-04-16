<template>
	<div>
		<div class="w-full h-dvh min-h-dvh overflow-visible bg-default text-default">
			<div class="p-2">
				<div class="min-w-full max-w-full max-h-full py-2 align-middle sm:px-4 lg:px-6 sm:rounded-lg bg-well rounded-md border border-default">
                    <div class="">
                        <div class="flex flex-row justify-between sm:flex sm:items-center">
                            <div class="px-4 sm:px-0 sm:flex-auto">
                                <!-- <h2 class="block text-medium font-medium leading-6 text-default">Tasks</h2> -->
                                <p class="mt-2 text-medium text-default">List of all task instances. Click on View Details button to view details.</p>
                            </div>
                            <div class="flex flex-row justify-between">
                                <!-- <div class="px-3">
                                    <label class="block text-medium font-medium leading-6 text-default">Search Tasks</label>
                                    <input type="text" @keydown.enter="" v-model="searchItem" class="text-default bg-default block w-fit input-textlike sm:text-sm" placeholder="Search..." />
                                </div>
                                <div class="px-3">
                                    <label class="block text-medium font-medium leading-6 text-default">Filter</label>
                                    <select v-model="filterItem" class="text-default bg-defaultblock w-fit input-textlike sm:text-sm">
                                        <option value="no_filter">No Filter</option>
                                        <option value="filter_item">filter_item</option>
                                    </select>
                                </div> -->
                                <div class="mt-5 py-0.5 px-3">
                                    <!-- <router-link :to="'/forms/new'"> -->
                                        <button @click="showWizard = true" class="btn btn-primary">Add New Task</button>
                                    <!-- </router-link> -->
                                </div>
                            </div>
                        </div>
                        <div class="my-4 flow-root">
                            <div class="-mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
                                <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
                                    <table class="table-auto min-w-full divide-y divide-default overflow-x-auto">
                                        <thead class="bg-accent">
                                            <tr class="border border-default grid grid-cols-5">
                                                <!-- Table Headers -> Name, Enabled/Scheduled, Status, LastRuntime, Details/Empty -->
                                                <th scope="col" class="py-2 text-center text-sm font-semibold text-default border border-default">
                                                    Name
                                                </th>
                                                <th scope="col" class="py-2 text-center text-sm font-semibold text-default border border-default">
                                                    Scheduled
                                                </th>
                                                <th scope="col" class="py-2 text-center text-sm font-semibold text-default border border-default">
                                                    Status
                                                </th>
                                                <th scope="col" class="py-2 text-center text-sm font-semibold text-default border border-default">
                                                    Last Run
                                                </th>
                                                <th scope="col" class="py-2 text-center text-sm font-semibold text-default border border-default">
                                                    Details
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody class="bg-default">
                                            <tr class="border border-default grid grid-cols-5 grid-flow-cols w-full text-center items-center rounded-sm py-1" v-for="taskInstance, index in taskInstances" :key="index">
                                                <!-- Table Cells -> TaskName, Checkbox, Status, LastRunTimestamp, ChevronButton -->
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    {{ taskInstance.name }}
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    <input type="checkbox" v-model="taskInstance.schedule.enabled"/>
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    &lt;status here&gt;
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    &lt;timestamp here&gt;
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-default">
                                                    <!-- <ChevronRightIcon class="w-6 h-6"/>  -->
                                                    <!-- Need to account for multiple tasks in list, currently one button controls all task details -->
                                                    <button v-if="!showDetails[index]" @click="taskDetailsBtn(index)" class="btn btn-secondary">View Details</button>
                                                    <button v-if="showDetails[index]" @click="taskDetailsBtn(index)" class="btn btn-secondary">Close Details</button>
                                                </td>
                                                <td v-if="showDetails[index]" class="col-span-5 h-full border border-default p-2 m-2">
                                                    <!-- Details for ZFS Replication Task -->
                                                    <div v-if="taskInstance.template.name === 'ZFS Replication Task'" class="grid grid-cols-5 items-left text-left">
                                                        <div class="col-span-1">
                                                            <p class="my-2">
                                                                Task Type: <b>{{ taskInstance.template.name }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Send Type:
                                                                <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">Remote</b>
                                                                <b v-if="findValue(taskInstance.parameters, 'destDataset', 'host') === ''">Local</b> 
                                                            </p>
                                                           
                                                        </div>
                                                        <div class="col-span-1">
                                                            <p class="my-2">
                                                                Source: <b>{{ findValue(taskInstance.parameters, 'sourceDataset', 'pool') }}/{{ findValue(taskInstance.parameters, 'sourceDataset', 'dataset') }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Destination: <b>{{ findValue(taskInstance.parameters, 'destDataset', 'pool') }}/{{ findValue(taskInstance.parameters, 'destDataset', 'dataset') }}</b>
                                                            </p> 
                                                            <p class="my-2" v-if="findValue(taskInstance.parameters, 'destDataset', 'host') !== ''">
                                                                Remote SSH Host: <b>{{ findValue(taskInstance.parameters, 'destDataset', 'host') }}</b>
                                                                <br/>
                                                                Remote SSH Port: : <b>{{ findValue(taskInstance.parameters, 'destDataset', 'port') }}</b>
                                                            </p>
                                                        </div>
                                                        <div class="col-span-1">
                                                             <p class="my-2">
                                                                Recursive: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'recursive_flag')) }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Raw: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'raw_flag')) }}</b>
                                                            </p>
                                                            <p class="my-2">
                                                                Compressed: <b>{{ boolToYesNo(findValue(taskInstance.parameters, 'sendOptions', 'compressed_flag')) }}</b>
                                                            </p>
                                                        </div>
                                                       
                                                        <div class="col-span-2">
                                                            <p class="my-2">Schedules:</p>
                                                            <div v-for="interval, idx in taskInstance.schedule.intervals" :key="idx" class="flex flex-row col-span-2 border border-default border-collapse p-1">
                                                                <p class="mx-1" v-if="interval.day">Day: {{interval.day.value}}</p>
                                                                <p class="mx-1" v-if="interval.month">Month: {{interval.month.value}}</p>
                                                                <p class="mx-1" v-if="interval.year">Year: {{interval.year.value}}</p>
                                                                <p class="mx-1" v-if="interval.hour">Hour: {{interval.hour.value}}</p>
                                                                <p class="mx-1" v-if="interval.minute">Minute: {{interval.minute.value}}</p>
                                                                <p class="mx-1" v-if="interval.dayOfWeek">Day(s) of Week:{{interval.dayOfWeek.values}}</p>
                                                            </div>
                                                        </div>                                        
                                                    </div>
                                                    <div class="button-group-row justify-between col-span-5 mt-2 ">

                                                        <button class="flex flex-row min-h-fit flex-nowrap btn btn-primary">
                                                            Run Now
                                                            <PlayIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                        <button class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                            Edit
                                                            <PencilIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                        <button class="flex flex-row min-h-fit flex-nowrap btn btn-secondary">
                                                            Manage
                                                            <CalendarDaysIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                        <button class="flex flex-row min-h-fit flex-nowrap btn btn-danger">
                                                            Remove
                                                            <TrashIcon class="h-5 ml-2 mt-0.5"/>
                                                        </button>
                                                            
                                                    </div>
                                                </td>           
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                                <!-- <div v-if="!formsLoaded" class="flex items-center justify-center">
                                    <LoadingSpinner :width="'w-52'" :height="'h-52'" :baseColor="'text-gray-200'" :fillColor="'fill-gray-500'"/>
                                </div> -->
                            </div>
                        </div>
                    </div>
                </div>
			</div>
            <div v-if="showWizard">
                <AddTask :id-key="'add-task-modal'"/>
            </div>
		</div>
	</div>
</template>

<script setup lang="ts">
import "@45drives/cockpit-css/src/index.css";
import "@45drives/cockpit-vue-components/dist/style.css";
import {computed, Ref, inject, ref, provide, onMounted} from 'vue';
import { ArrowPathIcon, Bars3Icon, BarsArrowDownIcon, BarsArrowUpIcon, ChevronRightIcon, PlayIcon, PencilIcon, TrashIcon, CalendarDaysIcon } from '@heroicons/vue/24/outline';
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue';
import LoadingSpinner from '../components/common/LoadingSpinner.vue';
import { Scheduler, TaskInstance, ZFSReplicationTaskTemplate } from '../models/Classes';
import { boolToYesNo } from '../composables/helpers'
import AddTask from "../components/wizard/AddTask.vue";

// const taskTemplates = inject<Ref<TaskTemplateType[]>>('task-templates')!;
const taskInstances = inject<Ref<TaskInstanceType[]>>('task-instances')!;

const showWizard = ref(false);
// const showDetails = ref(false);
const showDetails = ref({});

function taskDetailsBtn(idx) {
    showDetails.value[idx] = !showDetails.value[idx];
}

function findValue(obj, targetKey, valueKey) {
    if (!obj || typeof obj !== 'object') return null;

    // Checking the current level
    if (obj.key === targetKey) {
        let foundChild = obj.children?.find(child => child.key === valueKey);
        return foundChild ? (foundChild.value !== undefined ? foundChild.value : 'Not found') : 'Not found';
    }

    // Recursively checking in children
    if (Array.isArray(obj.children)) {
        for (let child of obj.children) {
            const result = findValue(child, targetKey, valueKey);
            if (result !== null) {  // Ensure '0', 'false', or empty string are valid returns
                return result;
            }
        }
    }
    
    return null;  // Return null if nothing is found
}


function getTaskStatus() {

}

function getLastRunTimestamp() {

}



provide('show-wizard', showWizard);
</script> 