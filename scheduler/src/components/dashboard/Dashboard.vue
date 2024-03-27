<template>
	<div class="min-w-full max-w-full max-h-full py-2 align-middle sm:px-4 lg:px-6 sm:rounded-lg bg-well rounded-md border border-default">
		<div class="">
            <div class="my-4 flow-root">
                <div class="-mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
                    <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
                        <table class="table-auto min-w-full divide-y divide-default overflow-x-auto">
                            <thead class="bg-accent">
                                <tr class="border border-default grid grid-cols-5">
                                    <!-- Table Headers -> Name, Enabled/Scheduled, Status, LastRuntime, Details/Empty -->
                                    <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-default border border-default">
                                        <!-- <button class="flex w-full justify-between whitespace-nowrap"> -->
                                            Name
                                            <!-- <BarsArrowDownIcon class="ml-1 aspect-square w-5 h-5 text-muted" /> -->
                                            <!-- <BarsArrowUpIcon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                            <!-- <Bars3Icon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                        <!-- </button> -->
                                    </th>
                                    <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-default border border-default">
                                        <!-- <button class="flex w-full justify-between whitespace-nowrap"> -->
                                            Scheduled
                                            <!-- <BarsArrowDownIcon class="ml-1 aspect-square w-5 h-5 text-muted" /> -->
                                            <!-- <BarsArrowUpIcon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                            <!-- <Bars3Icon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                        <!-- </button> -->
                                    </th>
                                    <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-default border border-default">
                                        <!-- <button class="flex w-full justify-between whitespace-nowrap"> -->
                                            Status
                                            <!-- <BarsArrowDownIcon class="ml-1 aspect-square w-5 h-5 text-muted" /> -->
                                            <!-- <BarsArrowUpIcon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                            <!-- <Bars3Icon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                        <!-- </button> -->
                                    </th>
                                    <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-default border border-default">
                                        <!-- <button class="flex w-full justify-between whitespace-nowrap"> -->
                                            Last Run
                                            <!-- <BarsArrowDownIcon class="ml-1 aspect-square w-5 h-5 text-muted" /> -->
                                            <!-- <BarsArrowUpIcon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                            <!-- <Bars3Icon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                        <!-- </button> -->
                                    </th>
                                    <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-default border border-default">
                                        <!-- <button class="flex w-full justify-between whitespace-nowrap"> -->
                                            Details
                                            <!-- <BarsArrowDownIcon class="ml-1 aspect-square w-5 h-5 text-muted" /> -->
                                            <!-- <BarsArrowUpIcon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                            <!-- <Bars3Icon class="ml-1 aspect-square w-5 h-5 text-muted"/> -->
                                        <!-- </button> -->
                                    </th>
                                </tr>
                            </thead>
                            <tbody class="bg-default">
                                <tr class="border border-default" >
                                    <!-- Table Cells -> TaskName, Checkbox, Status, LastRunTimestamp, ChevronButton -->
                                    <!-- <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-default border border-default">
                                        {{ dummyTaskInstance.name }}
                                    </td>
                                    <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-default border border-default">
                                        <input type="checkbox" v-model="dummyTaskInstance.schedule.enabled"/>
                                    </td>
                                    <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-default border border-default">
                                        N/A
                                    </td>
                                    <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-default border border-default">
                                        &lt;timestamp here&gt;
                                    </td>
                                    <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-default border border-default">
                                        <ChevronUpIcon class="w-6 h-6"/>    
                                    </td> -->
                                    <div v-for="dummyTaskInstance, index in dummyTaskInstances" :key="dummyTaskInstance.parameters.key">
                                        <Disclosure v-slot="{open}" :defaultOpen="false">
                                            <DisclosureButton class="grid grid-cols-5 grid-flow-cols w-full text-center items-center rounded-sm">
                                                <div class="py-1 mt-1 col-span-1">
                                                    {{ dummyTaskInstance.name }}
                                                </div>
                                                <div class="py-1 mt-1 col-span-1">
                                                    <button class="flex min-w-fit w-full h-full">
                                                        <label class="">
                                                            <input type="checkbox" v-model="dummyTaskInstance.schedule.enabled"
                                                             class="w-4 h-4 text-success focus:ring-green-500 dark:focus:ring-green-600 dark:ring-offset-gray-800 focus:ring-2"/>
                                                        </label>
                                                    </button>
                                                </div>
                                                <div class="py-1 mt-1 col-span-1 font-semibold">
                                                    N/A
                                                </div>
                                                <div class="py-1 mt-1 col-span-1">
                                                    &lt;timestamp here&gt;
                                                </div>
                                                <div class="py-1 mt-1 mr-2 col-span-1 items-center">
                                                    <ChevronUpIcon 
                                                    class=" h-10 w-10 text-default transition-all duration-200 transform" :class="{ 'rotate-90': !open, 'rotate-180': open, }"/>    
                                                </div>
                                            </DisclosureButton>
                                            <DisclosurePanel>

                                            </DisclosurePanel>
                                        </Disclosure>
                                    </div>
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
</template>

<script setup lang="ts">
import {computed, Ref, inject, ref} from 'vue';
import { ArrowPathIcon, Bars3Icon, BarsArrowDownIcon, BarsArrowUpIcon, ChevronUpIcon } from '@heroicons/vue/24/outline';
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue';
import LoadingSpinner from '../common/LoadingSpinner.vue';

class name {
    constructor(parameters) {
        
    }
}

const dummyTaskTemplateList = ref<TaskTemplate[]>([
    {
        name: 'ZFS Replication Task',
        parameterSchema: {
            label: 'ZFS Replication Config',
            key: 'zfs_replication', // Unique key for the parameter schema
            children: [
                { label: 'Source', key: 'source', children: [
                    // {label: "Host", key: "host", value: }
                ]},
                { label: 'Destination', key: 'dest', children: []},
                { label: 'Compression', key: 'compression', children: []},
                // Add other parameters as needed
            ]
        }
    },
    // Add more TaskTemplates as necessary
]);


const dummyTaskInstances = ref<TaskInstance[]>([
    {
        name: 'ZFS Replication Task 1',
        template: dummyTaskTemplateList[0], // Reference to the ZFS Replication TaskTemplate
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



</script>