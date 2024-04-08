export class Scheduler implements SchedulerType {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }

    loadTaskInstances() {
        // check /etc/systemd/system/ for .service files (that also have .env)
        
    }
    
    


    registerTaskInstance(taskInstance) {
        //generate key/value pairs
        //run script to generate env file with key/value pairs
        //run script to generate service + timer via env file + template, with schedule (as string?)


        //run systemctl daemon-reload

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
    }
    
    disableSchedule(taskInstance) {
        //deactivate timer file
        //run systemctl daemon-reload
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

export class TaskScheduleInterval implements TaskScheduleIntervalType{
    value: number;
    unit: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years';
    //need to account for DayOfWeek, DayOfMonth, steps, ranges, lists, etc.

    constructor(value: number, unit: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years') {
        this.value = value;
        this.unit = unit;
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
                .addChild(new StringParameter('Custom Name Schema', 'customNameSchema', ''))
            )
            .addChild(new IntParameter('Snapshot Retention', 'snapsToKeep', 5));
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: TaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}

export class ParameterNode implements ParameterNodeType {
    label: string;
    key: string;
    children: ParameterNode[];

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
        
        const poolParam = new SelectionParameter("Pool", "pool", pool);
        this.addChild(poolParam);
        
        const datasetParam = new SelectionParameter("Dataset", "dataset", dataset);     
        this.addChild(datasetParam);
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
        const user = (this.children[4] as SelectionParameter).value;
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

