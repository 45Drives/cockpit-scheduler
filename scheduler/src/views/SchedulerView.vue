<template>
	<div>
		<div class="w-full h-dvh min-h-dvh overflow-visible bg-default text-default">
			<div class="p-2">
				<div class="min-w-full max-w-full max-h-full py-2 align-middle sm:px-4 lg:px-6 sm:rounded-lg bg-well rounded-md border border-default">
                    <div class="">
                        <div class="flex flex-row justify-between sm:flex sm:items-center">
                            <div class="px-4 sm:px-0 sm:flex-auto">
                                <!-- <h2 class="block text-medium font-medium leading-6 text-default">Tasks</h2> -->
                                <p class="mt-2 text-medium text-default">List of all task instances. Click on Details button to view details.</p>
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
                                            <tr class="border border-default grid grid-cols-5 grid-flow-cols w-full text-center items-center rounded-sm py-1" v-for="dummyTaskInstance, index in dummyTaskInstances" :key="dummyTaskInstance.parameters.key">
                                                <!-- Table Cells -> TaskName, Checkbox, Status, LastRunTimestamp, ChevronButton -->
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    {{ dummyTaskInstance.name }}
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    <input type="checkbox" v-model="dummyTaskInstance.schedule.enabled"/>
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    N/A
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-r border-default">
                                                    &lt;timestamp here&gt;
                                                </td>
                                                <td class="whitespace-nowrap text-sm font-medium text-default border-default">
                                                    <!-- <ChevronRightIcon class="w-6 h-6"/>  -->
                                                    <button v-if="showDetails == true" @click="taskDetailsBtn()" class="btn btn-secondary">View Details</button>
                                                    <button v-if="showDetails == false" @click="taskDetailsBtn()" class="btn btn-secondary">Close Details</button>
                                                </td>
                                                <td v-if="showDetails == true" class="col-span-5 h-20">
                                                    Add Details Here
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
import {computed, Ref, inject, ref, provide} from 'vue';
import { ArrowPathIcon, Bars3Icon, BarsArrowDownIcon, BarsArrowUpIcon, ChevronRightIcon } from '@heroicons/vue/24/outline';
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue';
import LoadingSpinner from '../components/common/LoadingSpinner.vue';
import { Scheduler } from '../models/Scheduler';
import AddTask from "../components/wizard/AddTask.vue";
import { ZFSReplicationTaskTemplate } from "../models/Tasks";


const taskTemplates = inject<Ref<TaskTemplateType[]>>('task-templates')!;

// const dummyTaskTemplates = ref<TaskTemplateType[]>([
//     {
//         name: 'ZFS Replication Task',
//         parameterSchema: {
//             label: 'ZFS Replication Config',
//             key: 'zfs_replication', // Unique key for the parameter schema
//             children: [
//                 { label: 'Source', key: 'source', children: []},
//                 { label: 'Destination', key: 'dest', children: []},
//                 { label: 'Compression', key: 'compression', children: []},
//                 // Add other parameters as needed
//             ]
//         }
//     },

//     // Add more TaskTemplates as necessary
// ]);


const dummyTaskInstances = ref<TaskInstanceType[]>([
    {
        name: 'ZFS Replication Task 1',
        template: taskTemplates[0], // Reference to the ZFS Replication TaskTemplate
        parameters: {
            label: 'zfs rep task config',
            key: 'zfs_rep_task_1',
            children: []
        },
        schedule: {
            enabled: true,
            intervals: []
        }
    },
    // Add more TaskInstances as necessary
]);


const showWizard = ref(false);
const showDetails = ref(false);

function taskDetailsBtn() {
    showDetails.value = !showDetails.value;
}

provide('show-wizard', showWizard);
provide('task-instances', dummyTaskInstances);
// provide('task-templates', dummyTaskTemplates);
</script> 