// Scheduler.ts

import { ParameterNode, SelectionParameter, SelectionOption, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter } from './Parameters';
import { TaskInstance, TaskTemplate } from './Tasks';

export class Scheduler {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }
    
    loadTaskTemplates() {
        // check /opt/45drives/houston/scheduler/templates/ for .service files
    }
    
    loadTaskInstances() {
        // check /etc/systemd/system/ for .service files (that also have .env)
    }
    
    loadTaskLog() {
        // unknown
    }
    
    registerTaskInstance(TaskInstance) {
        //create systemd, timer, env files here
    }
    
    unregisterTaskInstance(TaskInstance) {
        //delete task + associated files
    }
    
    updateTaskInstance(TaskInstance) {
        //populate data from env file and then delete + recreate task files
    }
    
    runTaskNow(TaskInstance) {
        // return TaskExecutionResult;
    }
    
    loadSchedulesFor(TaskInstance) {
        // return TaskSchedule[];
    }
    
    enableSchedule(TaskInstance) {
        
    }
    
    disableSchedule(TaskInstance) {
        
    }
    
    updateSchedule(TaskInstance) {
        
    }
}

export class TaskSchedule {
    enabled: boolean;
    intervals: TaskScheduleInterval[];

    constructor(enabled: boolean, intervals: TaskScheduleInterval[]) {
        this.enabled = enabled;
        this.intervals = intervals;
    }
}

export class TaskScheduleInterval {
    value: number;
    unit: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years';
    //need to account for DayOfWeek, DayOfMonth, steps, ranges, lists, etc.

    constructor(value: number, unit: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years') {
        this.value = value;
        this.unit = unit;
    }
    
}
