import { ParameterNode, ZfsDatasetParameter, StringParameter, BoolParameter, IntParameter, SelectionParameter, SelectionOption, LocationParameter } from "./Parameters";

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

export class ZFSReplicationTaskTemplate extends TaskTemplate {
    constructor() {
        const name = "ZFS Replication Task";
        const parameterSchema = new ParameterNode("ZFS Replication Task Config", "zfsRepConfig")
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
                .addChild(new IntParameter('Destination', 'destination', 5))
            );
        super(name, parameterSchema);
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: ZFSReplicationTaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}

export class AutomatedSnapshotTaskTemplate extends TaskTemplate {
    constructor() {
        const name = "Automated Snapshot Task";
        const parameterSchema = new ParameterNode("Automated Snapshot Task Config", "autoSnapConfig")
            .addChild(new ZfsDatasetParameter('Filesystem', 'filesystem', '', 0, '', '', ''))
            .addChild(new BoolParameter('Recursive', 'recursive_flag', false))
            .addChild(new BoolParameter('Custom Name Flag', 'customName_flag', false))
            .addChild(new StringParameter('Custom Name', 'customName', ''))
            .addChild(new IntParameter('Snapshot Retention', 'snapRetention', 5)
        );
        super(name, parameterSchema);
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: AutomatedSnapshotTaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}

export class RsyncTaskTemplate extends TaskTemplate {
    constructor() {
        const name = "Rsync Task";
        const push = new SelectionOption('push', 'Push');
        const pull = new SelectionOption('pull', 'Pull');
        const directionSelection = [] as any as SelectionOption[];
        directionSelection.push(push);
        directionSelection.push(pull);
        const parameterSchema = new ParameterNode("Rsync Task Config", "rsyncConfig")
        .addChild(new StringParameter('Local Path', 'local_path', ''))
        .addChild(new LocationParameter('Target Information', 'target_info', '', 22, '', '', ''))
        .addChild(new SelectionParameter('Direction', 'direction', 'push', directionSelection))
        .addChild(new ParameterNode('Rsync Options', 'rsyncOptions')
            .addChild(new BoolParameter('Archive', 'archive_flag', true))
            .addChild(new BoolParameter('Recursive', 'recursive_flag', false))
            .addChild(new BoolParameter('Compressed', 'compressed_flag', false))
            .addChild(new BoolParameter('Delete', 'delete_flag', false))
            .addChild(new BoolParameter('Quiet', 'quiet_flag', false))
            .addChild(new BoolParameter('Preserve Times', 'times_flag', false))
            .addChild(new BoolParameter('Preserve Hard Links', 'hardLinks_flag', false))
            .addChild(new BoolParameter('Preserve Permissions', 'permissions_flag', false))
            .addChild(new BoolParameter('Preserve Extended Attributes', 'xattr_flag', false))
            .addChild(new IntParameter('Limit Bandwidth', 'bandwidth_limit_kbps', 0))
            .addChild(new StringParameter('Include', 'include_pattern', ''))
            .addChild(new StringParameter('Exclude', 'exclude_pattern', ''))
            .addChild(new StringParameter('Additional Custom Arguments', 'custom_args', ''))
            .addChild(new BoolParameter('Parallel Transfer', 'parallel_flag', false))
            .addChild(new IntParameter('Threads', 'parallel_threads', 0))
        );
        super(name, parameterSchema);
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: RsyncTaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}

export class ScrubTaskTemplate extends TaskTemplate {
    constructor() {
        const name = "Scrub Task";
        const parameterSchema = new ParameterNode("Scrub Task Config", "scrubConfig")
        .addChild(new ZfsDatasetParameter('Pool', 'pool', '', 0, '', '', ''));

        super(name, parameterSchema);
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: ScrubTaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}

export class SmartTestTemplate extends TaskTemplate {
    constructor() {
        const name = "SMART Test";
        // const testTypeOptions = [
        //     new SelectionOption('short', 'short'),
        //     new SelectionOption('long', 'long'),
        //     new SelectionOption('conveyance', 'conveyance'),
        //     new SelectionOption('offline', 'offline'),
        // ];

        const parameterSchema = new ParameterNode("SMART Test Config", "smartTestConfig")
        // .addChild(new ListParameter('Disks', 'disks', []))
        // .addChild(new SelectionParameter('Test Type', 'test_type', 'short', testTypeOptions));
        .addChild(new StringParameter('Disks', 'disks', ''))
        .addChild(new StringParameter('Test Type', 'testType', ''))

        super(name, parameterSchema);
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: SmartTestTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}