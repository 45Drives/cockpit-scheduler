import { BetterCockpitFile, errorString, useSpawn } from '@45drives/cockpit-helpers';
import { getTaskData, getPoolData, getDatasetData, createTaskFiles, createStandaloneTask, createScheduleForTask, removeTask, runTask, getLatestTaskExecutionResult, getTaskStatus, checkTaskTimer, enableTaskTimer, disableTaskTimer, getTaskExecutionResults } from '../composables/utility';
import { ref } from 'vue';

export class Scheduler implements SchedulerType {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }

    async loadTaskInstances() {
        this.taskInstances.splice(0, this.taskInstances.length);

        const tasksData = await getTaskData();

        tasksData.forEach(task => {
            const newTaskTemplate = ref();
            if (task.template == 'ZfsReplicationTask') {
                newTaskTemplate.value = new ZFSReplicationTaskTemplate;
            } else if (task.template == 'AutomatedSnapshotTask') {
                newTaskTemplate.value = new AutomatedSnapshotTaskTemplate;
            }

            const parameters = task.parameters;
            const parameterNodeStructure = this.createParameterNodeFromSchema(newTaskTemplate.value.parameterSchema, parameters);
            const taskIntervals : TaskScheduleInterval[] = [];

            task.schedule.intervals.forEach(interval => {
                const thisInterval = new TaskScheduleInterval(interval);
                taskIntervals.push(thisInterval);
            });

            const newSchedule = new TaskSchedule(task.schedule.enabled, taskIntervals);
            const newTaskInstance = new TaskInstance(task.name, newTaskTemplate.value, parameterNodeStructure, newSchedule); 
            this.taskInstances.push(newTaskInstance);
        });

        console.log('this.taskInstances:', this.taskInstances);
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
            } else if (node instanceof SelectionParameter){
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
            // console.log(`Assigning value for key: ${fullKey}`);  // Debug log to see which keys are being processed
            if (parameters.hasOwnProperty(fullKey)) {
                let value = parameters[fullKey];
                // console.log(`Found value: ${value} for key: ${fullKey}`);  // Debug log to confirm values
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

    async registerTaskInstance(taskInstance : TaskInstance) {
        //generate env file with key/value pairs (Task Parameters)
        const envKeyValues = taskInstance.parameters.asEnvKeyValues();
        console.log('envKeyVals:', envKeyValues);

        const envKeyValuesString = envKeyValues.join('\n')

        const templateName = this.formatTemplateName(taskInstance.template.name);
        
        const templateServicePath = `/opt/45drives/houston/scheduler/templates/${templateName}.service`;
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

        //run script to generate service + timer via template, param env and schedule json
        if (taskInstance.schedule.intervals.length < 1) {
            //ignore schedule for now
            console.log('No schedules found, parameter file generated.');
            
            await createStandaloneTask(templateServicePath, envFilePath);
            
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

            await createTaskFiles(templateServicePath, envFilePath, templateTimerPath, jsonFilePath);
        }

    }   
    
    
    async updateTaskInstance(taskInstance) {
        //populate data from env file and then delete + recreate task files
        const envKeyValues = taskInstance.parameters.asEnvKeyValues();
        console.log('envKeyVals:', envKeyValues);

        const envKeyValuesString = envKeyValues.join('\n')

        const templateName = this.formatTemplateName(taskInstance.template.name);
        
        const templateServicePath = `/opt/45drives/houston/scheduler/templates/${templateName}.service`;

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

        await createStandaloneTask(templateServicePath, envFilePath);
    }
    
    async runTaskNow(taskInstance: TaskInstanceType) {
        //execute service file now
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;
        
        console.log(`Running ${fullTaskName}...`);
        await runTask(fullTaskName);
        console.log(`Task ${fullTaskName} completed.`);
        // return TaskExecutionResult;
    }

    async unregisterTaskInstance(taskInstance: TaskInstanceType) {
        //delete task + associated files
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        await removeTask(fullTaskName);
        console.log(`${fullTaskName} removed`);
    }

    async getTaskStatusFor(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const fullTaskName = houstonSchedulerPrefix + templateName + '_' + taskInstance.name;

        const status = await getTaskStatus(fullTaskName);
        return status;
    }

    async checkScheduleState(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        return await checkTaskTimer(fullTaskName);
    }

    async enableSchedule(taskInstance) {
        //activate timer file
        //run systemctl daemon-reload
        //flip checkbox value
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        await enableTaskTimer(fullTaskName);
        taskInstance.schedule.enabled = true;
        console.log('taskInstance after enable:', taskInstance);
        await this.updateSchedule(taskInstance);

    }
    
    async disableSchedule(taskInstance) {
        //deactivate timer file
        //run systemctl daemon-reload
        //flip checkbox value
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        await disableTaskTimer(fullTaskName);
        taskInstance.schedule.enabled = false;
        console.log('taskInstance after disable:', taskInstance);
        await this.updateSchedule(taskInstance);
    }
    

    async updateSchedule(taskInstance) {
        const templateName = this.formatTemplateName(taskInstance.template.name);
  
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

        await createScheduleForTask(fullTaskName, templateTimerPath, jsonFilePath);
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
            } else if (value === '0' && type === 'minute') {
                return 'at the start of the hour'
            } else if (value === '0' && type === 'hour') {
                return 'at midnight';
            } else if (type === 'day') {
                return `on the ${value}${getDaySuffix(value)} of the month`;
            } else if (type === 'month') {
                return `in ${getMonthName(value)}`;
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
        if(day) elements.push(day);
        if(month) elements.push(month);
        if(year) elements.push(year)
    
        if (interval.dayOfWeek && interval.dayOfWeek.length > 0) {
            elements.push(`on ${interval.dayOfWeek.join(', ')}`);
        }
    
        return elements.filter(e => e).join(', ');
    }
    

    formatTemplateName(templateName) {
        // Split the string into words using space as the delimiter
        let words = templateName.split(' ');
        // Capitalize the first letter of each word and lowercase the rest
        let formattedWords = words.map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
        // Join the words without spaces
        let formattedTemplateName = formattedWords.join('');
        return formattedTemplateName;
    }
    
}

export class TaskTemplate implements TaskTemplateType {
    name: string;
    parameterSchema: ParameterNode;

    constructor(name: string, parameterSchema: ParameterNode) {
        this.name = name;
        this.parameterSchema = parameterSchema;
    }

    createTaskInstance(parameters: ParameterNode) {
        return TaskInstance;
    }
}

export class TaskInstance implements TaskInstanceType {
    name: string;
    template: TaskTemplate;
    parameters: ParameterNode;
    schedule: TaskSchedule;

    constructor(name: string, template: TaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) {
        this.name = name;
        this.template = template;
        this.parameters = parameters;
        this.schedule = schedule;
    }
}

export class TaskSchedule implements TaskScheduleType{
    enabled: boolean;
    intervals: TaskScheduleInterval[];

    constructor(enabled: boolean, intervals: TaskScheduleInterval[]) {
        this.enabled = enabled;
        this.intervals = intervals;
    }
    
}

export class TaskScheduleInterval implements TaskScheduleIntervalType {
    [key: string]: any; // Use a more specific type if possible
    dayOfWeek?: DayOfWeek[];

    constructor(intervalData: TaskScheduleIntervalType) {
        Object.keys(intervalData).forEach(key => {
            this[key] = intervalData[key];
        });
    }
}


export class ZFSReplicationTaskTemplate implements TaskTemplate {
    name: string;
    parameterSchema: ParameterNode;

    constructor() {
        this.name = "ZFS Replication Task";
        this.parameterSchema = new ParameterNode("ZFS Replication Task Config", "zfsRepConfig")
            .addChild(new ZfsDatasetParameter('Source Dataset', 'sourceDataset', '', 0, '', '', ''))
            .addChild(new ZfsDatasetParameter('Destination Dataset', 'destDataset', '', 22, '', '', ''))
            .addChild(new ParameterNode('Send Options', 'sendOptions')
                .addChild(new BoolParameter('Compressed', 'compressed_flag', false))
                .addChild(new BoolParameter('Raw', 'raw_flag', false))
                .addChild(new BoolParameter('Recursive', 'recursive_flag', false))
                .addChild(new IntParameter('MBuffer Size', 'mbufferSize', 1))
                .addChild(new StringParameter('MBuffer Unit', 'mbufferUnit', 'G'))
                .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', false))
                .addChild(new StringParameter('Custom Name', 'customName', ''))
            )
            .addChild(new ParameterNode('Snapshot Retention', 'snapRetention')
                .addChild(new IntParameter('Source', 'source', 5))
                .addChild(new IntParameter('Destination', 'destination', 5)
            )
        );
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: ZFSReplicationTaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
    
}

export class AutomatedSnapshotTaskTemplate implements TaskTemplate {
    name: string;
    parameterSchema: ParameterNode;

    constructor() {
        this.name = "Automated Snapshot Task";
        this.parameterSchema = new ParameterNode("Automated Snapshot Task Config", "autoSnapConfig")
            .addChild(new ZfsDatasetParameter('Filesystem', 'filesystem', '', 0, '', '', ''))
            .addChild(new BoolParameter('Recursive', 'recursive_flag', false))
            .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', false))
            .addChild(new StringParameter('Custom Name', 'customName', ''))
            .addChild(new IntParameter('Snapshot Retention', 'snapRetention', 5));
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: AutomatedSnapshotTaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
    
}

export class ParameterNode implements ParameterNodeType {
    label: string;
    key: string;
    children: ParameterNode[];
    value: any;

    constructor(label: string, key: string) {
        this.label = label;
        this.key = key;
        this.children = [];
    }

    addChild(child: ParameterNode) {
        this.children.push(child);
        return this;
    }

    asEnvKeyValues(): string[] {
        return this.children.map(c => c.asEnvKeyValues()) // recursively get child key=value pairs
            .flat()
            .map(kv => `${this.key}_${kv}`); // prefix key with parent key and _
    }

    // isValid() { }
      
}

export class StringParameter extends ParameterNode implements StringParameterType {
    value: string;

    constructor(label: string, key: string, value: string = '') {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value}`]; // Generate key=value pair for StringParameter
    }
}

export class IntParameter extends ParameterNode implements IntParameterType {
    value: number;

    constructor(label: string, key: string, value: number = 0) {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value.toString()}`]; // Generate key=value pair for IntParameter
    }
}

export class BoolParameter extends ParameterNode implements BoolParameterType {
    value: boolean;

    constructor(label: string, key: string, value: boolean = false) {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value ? 'true' : 'false'}`]; // Generate key=value pair for BoolParameter
    }
}


export class SelectionOption implements SelectionOptionType {
    value: string | number | boolean;
    label: string;

    constructor(value: string | number | boolean, label: string) {
        this.value = value;
        this.label = label;
    }
}

export class SelectionParameter extends ParameterNode implements SelectionParameterType {
    value: string;
    options: SelectionOption[];

    constructor(label: string, key: string, value: string = '', options: SelectionOption[] = []) {
        super(label, key);
        this.value = value;
        this.options = options;
    }

    addOption(option: SelectionOption) {
        this.options.push(option);
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value}`]; // Implement logic to handle options if needed
    }
}

export class ZfsDatasetParameter extends ParameterNode implements ParameterNodeType {
    constructor(label: string, key: string, host: string = "", port: number = 0, user: string = "", pool: string = "", dataset: string = "") {
        super(label, key);
        
        // Add child parameters
        this.addChild(new StringParameter("Host", "host", host));
        this.addChild(new IntParameter("Port", "port", port));
        this.addChild(new StringParameter("User", "user", user));
        
        // const poolParam = new SelectionParameter("Pool", "pool", pool);
        const poolParam = new SelectionParameter("Pool", "pool", pool);
        
        this.addChild(poolParam);
        
        // const datasetParam = new SelectionParameter("Dataset", "dataset", dataset);
        const datasetParam = new SelectionParameter("Dataset", "dataset", dataset);     
        this.addChild(datasetParam);

    }

    async loadPools() {
        const pools = await getPoolData(this.children['host'], this.children['port'], this.children['user'])
        const poolParam = this.getChild('pool') as SelectionParameter;

        pools.forEach(pool => {
            poolParam.addOption(new SelectionOption(pool, pool));
            // this.loadDatasets(pools[0]);
        });
    }

    async loadDatasets(pool: string) {
        const datasets = await getDatasetData(this.children['host'], this.children['port'], this.children['user'], pool);
        const datasetParam = this.getChild('dataset') as SelectionParameter;
        
        datasets.forEach(dataset => {
            datasetParam.addOption(new SelectionOption(dataset, dataset));
        });
    }

    getChild(key: string): ParameterNode {
        const child = this.children.find(child => child.key === key);
        if (!child) {
            throw new Error(`Child with key ${key} not found`);
        }
        return child;
    }
}

export class TaskExecutionLog {
    entries: TaskExecutionResult[];

    constructor(entries: TaskExecutionResult[]) {
        this.entries = entries;
    }

    // async loadEntries() {}


    async getEntriesFor(taskInstance, timestamp) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;

        const fullTaskName = houstonSchedulerPrefix + templateName + '_' + taskName;
        
        const taskLogData = await getTaskExecutionResults(fullTaskName, timestamp);
        // console.log('taskLogData:', taskLogData);
        
        return taskLogData;
    }

    async getLatestEntryFor(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;

        const fullTaskName = houstonSchedulerPrefix + templateName + '_' + taskName;
        const latestEntry = await getLatestTaskExecutionResult(fullTaskName);

        // console.log('latest entry:', latestEntry);
        const logEntry = new TaskExecutionResult(latestEntry.exit_code, latestEntry.output, latestEntry.start_date, latestEntry.finish_date)

        return logEntry || 'None';
    }

    formatTemplateName(templateName) {
        // Split the string into words using space as the delimiter
        let words = templateName.split(' ');
        // Capitalize the first letter of each word and lowercase the rest
        let formattedWords = words.map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
        // Join the words without spaces
        let formattedTemplateName = formattedWords.join('');
        return formattedTemplateName;
    }

}

export class TaskExecutionResult {
    exitCode: number;
    output: string;
    // startDate: Date;
    // finishDate: Date;
    startDate: string;
    finishDate: string;

    // constructor(exitCode: number, output: string, startDate: Date, finishDate: Date) {
    constructor(exitCode: number, output: string, startDate: string, finishDate: string) {
        this.exitCode = exitCode;
        this.output = output;
        this.startDate = startDate;
        this.finishDate = finishDate;
    }
}