import { useSpawn, errorString } from '@45drives/cockpit-helpers';
// @ts-ignore
import get_tasks_script from '../scripts/get-task-instances.py?raw';
// @ts-ignore
import get_datasets_script from '../scripts/get-datasets-in-pool.py?raw';
// @ts-ignore
import get_pools_script from '../scripts/get-pools.py?raw';

//['/usr/bin/env', 'python3', '-c', script, ...args ]


export class Scheduler implements SchedulerType {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }

    async loadTaskInstances() {
        try {
            const state = useSpawn(['/usr/bin/env','python3', '-c', get_tasks_script], {superuser: 'try'});
            const tasksOutput = (await state.promise()).stdout;
            // console.log('Raw tasksOutput:', tasksOutput);
            const tasksData = JSON.parse(tasksOutput);

            tasksData.forEach(task => {
                if (task.template == 'ZfsReplicationTask') {
                    const newTaskTemplate = new ZFSReplicationTaskTemplate;
                    const parameters = task.parameters;
                    const parameterNodeStructure = this.createParameterNodeFromSchema(newTaskTemplate.parameterSchema, parameters);

                    const newSchedule = new TaskSchedule(task.schedule.enabled, task.schedule.intervals);
                    const newTaskInstance = new TaskInstance(task.name, newTaskTemplate, parameterNodeStructure, newSchedule); 
                    this.taskInstances.push(newTaskInstance);
                }
            });

            console.log('this.taskInstances:', this.taskInstances);
    
        } catch (error) {
            console.error(errorString(error));
            return null;
        }
    }
        

    // Helper function to flatten the ParameterNode schema into a dictionary for easy lookup
    flattenSchema(node: ParameterNode, prefix = ''): { [key: string]: ParameterNode } {
        let dict: { [key: string]: ParameterNode } = {};
        const currentPrefix = prefix ? prefix + '_' : '';
        dict[currentPrefix + node.key] = node;
        node.children.forEach(child => {
            Object.assign(dict, this.flattenSchema(child, currentPrefix + node.key));
        });
        return dict;
    }

    // Main function to create a ParameterNode from JSON parameters based on a schema
    createParameterNodeFromSchema(schema: ParameterNode, parameters: any): ParameterNode {
        // Flatten the schema to easily match keys from JSON
        const flatSchema = this.flattenSchema(schema);
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

    registerTaskInstance(taskInstance) {
        //generate env file with key/value pairs (Task Parameters)
        //generate json file with enabled boolean + intervals (Schedule Intervals)

        //run script to generate service + timer via template, param env and schedule json

    }   
    
    unregisterTaskInstance(taskInstance) {
        //delete task + associated files
    }
    
    updateTaskInstance(taskInstance) {
        //populate data from env file and then delete + recreate task files
    }
    
    runTaskNow(taskInstance) {
        //execute service file now

        // return TaskExecutionResult;
    }
    
    loadSchedulesFor(taskInstance) {
        // return TaskSchedule[];
    }
    
    enableSchedule(taskInstance) {
        //activate timer file
        //run systemctl daemon-reload
        //flip checkbox value
    }
    
    disableSchedule(taskInstance) {
        //deactivate timer file
        //run systemctl daemon-reload
        //flip checkbox value
    }
    
    updateSchedule(taskInstance) {
        
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

class TaskScheduleInterval implements TaskScheduleIntervalType {
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
    
    // createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): TaskInstance {
    //     return new TaskInstance(this.name, this, parameters, schedule!);
    // }
    
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

    isValid() {
        // Implementation for validation
    }

    /* uiComponent(): Component {
         // Dynamically return Vue component based on parameter type
        if (this instanceof StringParameter) {
            return StringParameterComponent;
        } else if (this instanceof IntParameter) {
            return IntParameterComponent;
        } else if (this instanceof BoolParameter) {
            return BoolParameterComponent;
        } else if (this instanceof SelectionParameter) {
            return SelectParameterComponent;
        } else if (this instanceof ZfsDatasetParameter) {
            return ZFSDatasetParameterComponent;
        } else {
            // Handle other parameter types or default case
            return GenericComponent;
        }
    } */


      
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
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_pools_script, this.children['host'], this.children['port'], this.children['user']]);
        const poolsData = (await state.promise()).stdout;
        const pools = JSON.parse(poolsData)
        const poolParam = this.getChild('pool') as SelectionParameter;

        pools.forEach(pool => {
            poolParam.addOption(new SelectionOption(pool, pool));
            // this.loadDatasets(pools[0]);
        });
    }

    async loadDatasets(pool: string) {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_datasets_script, this.children['host'], this.children['port'], this.children['user'], pool]);
        const datasetsData = (await state.promise()).stdout;
        const datasets = JSON.parse(datasetsData)
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
    


    // Method to create ZfsDatasetParameter from a location
    static fromLocation(label: string, key: string, location: Location): ZfsDatasetParameter {
        const { host, port, user, root, path } = location;
        return new ZfsDatasetParameter(label, key, host, port, user, root, path);
    }

    // Method to convert ZfsDatasetParameter to a location
    toLocation(): Location {
        const label = (this.children[0] as StringParameter).value;
        const key = (this.children[1] as StringParameter).value;
        const host = (this.children[2] as StringParameter).value;
        const port = (this.children[3] as IntParameter).value;
        const user = (this.children[4] as StringParameter).value;
        const root = (this.children[5] as SelectionParameter).value;
        const path = (this.children[6] as SelectionParameter).value;

        return { host, port, user, root, path };
    }
}

export class Location implements LocationType {
    host: string;
    port: number;
    user: string;
    root: string;
    path: string;

    constructor(host: string, port: number, user: string, root: string, path: string) {
        this.host = host;
        this.port = port;
        this.user = user;
        this.root = root;
        this.path = path;
    }
}

export class TaskExecutionLog {
    entries: TaskExecutionResult[];

    constructor(entries: TaskExecutionResult[]) {
        this.entries = entries;
    }

    loadEntries() {

    }

    getEntriesFor(TaskInstance) {
        // return TaskExecutionResult[];
    }

    getLatestEntryFor(TaskInstance) {
        return TaskExecutionResult || 'None';
    }

}

export class TaskExecutionResult {
    exitCode: number;
    output: string;
    startDate: Date;
    finishDate: Date;

    constructor(exitCode: number, output: string, startDate: Date, finishDate: Date) {
        this.exitCode = exitCode;
        this.output = output;
        this.startDate = startDate;
        this.finishDate = finishDate;
    }
}

