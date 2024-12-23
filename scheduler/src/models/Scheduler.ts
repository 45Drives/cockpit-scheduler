import { ref } from 'vue';
import { BetterCockpitFile, errorString, useSpawn } from '@45drives/cockpit-helpers';
import { TaskInstance, TaskTemplate, TaskSchedule, ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskScheduleInterval, RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate, CustomTaskTemplate } from './Tasks';
import { ParameterNode, StringParameter, SelectionParameter, IntParameter, BoolParameter } from './Parameters';
import { createStandaloneTask, createTaskFiles, createScheduleForTask, removeTask, runTask, formatTemplateName } from '../composables/utility';
import { TaskExecutionLog, TaskExecutionResult } from './TaskLog';
// @ts-ignore
import get_tasks_script from '../scripts/get-task-instances.py?raw';;

export class Scheduler implements SchedulerType {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }

    async loadTaskInstances() {
        this.taskInstances.splice(0, this.taskInstances.length);
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_tasks_script], { superuser: 'try' });
            const tasksOutput = (await state.promise()).stdout;
            // console.log('Raw tasksOutput:', tasksOutput);
            const tasksData = JSON.parse(tasksOutput);
            tasksData.forEach(task => {
                const newTaskTemplate = ref();
                if (task.template == 'ZfsReplicationTask') {
                    newTaskTemplate.value = new ZFSReplicationTaskTemplate;
                } else if (task.template == 'AutomatedSnapshotTask') {
                    newTaskTemplate.value = new AutomatedSnapshotTaskTemplate;
                } else if (task.template == 'RsyncTask') {
                    newTaskTemplate.value = new RsyncTaskTemplate;
                } else if (task.template == 'ScrubTask') {
                    newTaskTemplate.value = new ScrubTaskTemplate;
                } else if (task.template == 'SmartTest') {
                    newTaskTemplate.value = new SmartTestTemplate;
                }
                else if (task.template == 'CustomTask') {
                    newTaskTemplate.value = new CustomTaskTemplate;
                }
                const parameters = task.parameters;
                const parameterNodeStructure = this.createParameterNodeFromSchema(newTaskTemplate.value.parameterSchema, parameters);
                const taskIntervals: TaskScheduleInterval[] = [];
                const notes = task.notes;

                task.schedule.intervals.forEach(interval => {
                    const thisInterval = new TaskScheduleInterval(interval);
                    taskIntervals.push(thisInterval);
                });
                const newSchedule = new TaskSchedule(task.schedule.enabled, taskIntervals);
                const newTaskInstance = new TaskInstance(task.name, newTaskTemplate.value, parameterNodeStructure, newSchedule,notes);
                this.taskInstances.push(newTaskInstance);
            });

            console.log('this.taskInstances:', this.taskInstances);

        } catch (state) {
            console.error(errorString(state));
            return null;
        }
    }

    // Main function to create a ParameterNode from JSON parameters based on a schema
    createParameterNodeFromSchema(schema: ParameterNode, parameters: any): ParameterNode {
        // Create a deep clone of the schema to fill in values without modifying the original schema
        function cloneSchema(node: ParameterNode): ParameterNode {
            let newNode: ParameterNode;
            // Check node type to instantiate correct parameter type
            if (node instanceof StringParameter) {
                newNode = new StringParameter(node.label, node.key);
            } else if (node instanceof IntParameter) {
                newNode = new IntParameter(node.label, node.key);
            } else if (node instanceof BoolParameter) {
                newNode = new BoolParameter(node.label, node.key);
            } else if (node instanceof SelectionParameter) {
                newNode = new SelectionParameter(node.label, node.key)
            } else {
                newNode = new ParameterNode(node.label, node.key);
            }

            node.children.forEach(child => {
                newNode.addChild(cloneSchema(child));
            });
            return newNode;
        }
        const parameterRoot = cloneSchema(schema);

        // Function to assign values from JSON to the corresponding ParameterNode
        function assignValues(node: ParameterNode, prefix = ''): void {
            const currentPrefix = prefix ? prefix + '_' : '';
            const fullKey = currentPrefix + node.key;
            // console.log(`Assigning value for key: ${fullKey}`);  
            if (parameters.hasOwnProperty(fullKey)) {
                let value = parameters[fullKey];
                if (node instanceof StringParameter || node instanceof SelectionParameter) {
                    node.value = value;
                } else if (node instanceof IntParameter) {
                    node.value = parseInt(value);
                } else if (node instanceof BoolParameter) {
                    node.value = value === 'true';
                }
            }
            node.children.forEach(child => assignValues(child, fullKey));
        }

        // Start the assignment from the root
        assignValues(parameterRoot);
        return parameterRoot;
    }

    parseEnvKeyValues(envKeyValues: string[], templateName: string) {
        let envObject = envKeyValues.reduce((acc, curr) => {
            const [key, value] = curr.split('=');
            acc[key] = value;
            return acc;
        }, {});

        console.log('templateName:', templateName);

        switch (templateName) {
            case 'ZfsReplicationTask':
                if (envObject['zfsRepConfig_sendOptions_raw_flag'] === 'true') {
                    envObject['zfsRepConfig_sendOptions_compressed_flag'] = '';
                } else if (envObject['zfsRepConfig_sendOptions_compressed_flag'] === 'true') {
                    envObject['zfsRepConfig_sendOptions_raw_flag'] = '';
                }
                break;

            case 'RsyncTask':
                if (!envObject['rsyncConfig_target_info_host']) {
                    envObject['rsyncConfig_target_info_host'] = '';
                    envObject['rsyncConfig_target_info_port'] = '';
                    envObject['rsyncConfig_target_info_user'] = '';
                }

                if (envObject['rsyncConfig_rsyncOptions_bandwidth_limit_kbps'] !== '0' && envObject['rsyncConfig_rsyncOptions_bandwidth_limit_kbps'] !== 0) {
                    envObject['rsyncConfig_rsyncOptions_bandwidth_limit_kbps'] = `${envObject['rsyncConfig_rsyncOptions_bandwidth_limit_kbps']}`;
                } else {
                    envObject['rsyncConfig_rsyncOptions_bandwidth_limit_kbps'] = '';
                }

                if (envObject['rsyncConfig_rsyncOptions_include_pattern'] && envObject['rsyncConfig_rsyncOptions_include_pattern'] !== "''") {
                    envObject['rsyncConfig_rsyncOptions_include_pattern'] = `${envObject['rsyncConfig_rsyncOptions_include_pattern']}`;
                } else {
                    envObject['rsyncConfig_rsyncOptions_include_pattern'] = '';
                }

                if (envObject['rsyncConfig_rsyncOptions_exclude_pattern'] && envObject['rsyncConfig_rsyncOptions_exclude_pattern'] !== "''") {
                    envObject['rsyncConfig_rsyncOptions_exclude_pattern'] = `${envObject['rsyncConfig_rsyncOptions_exclude_pattern']}`;
                } else {
                    envObject['rsyncConfig_rsyncOptions_exclude_pattern'] = '';
                }

                if (envObject['rsyncConfig_rsyncOptions_custom_args'] && envObject['rsyncConfig_rsyncOptions_custom_args'] !== "''") {
                    envObject['rsyncConfig_rsyncOptions_custom_args'] = `${envObject['rsyncConfig_rsyncOptions_custom_args']}`;
                } else {
                    envObject['rsyncConfig_rsyncOptions_custom_args'] = '';
                }
                break;

            default:
                break;
        }
        console.log('envObject After:', envObject);
        return envObject;
    }

    getScriptFromTemplateName(templateName: string) {
        switch (templateName) {
            case 'ZfsReplicationTask':
                return 'replication-script';
            case 'AutomatedSnapshotTask':
                return 'autosnap-script';
            case 'RsyncTask':
                return 'rsync-script';
            case 'SmartTest':
                return 'smart-test-script';
            default:
                console.error('no script provided');
                break;
        }
    }

    async registerTaskInstance(taskInstance: TaskInstance) {
        //generate env file with key/value pairs (Task Parameters)
        const envKeyValues = taskInstance.parameters.asEnvKeyValues();
        console.log('envKeyVals Before Parse:', envKeyValues);
        const templateName = formatTemplateName(taskInstance.template.name);
        let scriptPath = '';
        const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
        envObject['taskName'] = taskInstance.name;

        if(templateName=="CustomTask"){
            const children = taskInstance.parameters?.children;
            const pathParam = children?.find((child: any) => child.key === 'path');
            scriptPath = pathParam?.value || '/opt/45drives/houston/scheduler/scripts/undefined.py';

        }else{
            const scriptFileName = this.getScriptFromTemplateName(templateName);
            scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;
        }


        // Remove empty values from envObject
        const filteredEnvObject = Object.fromEntries(Object.entries(envObject).filter(([key, value]) => value !== '' && value !== 0));

        console.log('Filtered envObject:', filteredEnvObject);

        // Convert the parsed envObject back to envKeyValuesString
        const envKeyValuesString = Object.entries(filteredEnvObject).map(([key, value]) => `${key}=${value}`).join('\n');
        const templateTimerPath = `/opt/45drives/houston/scheduler/templates/Schedule.timer`;

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const envFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.env`;

        console.log('envFilePath:', envFilePath);

        const file = new BetterCockpitFile(envFilePath, {
            superuser: 'try',
        });

        file.replace(envKeyValuesString).then(() => {
            console.log('env file created and content written successfully');
            file.close();

        }).catch(error => {
            console.error("Error writing content to the file:", error);
            file.close();
        });

        const jsonFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.json`;
        console.log('jsonFilePath:', jsonFilePath);

        //run script to generate notes file
        console.log("genrating notes file");
        const notesFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.txt`;
        //const notes = taskInstance.notes
        const notes = taskInstance.notes
        const file3 = new BetterCockpitFile(notesFilePath, {
            superUser: 'try',
        }) 
        file3.replace(notes).then(() => {
            console.log('Notes file created and content written successfully');
            file3.close();

        }).catch(error => {
            console.error("Error writing content to the notes file:", error);
            file3.close();
        });


        //run script to generate service + timer via template, param env and schedule json
        if (taskInstance.schedule.intervals.length < 1) {
            //ignore schedule for now
            console.log('No schedules found, parameter file generated.');

            await createStandaloneTask(templateName, scriptPath, envFilePath);

        } else {
            //generate json file with enabled boolean + intervals (Schedule Intervals)
            // requires schedule data object
            console.log('schedule:', taskInstance.schedule);

            const file2 = new BetterCockpitFile(jsonFilePath, {
                superuser: 'try',
            });

            const jsonString = JSON.stringify(taskInstance.schedule, null, 2);

            file2.replace(jsonString).then(() => {
                console.log('json file created and content written successfully');
                file2.close();
            }).catch(error => {
                console.error("Error writing content to the file:", error);
                file2.close();
            });

            await createTaskFiles(templateName, scriptPath, envFilePath, templateTimerPath, jsonFilePath);
        }
    }

    async updateTaskInstance(taskInstance) {
        //populate data from env file and then delete + recreate task files
        const envKeyValues = taskInstance.parameters.asEnvKeyValues();
        console.log('envKeyVals:', envKeyValues);
        const templateName = formatTemplateName(taskInstance.template.name);

        const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
        envObject['taskName'] = taskInstance.name;

        const scriptFileName = this.getScriptFromTemplateName(templateName);
        const scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;

        // Remove empty values from envObject
        const filteredEnvObject = Object.fromEntries(Object.entries(envObject).filter(([key, value]) => value !== '' && value !== 0));

        console.log('Filtered envObject:', filteredEnvObject);

        // Convert the parsed envObject back to envKeyValuesString
        const envKeyValuesString = Object.entries(filteredEnvObject).map(([key, value]) => `${key}=${value}`).join('\n');

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const envFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.env`;

        console.log('envFilePath:', envFilePath);

        const file = new BetterCockpitFile(envFilePath, {
            superuser: 'try',
        });

        file.replace(envKeyValuesString).then(() => {
            console.log('env file updated successfully');
            file.close();
        }).catch(error => {
            console.error("Error updating file:", error);
            file.close();
        });

        await createStandaloneTask(templateName, scriptPath, envFilePath);

        // Reload the system daemon
        let command = ['sudo', 'systemctl', 'daemon-reload'];
        let state = useSpawn(command, { superuser: 'try' });
        await state.promise();
    }

    async updateTaskNotes(taskInstance) {
        //populate data from env file and then delete + recreate task files
   
        const templateName = formatTemplateName(taskInstance.template.name);

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const notesFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.txt`;

        console.log('notesFilePath:', notesFilePath);

        const file = new BetterCockpitFile(notesFilePath, {
            superuser: 'try',
        });

        file.replace(taskInstance.notes).then(() => {
            console.log('notes file updated successfully');
            file.close();
        }).catch(error => {
            console.error("Error updating file:", error);
            file.close();
        });

        // Reload the system daemon
        let command = ['sudo', 'systemctl', 'daemon-reload'];
        let state = useSpawn(command, { superuser: 'try' });
        await state.promise();
    }

    async unregisterTaskInstance(taskInstance: TaskInstanceType) {
        //delete task + associated files
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        await removeTask(fullTaskName);

        console.log(`${fullTaskName} removed`);
        // await this.loadTaskInstances();
    }

    async runTaskNow(taskInstance: TaskInstanceType) {
        //execute service file now
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        console.log(`Running ${fullTaskName}...`);
        await runTask(fullTaskName);
        console.log(`Task ${fullTaskName} completed.`);
        // return TaskExecutionResult;
    }

    async getTimerStatus(taskInstance: TaskInstanceType) {
        const taskLog = new TaskExecutionLog([]);
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = houstonSchedulerPrefix + templateName + '_' + taskInstance.name;

        try {
            const command = ['systemctl', 'status', `${fullTaskName}.timer`, '--no-pager', '--output=cat'];
            const state = useSpawn(command, { superuser: 'try' });
            const result = await state.promise();
            const output = result.stdout;

            return this.parseTaskStatus(output, fullTaskName, taskLog, taskInstance);
        } catch (error) {
            console.error(`Error checking timer status:`, error);
            return 'Error checking timer status';
        }
    }

    async getServiceStatus(taskInstance: TaskInstanceType) {
        const taskLog = new TaskExecutionLog([]);
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = houstonSchedulerPrefix + templateName + '_' + taskInstance.name;

        try {
            const command = ['systemctl', 'status', `${fullTaskName}.service`, '--no-pager', '--output=cat'];
            const state = useSpawn(command, { superuser: 'try' });
            const result = await state.promise();
            const output = result.stdout;

            // Return the parsed status based on stdout
            return this.parseTaskStatus(output, fullTaskName, taskLog, taskInstance);
        } catch (error: any) {
            // Only log real errors, not status-related cases
            // console.error(`Error checking service status:`, error);
            return this.parseTaskStatus(error.stdout || '', fullTaskName, taskLog, taskInstance); // Use error.stdout if available
        }
    }


    async parseTaskStatus(output: string, fullTaskName: string, taskLog: TaskExecutionLog, taskInstance: TaskInstanceType) {
        try {
            let status = '';
            const activeStatusRegex = /^\s*Active:\s*(\w+\s*\([^)]*\))/m;
            const activeStatusMatch = output.match(activeStatusRegex);
            const succeededRegex = new RegExp(`${fullTaskName}.service: Succeeded`, 'm');

            if (activeStatusMatch) {
                const systemdState = activeStatusMatch[1].trim();

                // Match the systemctl state to internal task states
                switch (systemdState) {
                    case 'activating (start)':
                        status = 'Starting...';
                        break;
                    case 'active (waiting)':
                        status = 'Active (Pending)';
                        break;
                    case 'active (running)':
                        status = 'Active (Running)';
                        break;
                    case 'inactive (dead)':
                        // Check if the task has succeeded
                        if (succeededRegex.test(output)) {
                            status = 'Completed';
                        } else {
                            const recentlyCompleted = await taskLog.wasTaskRecentlyCompleted(taskInstance);
                            status = recentlyCompleted ? 'Completed' : 'Inactive (Disabled)';
                        }
                        break;
                    case 'failed (result)':
                        status = 'Failed';
                        break;
                    default:
                        status = systemdState;  // Fallback to systemctl state if nothing matches
                }
            } else {
                // No valid status found
                status = "Unit inactive or not found.";
            }

            // console.log(`Status for ${fullTaskName}`, status);
            return status;
        } catch (error) {
            console.error(`Error parsing status for ${fullTaskName}:`, error);
            return false;
        }
    }

    async enableSchedule(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        const timerName = `${fullTaskName}.timer`;
        try {
            // Reload the system daemon
            let command = ['sudo', 'systemctl', 'daemon-reload'];
            let state = useSpawn(command, { superuser: 'try' });
            await state.promise();

            // Start and Enable the timer
            command = ['sudo', 'systemctl', 'enable', timerName];
            state = useSpawn(command, { superuser: 'try' });
            await state.promise();

            console.log(`${timerName} has been enabled and started`);
            taskInstance.schedule.enabled = true;
            console.log('taskInstance after enable:', taskInstance);
            await this.updateSchedule(taskInstance);
        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }

    async disableSchedule(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        const timerName = `${fullTaskName}.timer`;
        try {
            // Reload systemd daemon
            let reloadCommand = ['sudo', 'systemctl', 'daemon-reload'];
            let reloadState = useSpawn(reloadCommand, { superuser: 'try' });
            await reloadState.promise();

            // Stop and Disable the timer
            let stopCommand = ['sudo', 'systemctl', 'stop', timerName];
            let stopState = useSpawn(stopCommand, { superuser: 'try' });
            await stopState.promise();

            let disableCommand = ['sudo', 'systemctl', 'disable', timerName];
            let disableState = useSpawn(disableCommand, { superuser: 'try' });
            await disableState.promise();

            console.log(`${timerName} has been stopped and disabled`);
            taskInstance.schedule.enabled = false;
            console.log('taskInstance after disable:', taskInstance);

            await this.updateSchedule(taskInstance);

        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }

    async updateSchedule(taskInstance) {
        const templateName = formatTemplateName(taskInstance.template.name);

        const templateTimerPath = `/opt/45drives/houston/scheduler/templates/Schedule.timer`;

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;
        const jsonFilePath = `/etc/systemd/system/${fullTaskName}.json`;
        console.log('jsonFilePath:', jsonFilePath);

        const file = new BetterCockpitFile(jsonFilePath, {
            superuser: 'try',
        });

        const jsonString = JSON.stringify(taskInstance.schedule, null, 2);

        file.replace(jsonString).then(() => {
            console.log('json file created and content written successfully');
            file.close();
        }).catch(error => {
            console.error("Error writing content to the file:", error);
            file.close();
        });

        if (taskInstance.schedule.enabled) {
            await createScheduleForTask(fullTaskName, templateTimerPath, jsonFilePath);

            // Reload the system daemon
            let command = ['sudo', 'systemctl', 'daemon-reload'];
            let state = useSpawn(command, { superuser: 'try' });
            await state.promise();

            command = ['sudo', 'systemctl', 'restart', fullTaskName + '.timer'];
            state = useSpawn(command, { superuser: 'try' });
            await state.promise();
        }
    }

    parseIntervalIntoString(interval) {
        const elements: string[] = [];

        function getMonthName(number) {
            const months = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'];
            return months[number - 1] || 'undefined';
        }

        function getDaySuffix(day) {
            if (day > 3 && day < 21) return 'th';
            switch (day % 10) {
                case 1: return 'st';
                case 2: return 'nd';
                case 3: return 'rd';
                default: return 'th';
            }
        }

        function formatUnit(value, type) {
            if (value === '*') {
                return type === 'minute' ? 'every minute' :
                    type === 'hour' ? 'every hour' : `every ${type}`;
            } else if (value.startsWith('*/')) {
                const interval = value.slice(2);
                return `every ${interval} ${type}${interval > 1 ? 's' : ''}`;
            } else if (value.includes('/')) {
                const [base, step] = value.split('/');
                if (type === 'day') {
                    return `every ${step} days starting on the ${base}${getDaySuffix(parseInt(base))}`;
                }
                return `every ${step} ${type}${step > 1 ? 's' : ''} starting from ${base}`;
            } else if (value === '0' && type === 'minute') {
                return 'at the start of the hour';
            } else if (value === '0' && type === 'hour') {
                return 'at midnight';
            } else if (type === 'day') {
                return `on the ${value}${getDaySuffix(parseInt(value))} of the month`;
            } else if (type === 'month') {
                return `in ${getMonthName(parseInt(value))}`;
            }
            return `at ${value} ${type}`;
        }

        const formattedMinute = interval.minute ? formatUnit(interval.minute.value.toString(), 'minute') : null;
        const formattedHour = interval.hour ? formatUnit(interval.hour.value.toString(), 'hour') : null;

        // Special case for "at midnight"
        if (formattedMinute === null && formattedHour === 'at midnight') {
            elements.push('at midnight');
        } else {
            if (formattedMinute) elements.push(formattedMinute);
            if (formattedHour) elements.push(formattedHour);
        }

        const day = interval.day ? formatUnit(interval.day.value.toString(), 'day') : "every day";
        const month = interval.month ? formatUnit(interval.month.value.toString(), 'month') : "every month";
        const year = interval.year ? formatUnit(interval.year.value.toString(), 'year') : "every year";

        // Push only non-null values
        if (day) elements.push(day);
        if (month) elements.push(month);
        if (year) elements.push(year)

        if (interval.dayOfWeek && interval.dayOfWeek.length > 0) {
            elements.push(`on ${interval.dayOfWeek.join(', ')}`);
        }

        return elements.filter(e => e).join(', ');
    }
}