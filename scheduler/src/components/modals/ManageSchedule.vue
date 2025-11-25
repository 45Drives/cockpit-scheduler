<template>
    <Modal @close="closeModal" :isOpen="showScheduleWizard" :margin-top="'mt-6'" :width="'w-3/5'"
        :min-width="'min-w-3/5'" :height="'h-min'" :min-height="'min-h-min'" :close-on-background-click="false">
        <template v-slot:title>
            Manage Schedule
        </template>
        <template v-slot:content>
            <div name="new-schedule-interval" class="">
                <div class="grid grid-flow-cols grid-cols-2 my-2 gap-2 grid-rows-2">

                    <div @click="clearSelectedInterval()" name="schedule-input"
                        class="border border-default rounded-md p-2 col-span-2 row-span-1 col-start-1 row-start-1 bg-accent grid grid-cols-1">
                        <div name="schedule-preset" class="col-span-1">
                            <label for="schedule-preset-selection"
                                class="block text-sm font-medium leading-6 text-default">Interval Preset</label>
                            <select @click.stop id="task-template-selection" v-model="selectedPreset"
                                name="task-template-selection"
                                class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">
                                <option value="none">None</option>
                                <option value="minutely">Minutely</option>
                                <option value="hourly">Hourly</option>
                                <option value="daily">Daily</option>
                                <option value="weekly">Weekly</option>
                                <option value="monthly">Monthly</option>
                                <option value="yearly">Yearly</option>
                            </select>
                        </div>

                        <div name="schedule-fields" class="col-span-1 grid grid-cols-2 gap-2 mt-2">
                            <div name="hour">
                                <div class="flex flex-row justify-between items-center">
                                    <div class="flex flex-row justify-between items-center">
                                        <label class="block text-sm leading-6 text-default">Hour</label>
                                        <InfoTile class="ml-1"
                                            title="Use * for every value. Use A/N for repeats (e.g., 0/4 = every 4 hours starting at 00). Use commas for lists (e.g., 0,15,30). Use double periods for ranges (e.g., 8..17)." />
                                    </div>
                                    <ExclamationCircleIcon v-if="hourErrorTag" class="mt-1 w-5 h-5 text-danger" />
                                </div>
                                <input @click.stop v-model="newInterval.hour!.value" type="text" placeholder="(0-23)"
                                    :class="[
                                    'my-1 block w-full text-default input-textlike bg-default',
                                    hourErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                                    ]"
                                    title="Use * for every value. Use A/N for repeats (e.g., 0/4 = every 4 hours starting at 00). Use commas for lists (e.g., 0,15,30). Use double periods for ranges (e.g., 8..17)." />
                            </div>
                            <div name="minute">
                                <div class="flex flex-row justify-between items-center">
                                    <div class="flex flex-row justify-between items-center">
                                        <label class="block text-sm leading-6 text-default">Minute</label>
                                        <InfoTile class="ml-1"
                                            title="Use * for every value. Use A/N for repeats (e.g., 0/4 = every 4 hours starting at 00). Use commas for lists (e.g., 0,15,30). Use double periods for ranges (e.g., 8..17)." />
                                    </div>
                                    <ExclamationCircleIcon v-if="minuteErrorTag" class="mt-1 w-5 h-5 text-danger" />
                                </div>
                                <input @click.stop v-model="newInterval.minute!.value" type="text" placeholder="(0-59)"
                                    :class="[
                                    'my-1 block w-full text-default input-textlike bg-default',
                                    minuteErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                                    ]"
                                    title="Use * for every value. Use A/N for repeats (e.g., 0/4 = every 4 hours starting at 00). Use commas for lists (e.g., 0,15,30). Use double periods for ranges (e.g., 8..17)." />
                            </div>

                            <div name="date-data" class="col-span-2 grid grid-cols-3 gap-2">
                                <div name="day">
                                    <div class="flex flex-row justify-between items-center">
                                        <div class="flex flex-row justify-between items-center">
                                            <label class="block text-sm leading-6 text-default">Day</label>
                                            <InfoTile class="ml-1"
                                                title="Use * for Every Value, X/N for Every Nth Value starting on Day X, Commas to specify separate values, Two periods to specify a range of values (2..8)." />
                                        </div>
                                        <ExclamationCircleIcon v-if="dayErrorTag" class="mt-1 w-5 h-5 text-danger" />
                                    </div>
                                    <input @click.stop v-model="newInterval.day!.value" type="text" placeholder="(1-31)"
                                        :class="[
                                        'my-1 block w-full text-default input-textlike bg-default',
                                        dayErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                                        ]"
                                        title="Use asterisk (*) for all values, double-periods (..) for ranges (eg. 2..7), and commas for lists (eg. 2,4,7)" />
                                </div>
                                <div name="month">
                                    <div class="flex flex-row justify-between items-center">
                                        <div class="flex flex-row justify-between items-center">
                                            <label class="block text-sm leading-6 text-default">Month</label>
                                            <InfoTile class="ml-1"
                                                title="Use * for Every Value, Commas to specify separate values, Two periods to specify a range of values (2..8)." />
                                        </div>
                                        <ExclamationCircleIcon v-if="monthErrorTag" class="mt-1 w-5 h-5 text-danger" />
                                    </div>
                                    <input @click.stop v-model="newInterval.month!.value" type="text"
                                        placeholder="(1-12)" :class="[
                                        'my-1 block w-full text-default input-textlike bg-default',
                                        monthErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                                        ]"
                                        title="Use asterisk (*) for all values, double-periods (..) for ranges (eg. 2..7), and commas for lists (eg. 2,4,7)" />
                                </div>
                                <div name="year">
                                    <div class="flex flex-row justify-between items-center">
                                        <div class="flex flex-row justify-between items-center">
                                            <label class="block text-sm leading-6 text-default">Year</label>
                                            <InfoTile class="ml-1"
                                                title="Use * for Every Value, Commas to specify separate values, Two periods to specify a range of values (2..8)." />
                                        </div>
                                        <ExclamationCircleIcon v-if="yearErrorTag" class="mt-1 w-5 h-5 text-danger" />
                                    </div>
                                    <input @click.stop v-model="newInterval.year!.value" type="text"
                                        placeholder="(YYYY)" :class="[
                                        'my-1 block w-full text-default input-textlike bg-default',
                                        yearErrorTag ? 'outline outline-1 outline-rose-500 dark:outline-rose-700' : ''
                                        ]"
                                        title="Use asterisk (*) for all values, double-periods (..) for ranges (eg. 2..7), and commas for lists (eg. 2,4,7)" />
                                </div>
                            </div>

                            <div name="dayOfWeek" class="col-span-2">
                                <label class="block text-sm leading-6 text-default">Day of Week</label>
                                <table class="w-full">
                                    <tr class="grid grid-cols-7">
                                        <td v-for="day in daysOfWeek" class="px-0.5 col-span-1">
                                            <button @click.stop
                                                class="flex items-center w-full h-full border border-default rounded-lg bg-default"
                                                :class="daySelectedClass(day)">
                                                <label :for="`${day}`"
                                                    class="flex flex-col items-center whitespace-nowrap w-full p-1 px-1 text-sm gap-0.5 bg-default rounded-lg"
                                                    :class="daySelectedClass(day)">
                                                    <p class="w-full mt-0.5 text-sm text-default">{{ day }}</p>
                                                    <input @click.stop :id="`${day}`" v-model="newInterval.dayOfWeek"
                                                        type="checkbox" :value="`${day}`" :name="`${day}`"
                                                        class="mb-0.5 w-4 h-4 text-success bg-well border-default rounded focus:ring-green-500 dark:focus:ring-green-600 dark:ring-offset-gray-800 focus:ring-2" />
                                                </label>
                                            </button>
                                        </td>
                                    </tr>
                                </table>
                            </div>
                            <div name="buttons" class="col-span-2 button-group-row justify-between mt-2">
                                <button name="clearFields" @click.stop="clearFields()" class="btn btn-danger h-min">
                                    Clear Interval
                                </button>
                                <button v-if="selectedIndex !== undefined" name="updateInterval"
                                    @click.stop="saveInterval(newInterval)" class="btn btn-secondary h-min">
                                    Update Interval</button>
                                <button v-else name="saveInterval" @click.stop="saveInterval(newInterval)"
                                    class="btn btn-secondary h-min"
                                    :disabled="usingSnapshotRetention && localIntervals.length >= 1">
                                    Save Interval</button>
                            </div>
                        </div>
                    </div>

                    <div @click="clearSelectedInterval()" name="schedule-preview"
                        class="col-start-1 row-start-2 border border-default rounded-md p-2 col-span-1 bg-accent">
                        <label class="block text-sm font-medium leading-6 text-default">Interval Preview</label>
                        <div class="mt-1">
                            <CalendarComponent :key="calendarKey" :interval="newInterval!" />
                        </div>
                    </div>

                    <div name="schedule-interval-list" @click="clearSelectedInterval()"
                        class="col-start-2 row-start-2 border border-default rounded-md p-2 col-span-1 bg-accent">
                        <div @click="clearSelectedInterval()">
                            <div class="flex flex-row justify-between">
                                <label class="block text-sm font-medium leading-6 text-default whitespace-nowrap">
                                    Current Intervals</label>
                            </div>
                            <ul role="list" class="divide-y divide-default rounded-lg mt-2">
                                <li v-for="interval, idx in localIntervals" :key="idx" class="text-default rounded-lg"
                                    :class="intervalSelectedClass(idx)">
                                    <button class="h-full w-full rounded-lg p-2 px-2 text-left"
                                        @click.stop="selectionMethod(interval, idx)"
                                        :class="intervalSelectedClass(idx)">
                                        <div class="flex flex-col w-full grow">
                                            <span v-if="selectedIndex !== undefined && selectedIndex == idx"
                                                class="flex flex-row grow w-full justify-center text-center text-xs text-semibold italic text-default">
                                                EDITING INTERVAL:</span>
                                            <p>{{ myScheduler.parseIntervalIntoString(interval) }}</p>
                                        </div>
                                    </button>
                                </li>
                            </ul>
                            <div v-if="selectedInterval !== undefined" class="button-group-row justify-between mt-2">
                                <button name="remove-interval" @click.stop="removeSelectedInterval(selectedIndex)"
                                    class="btn btn-danger h-min w-full">Remove Interval</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </template>
        <template v-slot:footer>
            <div class="w-full">
                <div class="button-group-row w-full justify-between">
                    <div class="button-group-row">
                        <button @click.stop="closeBtn()" id="close-add-schedule-btn" name="close-add-schedule-btn"
                            class="btn btn-danger h-fit w-full">Close</button>
                    </div>
                    <!-- Delete Schedule -->
                    <button v-if="props.mode === 'edit'" type="button" class="btn btn-danger h-fit w-fit"
                        @click="deleteScheduleBtn()" :disabled="deletingSchedule">
                        <span v-if="deletingSchedule">Deleting…</span>
                        <span v-else>Delete Schedule</span>
                    </button>
                    <div class="button-group-row">
                        <button disabled v-if="savingSchedule && hasIntervals" id="adding-schedule-btn" type="button"
                            class="btn btn-primary h-fit w-full">
                            <svg aria-hidden="true" role="status"
                                class="inline w-4 h-4 mr-3 text-gray-200 animate-spin text-default"
                                viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path
                                    d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                                    fill="currentColor" />
                                <path
                                    d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                                    fill="text-success" />
                            </svg>
                            Saving Schedule...
                        </button>
                        <button disabled v-if="!savingSchedule && !hasIntervals" id="add-schedule-btn" type="button"
                            class="btn btn-primary h-fit w-full" @click="saveScheduleBtn()">Save Schedule</button>
                        <button v-if="!savingSchedule && hasIntervals" id="add-schedule-btn" type="button"
                            class="btn btn-primary h-fit w-full" @click="saveScheduleBtn()">Save Schedule</button>
                    </div>
                </div>
            </div>
        </template>
    </Modal>

    <div v-if="showSaveConfirmation">
        <component :is="confirmationComponent" @close="updateShowSaveConfirmation" :showFlag="showSaveConfirmation"
            :title="'Save Schedule'" :message="'Schedule this task?'" :confirmYes="confirmScheduleTask"
            :confirmNo="cancelScheduleTask" :operation="'saving'" :operating="savingSchedule" />
    </div>

    <div v-if="showCloseConfirmation">
        <component :is="closeConfirmationComponent" @close="updateShowCloseConfirmation"
            :showFlag="showCloseConfirmation" :title="props.mode == 'new' ? 'Cancel Add Task' : 'Cancel Edit Schedule'"
            :message="props.mode == 'new' ? 'Are you sure? This task configuration will be lost.' : 'Are you sure? Any changes will be lost.'"
            :confirmYes="confirmCancel" :confirmNo="cancelCancel" :operation="'canceling'"
            :operating="cancelingAddTask" />
    </div>

    <div v-if="showDeleteConfirmation">
        <component :is="deleteConfirmationComponent" @close="updateShowDeleteConfirmation"
            :showFlag="showDeleteConfirmation" :title="'Delete Schedule'"
            :message="'This will disable the timer and delete the schedule files. The task itself will remain and can still be run manually. Proceed?'"
            :confirmYes="confirmDeleteSchedule" :confirmNo="cancelDeleteSchedule" :operation="'deleting'"
            :operating="deletingSchedule" />
    </div>


</template>
<script setup lang="ts">
import { inject, reactive, ref, Ref, watch, onMounted, computed } from 'vue';
import Modal from '../common/Modal.vue';
import CalendarComponent from '../common/CalendarComponent.vue';
import InfoTile from '../common/InfoTile.vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';
import { TaskInstance } from '../../models/Tasks';
import { pushNotification, Notification } from '@45drives/houston-common-ui';
import { injectWithCheck } from '../../composables/utility'
import { loadingInjectionKey, schedulerInjectionKey } from '../../keys/injection-keys';

interface ManageScheduleProps {
    idKey: string;
    task: TaskInstance;
    mode: 'new' | 'edit';
}

const props = defineProps<ManageScheduleProps>();
const emit = defineEmits(['close']);

const myScheduler = injectWithCheck(schedulerInjectionKey, "scheduler not provided!");

const showScheduleWizard = inject<Ref<boolean>>('show-schedule-wizard')!;
const showTaskWizard = inject<Ref<boolean>>('show-task-wizard')!;

const loading = injectWithCheck(loadingInjectionKey, "loading not provided!");

const savingSchedule = ref(false);
const scheduleEnabled = ref(true);

const initialScheduleIntervals = ref({});

const closeModal = () => {
    showScheduleWizard.value = false;
    emit('close');
}

function hasScheduleChanges() {
    return JSON.stringify(localIntervals.value) !== JSON.stringify(initialScheduleIntervals.value);
}

const hasIntervals = computed(() => {
    return localIntervals.value.length > 0 ? true : false;
});

const usingSnapshotRetention = computed(() => {
    const taskTemplate = props.task.template.name;
    const isSnapshotTask = taskTemplate === 'Automated Snapshot Task';
    const isReplicationTask = taskTemplate === 'ZFS Replication Task';

    // Find the snapshotRetention parameter if it exists
    const snapshotRetention = props.task.parameters.children.find(
        (param) => param.key === 'snapshotRetention'
    );

    if (!snapshotRetention) {
        return false;
    }

    // Check for Automated Snapshot Task
    if (isSnapshotTask) {
        const hasRetentionTime = snapshotRetention.children.some(
            (child) => child.key === 'retentionTime' && child.value > 0
        );
        return hasRetentionTime;
    }

    // Check for ZFS Replication Task
    if (isReplicationTask) {
        const sourceRetentionTime = snapshotRetention.children.find(
            (child) => child.key === 'source'
        )?.children.some(
            (child) => child.key === 'retentionTime' && child.value > 0
        );

        const destinationRetentionTime = snapshotRetention.children.find(
            (child) => child.key === 'destination'
        )?.children.some(
            (child) => child.key === 'retentionTime' && child.value > 0
        );

        return sourceRetentionTime || destinationRetentionTime;
    }

    return false;
});


const cancelingAddTask = ref(false);
const showCloseConfirmation = ref(false);
const closeConfirmationComponent = ref();
async function loadCloseConfirmationComponent() {
    const module = await import('../common/ConfirmationDialog.vue');
    closeConfirmationComponent.value = module.default;    
}

async function closeBtn() {
    if (props.mode == 'edit') {
        if (hasScheduleChanges()) {
            await loadCloseConfirmationComponent();
            showCloseConfirmation.value = true;
        } else{
            closeModal();
        }
    } else {
        await loadCloseConfirmationComponent();
        showCloseConfirmation.value = true;
    }
   
}

const updateShowCloseConfirmation = (newVal) => {
    showCloseConfirmation.value = newVal;
}

const confirmCancel: ConfirmationCallback = async () => {
    closeModal();
}

const cancelCancel: ConfirmationCallback = async () => {
    updateShowCloseConfirmation(false);
}

const thisTask = ref(props.task);
const newSchedule = reactive<TaskScheduleType>({
    enabled: scheduleEnabled.value,
    intervals: [],
});

const selectedPreset = ref('none');
const localIntervals = ref<TaskScheduleIntervalType[]>([]);

const daysOfWeek : DayOfWeek[] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const newInterval = reactive<TaskScheduleIntervalType>({
    minute: { value: '0' },
    hour: { value: '0' },
    day: { value: '1' },
    month: { value: '*' },
    year: { value: '*' },
    dayOfWeek: []
});

function clearFields() {
    selectedPreset.value = 'none';
    Object.assign(newInterval, {
        minute: { value: '' },
        hour: { value: '' },
        day: { value: '' },
        month: { value: '' },
        year: { value: '' },
        dayOfWeek: []
    });
    forceUpdateCalendar();
    clearSelectedInterval();
}

function setFields(min, hr, d, mon, y, dow) {
    newInterval.hour!.value = hr;
    newInterval.minute!.value = min;
    newInterval.day!.value = d;
    newInterval.month!.value = mon;
    newInterval.year!.value = y;
    newInterval.dayOfWeek! = dow;
}

const errorList = ref<string[]>([]);
const hourErrorTag = ref(false);
const minuteErrorTag = ref(false);
const dayErrorTag = ref(false);
const monthErrorTag = ref(false);
const yearErrorTag = ref(false);

function clearAllErrors() {
    errorList.value = [];
    hourErrorTag.value = false;
    minuteErrorTag.value = false;
    dayErrorTag.value = false;
    monthErrorTag.value = false;
    yearErrorTag.value = false;
}

function normalizeField(raw: string, kind: 'min' | 'hour' | 'day' | 'month' | 'year'): string {
    let v = (raw ?? '').trim();
    if (v === '') return '*';

    // 1) Normalize cron-style "*/N" -> "0/N"
    v = v.replace(/^\*\/(\d+)$/g, '0/$1');

    // 2) Normalize hyphen ranges "a-b" -> "a..b" (systemd uses '..')
    v = v.replace('-', '..');

    // 3) Trim spaces around comma lists
    if (v.includes(',')) v = v.split(',').map(s => s.trim()).join(',');

    return v;
}

function inRange(n: number, min: number, max: number) {
    return Number.isInteger(n) && n >= min && n <= max;
}

function validateSystemdField(value: string, kind: 'min' | 'hour' | 'day' | 'month' | 'year'): boolean {
    const v = (value ?? '').trim();
    if (v === '') return false;
    if (v === '*') return true;

    // Accept comma-separated unions of valid atoms
    if (v.includes(',')) {
        return v.split(',').every(part => validateSystemdField(part, kind));
    }

    // Accept ranges "a..b" (not "a-b")
    const range = v.match(/^(\d+)\.\.(\d+)$/);
    if (range) {
        const a = Number(range[1]), b = Number(range[2]);
        if (a >= b) return false;
        switch (kind) {
            case 'min': return inRange(a, 0, 59) && inRange(b, 0, 59);
            case 'hour': return inRange(a, 0, 23) && inRange(b, 0, 23);
            case 'day': return inRange(a, 1, 31) && inRange(b, 1, 31);
            case 'month': return inRange(a, 1, 12) && inRange(b, 1, 12);
            case 'year': return inRange(a, 1970, 9999) && inRange(b, 1970, 9999);
        }
    }

    // Accept repetitions "A/N" (start/step), not "*/N"
    const rep = v.match(/^(\d+)\/(\d+)$/);
    if (rep) {
        const start = Number(rep[1]), step = Number(rep[2]);
        if (step <= 0) return false;
        switch (kind) {
            case 'min': return inRange(start, 0, 59);
            case 'hour': return inRange(start, 0, 23);
            case 'day': return inRange(start, 1, 31);
            // systemd allows repetition on month/year in many versions; be conservative and forbid it if you prefer:
            case 'month': return inRange(start, 1, 12);
            case 'year': return inRange(start, 1970, 9999);
        }
    }

    // Accept single integers
    if (/^\d+$/.test(v)) {
        const n = Number(v);
        switch (kind) {
            case 'min': return inRange(n, 0, 59);
            case 'hour': return inRange(n, 0, 23);
            case 'day': return inRange(n, 1, 31);
            case 'month': return inRange(n, 1, 12);
            case 'year': return inRange(n, 1970, 9999);
        }
    }

    return false;
}


const deletingSchedule = ref(false);
const showDeleteConfirmation = ref(false);
const deleteConfirmationComponent = ref();

async function loadDeleteConfirmationComponent() {
    const module = await import('../common/ConfirmationDialog.vue');
    deleteConfirmationComponent.value = module.default;
}

async function deleteScheduleBtn() {
    await loadDeleteConfirmationComponent();
    showDeleteConfirmation.value = true;
}

const updateShowDeleteConfirmation = (newVal: boolean) => {
    showDeleteConfirmation.value = newVal;
};

const confirmDeleteSchedule: ConfirmationCallback = async () => {
    try {
        deletingSchedule.value = true;

        const ok = await myScheduler.deleteSchedule(thisTask.value);
        if (ok) {
            pushNotification(new Notification(
                'Schedule Removed',
                `The schedule for "${thisTask.value.name}" has been removed.`,
                'success',
                6000
            ));
        } else {
            pushNotification(new Notification(
                'Delete Failed',
                `Failed to remove the schedule for "${thisTask.value.name}". Check logs for details.`,
                'error',
                6000
            ));
        }

        // Close modal and refresh list so the toggle/labels update everywhere
        updateShowDeleteConfirmation(false);
        showScheduleWizard.value = false;
        showTaskWizard.value = false;

        loading.value = true;
        await myScheduler.loadTaskInstances();
        loading.value = false;
    } finally {
        deletingSchedule.value = false;
    }
};

const cancelDeleteSchedule: ConfirmationCallback = async () => {
    updateShowDeleteConfirmation(false);
};


function validateFields(interval) {
    clearAllErrors();

    // Keep originals for nudges before we normalize
    const origHour = interval.hour.value ?? '';
    const origMinute = interval.minute.value ?? '';
    const origDay = interval.day.value ?? '';

    // Normalize in-place so the UI reflects corrections like "*/4" -> "0/4"
    interval.hour.value = normalizeField(interval.hour.value, 'hour');
    interval.minute.value = normalizeField(interval.minute.value, 'min');
    interval.day.value = normalizeField(interval.day.value, 'day');
    interval.month.value = normalizeField(interval.month.value, 'month');
    interval.year.value = normalizeField(interval.year.value, 'year');

    // Nudges for cron-style step syntax the user typed
    nudgeIfCronStep(origHour, 'hour');
    nudgeIfCronStep(origMinute, 'minute');
    nudgeIfCronStep(origDay, 'day');

    // Validate against systemd-only rules
    if (!validateSystemdField(interval.hour.value, 'hour')) { hourErrorTag.value = true; errorList.value.push('Hour must be *, A, A..B, or A/N (e.g., 0/4).'); }
    if (!validateSystemdField(interval.minute.value, 'min')) { minuteErrorTag.value = true; errorList.value.push('Minute must be *, A, A..B, or A/N (e.g., 0/15).'); }
    if (!validateSystemdField(interval.day.value, 'day')) { dayErrorTag.value = true; errorList.value.push('Day must be *, A, A..B, or A/N.'); }
    if (!validateSystemdField(interval.month.value, 'month')) { monthErrorTag.value = true; errorList.value.push('Month must be *, A, A..B, or list (1..12).'); }
    if (!validateSystemdField(interval.year.value, 'year')) { yearErrorTag.value = true; errorList.value.push('Year must be *, a year number, A..B, or list.'); }

    if (errorList.value.length > 0) {
        pushNotification(new Notification('Schedule Interval Save Failed', `Submission has errors:\n- ${errorList.value.join('\n- ')}`, 'error', 6000));
        return false;
    }
    return true;
}

const selectedInterval = ref<TaskScheduleIntervalType>();
const selectedIndex = ref<number>();
function selectionMethod(interval : TaskScheduleIntervalType, index: number) {
    selectedInterval.value = interval;
    // Object.assign(newInterval, JSON.parse(JSON.stringify(interval)));
    selectedIndex.value = index;
  //  console.log('selectedInterval (selectionMethod):', selectedInterval.value);
    // console.log('selected interval for editing:', interval);
  //  console.log('selectedIndex (selectionMethod):', selectedIndex.value);
    // clearFields();
    editSelectedInterval(selectedInterval.value);
}

function saveInterval(interval) {
    if (usingSnapshotRetention.value) {
        pushNotification(new Notification('Interval Limit Reached', 'Tasks using Snapshot Retention Policy can currently only have one scheduled interval.\nCreate multiple tasks to handle different retention policies.', 'warning', 6000));
    }

    if (validateFields(interval)) {
      //  console.log('selectedIndex in saveInterval:', selectedIndex.value);
        if (selectedIndex.value !== undefined) {
            // Deep clone the interval object to ensure no references are shared
            const updatedInterval = JSON.parse(JSON.stringify(interval));
            
            localIntervals.value[selectedIndex.value] = updatedInterval;
          //  console.log('updatedInterval saved (saveInterval):', updatedInterval);
        } else {
            const newInterval = JSON.parse(JSON.stringify(interval));
            localIntervals.value.push(newInterval);
          //  console.log('newInterval saved (saveInterval):', newInterval);
        }
       
      //  console.log('all intervals (saveInterval):', localIntervals.value);
        clearFields();
    } 
}

function clearSelectedInterval() {
    selectedInterval.value = undefined;
    selectedIndex.value = undefined;
    clearAllErrors();
}

function removeSelectedInterval(index) {
  //  console.log('interval to remove (removeSelectedInterval):', localIntervals.value[index])
    localIntervals.value.splice(index, 1);
  //  console.log('intervals after splice (removeSelectedInterval):', localIntervals.value);
    clearSelectedInterval();
}

function editSelectedInterval(interval : TaskScheduleIntervalType) {
    console.log('triggered editSelectedInterval', interval);

    const defaultTimeComponent = '0';

    // Set each field value, falling back to default if not present
    newInterval.hour!.value = interval.hour?.value ?? defaultTimeComponent;
    newInterval.minute!.value = interval.minute?.value ?? defaultTimeComponent;
    newInterval.day!.value = interval.day?.value ?? defaultTimeComponent;
    newInterval.month!.value = interval.month?.value ?? defaultTimeComponent;
    newInterval.year!.value = interval.year?.value ?? defaultTimeComponent;

    // Set selectedDays to the days from the interval or to an empty array if not present
    newInterval.dayOfWeek! = interval.dayOfWeek ?? [];
}

const showSaveConfirmation = ref(false);
const confirmationComponent = ref();
const loadConfirmationComponent = async () => {
    const module = await import('../common/ConfirmationDialog.vue');
    confirmationComponent.value = module.default;
}

async function showConfirmationDialog() {
    await loadConfirmationComponent();
    showSaveConfirmation.value = true;
    console.log('Showing confirmation dialog...');
}

const confirmScheduleTask: ConfirmationCallback = async () => {
    savingSchedule.value = true;
    try {
        // ensure we attach a plain schedule object to the task
        thisTask.value.schedule = JSON.parse(JSON.stringify(newSchedule));

        if (props.mode === 'new') {
            await myScheduler.registerTaskInstance(thisTask.value);
            pushNotification(new Notification('Task + Schedule Saved', 'Task and schedule have been saved.', 'success', 6000));
        } else {
            await myScheduler.updateSchedule(thisTask.value);
            pushNotification(new Notification('Schedule Saved', 'Schedule has been updated.', 'success', 6000));
        }

        updateShowSaveConfirmation(false);
        showScheduleWizard.value = false;
        showTaskWizard.value = false;

        loading.value = true;
        try { await myScheduler.loadTaskInstances(); } finally { loading.value = false; }

    } catch (e: any) {
        pushNotification(new Notification('Save Failed', String(e?.message || e), 'error', 6000));
    } finally {
        savingSchedule.value = false;
    }
};


const cancelScheduleTask : ConfirmationCallback = async () => {
    updateShowSaveConfirmation(false);
}

const updateShowSaveConfirmation = (newVal) => {
    showSaveConfirmation.value = newVal;
}

const intervals = ref<TaskScheduleIntervalType[]>([]);

async function saveScheduleBtn() {
    if (localIntervals.value.length < 1) {
        pushNotification(new Notification('Save Failed', `At least one interval is required.`, 'error', 6000));
    } else {

        // Normalize all intervals once more prior to save
        const cleaned = localIntervals.value.map(i => {
            const copy = JSON.parse(JSON.stringify(i)) as TaskScheduleIntervalType;
            copy.hour!.value = normalizeField(copy.hour!.value, 'hour');
            copy.minute!.value = normalizeField(copy.minute!.value, 'min');
            copy.day!.value = normalizeField(copy.day!.value, 'day');
            copy.month!.value = normalizeField(copy.month!.value, 'month');
            copy.year!.value = normalizeField(copy.year!.value, 'year');
            return copy;
        });

        newSchedule.intervals = [];                // clear first to avoid duplicates across edits
        newSchedule.intervals.push(...cleaned);
        thisTask.value.schedule = newSchedule;

        await showConfirmationDialog();
    }
}

function nudgeIfCronStep(raw: string, fieldLabel: string) {
    if (/^\*\/\d+$/.test((raw ?? '').trim())) {
        pushNotification(new Notification(
            'Adjusted Step Syntax',
            `Converted "${raw}" to systemd's "start/step" form for ${fieldLabel} (e.g., 0/4).`,
            'info',
            5000
        ));
    }
}


watch(selectedPreset, (newVal, oldVal) => {
    switch (selectedPreset.value) {
        case 'none':
            setFields('0', '0', '1', '*', '*', []);
            break;
        case 'minutely':
            setFields('*', '*', '*', '*', '*', []);
            break;
        case 'hourly':
            setFields('0', '*', '*', '*', '*', []);
            break;
        case 'daily':  
            setFields('0', '0', '*', '*', '*', []);
            break;
        case 'weekly':
            setFields('0', '0', '*', '*', '*', [daysOfWeek[0]]);
            break;
        case 'monthly':   
            setFields('0', '0', '1', '*', '*', []);
            break;
        case 'yearly':
            setFields('0', '0', '1', '1', '*', []);
            break;
        default:
            break;
    }
});

const daySelectedClass = (dayOfWeek) => {
    const isSelected = newInterval.dayOfWeek!.includes(dayOfWeek);
    return isSelected ? 'bg-green-30 dark:bg-green-700' : '';
}

const intervalSelectedClass = (intervalIdx) => {
    return selectedIndex.value == intervalIdx ? 'bg-green-30 dark:bg-green-700' : 'bg-default'
}

watch(newInterval, (newVal, oldVal) => {
  //  console.log('newInterval changed (watch):', newVal);
    forceUpdateCalendar();
}, { deep: true });

const calendarKey = ref(0);

function forceUpdateCalendar() {
    calendarKey.value++;
}

onMounted(() => {
    console.log('mode (onMounted):', props.mode);
    // clearFields();
    // clearAllErrors();
    
  //  console.log('task data (onMounted)', props.task);
    if (props.mode == 'new') {
        selectedInterval.value = undefined;
        selectedIndex.value = undefined;
        localIntervals.value = [];
    } else {
        localIntervals.value = [...props.task.schedule.intervals];
      //  console.log('localIntervals (onMounted)', localIntervals.value);
        initialScheduleIntervals.value = JSON.parse(JSON.stringify(localIntervals.value));
   }
});

</script>
