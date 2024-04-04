// Scheduler.ts

import { ParameterNode, SelectionParameter, SelectionOption, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter } from './Parameters';
import { TaskInstance, TaskTemplate, TaskSchedule, TaskScheduleInterval, ZFSReplicationTaskTemplate } from './Tasks';

export class Scheduler implements SchedulerType {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }
    
    // loadTaskTemplates() {
    //     // check /opt/45drives/houston/scheduler/templates/ for .service files
        
    // }
    
    loadTaskInstances() {
        // check /etc/systemd/system/ for .service files (that also have .env)
    }
    
    loadTaskLog() {
        // unknown
    }
    
    registerTaskInstance(TaskInstance) {
        //create script to generate env file with task parameters
        //run script to generate service + timer via env file and schedule passed as string



        //generate key/value pairs
        /* ParameterNode.asEnvKeyValues() {
                return children.map(c => c.asEnvKeyValues()) // recursively get child key=value pairs
                            .flat()
                            .map(kv => "${key}_${kv}"); // prefix key with parent key and _
            }
            StringParameter.asEnvKeyValues() {
                return [
                    "${key}=${value}", // this node's env key=value pair
                ];
            }
            IntParameter.asEnvKeyValues() {
                return [
                    "${key}=${value.toString()}", // this node's env key=value pair
                ];
            }
            BoolParameter.asEnvKeyValues() {
                return [
                    "${key}=${value ? 'true' : 'false'}", // this node's env key=value pair
                ];
            } 
            
            // e.g.
            conf = ParameterNode("ZFS Replication Config", "zfsRepConfig")
            .addChild(ZfsDatasetParameter("Source Dataset", "sourceDataset"))
            .addChild(ZfsDatasetParameter("Destination Dataset", "destDataset"))
            // etc ...
            .addChild(BoolParameter("Use Compression", "compression"));

            // after configuring...

            conf.asEnvKeyValuePairs() returns ->
            [
                "zfsRepConfig_sourceDataset_pool=tank",
                "zfsRepConfig_sourceDataset_dataset=dataset1",
                "zfsRepConfig_destDataset_host=192.168.4.20",
                "zfsRepConfig_destDataset_pool=tank",
                "zfsRepConfig_destDataset_dataset=dataset1",
                ...
                "zfsRepConfig_useCompression=true",
            ]
        */
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
