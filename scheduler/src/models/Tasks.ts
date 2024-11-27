import { ParameterNode, ZfsDatasetParameter, StringParameter, BoolParameter, IntParameter, SelectionParameter, SelectionOption, LocationParameter, SnapshotRetentionParameter } from "./Parameters";
import { cloudSyncProviders, CloudSyncRemote } from './CloudSync';
import { TaskExecutionResult } from "./TaskLog";

export class TaskInstance implements TaskInstanceType {
    name: string;
    template: TaskTemplate;
    parameters: ParameterNode;
    schedule: TaskSchedule;
    // status: string;
    // lastExecutionResult: TaskExecutionResult | null;


    constructor(name: string, template: TaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) {
        this.name = name;
        this.template = template;
        this.parameters = parameters;
        this.schedule = schedule;
        // this.status = 'Pending';  // Default status
        // this.lastExecutionResult = null;  // No result initially

    }
}

export class TaskSchedule implements TaskScheduleType {
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
            .addChild(new ParameterNode('Snapshot Retention', 'snapshotRetention')
                .addChild(new SnapshotRetentionParameter('Source', 'source', 0, 'minutes'))
                .addChild(new SnapshotRetentionParameter('Destination', 'destination', 0, 'minutes'))
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
            .addChild(new SnapshotRetentionParameter('Snapshot Retention', 'snapshotRetention', 0, 'minutes')
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

        const directionSelection = [
            new SelectionOption('push', 'Push'),
            new SelectionOption('pull', 'Pull')
        ];
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
        const parameterSchema = new ParameterNode("SMART Test Config", "smartTestConfig")
            .addChild(new StringParameter('Disks', 'disks', ''))
            .addChild(new StringParameter('Test Type', 'testType', ''))

        super(name, parameterSchema);
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: SmartTestTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}

export class CloudSyncTaskTemplate extends TaskTemplate {
    constructor() {
        const name = "Cloud Sync Task";

        const providerSelectionOptions = Object.keys(cloudSyncProviders).map(providerKey => {
            const provider = cloudSyncProviders[providerKey];
            return new SelectionOption(providerKey, provider.name);
        });

        const directionSelection = [
            new SelectionOption('push', 'Push'),
            new SelectionOption('pull', 'Pull')
        ];

        const transferModeSelection = [
            new SelectionOption('copy', 'Copy'),
            new SelectionOption('move', 'Move'),
            new SelectionOption('sync', 'Sync'),
        ];

        const cutoffModeSelection = [
            new SelectionOption('hard', 'Hard'),
            new SelectionOption('soft', 'Soft'),
            new SelectionOption('cautious', 'Cautious'),
        ];

        const initialProviderKey = providerSelectionOptions[0].value;
        const initialProvider = cloudSyncProviders[initialProviderKey];

        const parameterSchema = new ParameterNode("Cloud Sync Task Config", "cloudSyncConfig")
            .addChild(new StringParameter('Local Path', 'local_path', ''))
            .addChild(new StringParameter('Target Path', 'target_path', ''))
            .addChild(new SelectionParameter('Direction', 'direction', 'push', directionSelection))
            .addChild(new SelectionParameter('Transfer Type', 'type', 'copy', transferModeSelection))
            .addChild(new SelectionParameter('Provider', 'provider', initialProviderKey, providerSelectionOptions))
            // .addChild(new CloudSyncRemote('',initialProviderKey, initialProvider.providerParams, initialProvider))
            .addChild(new StringParameter('Rclone Remote', 'rclone_remote', ''))
            .addChild(new ParameterNode('Rclone Options', 'rcloneOptions')
                .addChild(new BoolParameter('Check First', 'check_first_flag', false))
                .addChild(new BoolParameter('Checksum', 'checksum_flag', false))
                .addChild(new BoolParameter('Update', 'update_flag', false))
                .addChild(new BoolParameter('Ignore Existing', 'ignore_existing_flag', false))
                .addChild(new BoolParameter('Dry Run', 'dry_run_flag', false))
                .addChild(new IntParameter('Number of Transfers', 'transfers', 4))
                .addChild(new StringParameter('Include Pattern', 'include_pattern', ''))
                .addChild(new StringParameter('Exclude Pattern', 'exclude_pattern', ''))
                .addChild(new StringParameter('Additional Custom Arguments', 'custom_args', ''))
                .addChild(new IntParameter('Limit Bandwidth', 'bandwidth_limit_kbps', 0))
                .addChild(new BoolParameter('Ignore Size', 'ignore_size_flag', false))
                .addChild(new BoolParameter('Inplace', 'inplace_flag', false))
                .addChild(new IntParameter('Multi-Thread Chunk Size', 'multithread_chunk_size', 0))
                .addChild(new StringParameter('Multi-Thread Chunk Size Unit', 'multithread_chunk_size_unit', 'MiB'))
                .addChild(new IntParameter('Multi-Thread Cutoff', 'multithread_cutoff', 0))
                .addChild(new StringParameter('Multi-Thread Cutoff Unit', 'multithread_cutoff_unit', 'MiB'))
                .addChild(new IntParameter('Multi-Thread Streams', 'multithread_streams', 0))
                .addChild(new IntParameter('Multi-Thread Write Buffer Size', 'multithread_write_buffer_size', 0))
                .addChild(new StringParameter('Multi-Thread Write Buffer Size Unit', 'multithread_write_buffer_size_unit', 'KiB'))
                .addChild(new StringParameter('Files From', 'include_from_path', ''))
                .addChild(new StringParameter('Exclude From', 'exclude_from_path', ''))
                .addChild(new IntParameter('Max Transfer Size', 'max_transfer_size', 0))
                .addChild(new IntParameter('Max Transfer Size Unit', 'max_transfer_size_unit', 0))
                .addChild(new SelectionParameter('Cutoff Mode', 'cutoff_mode', 'HARD', cutoffModeSelection))
                .addChild(new BoolParameter('No Traverse', 'no_traverse_flag', false))
            )
            
        super(name, parameterSchema);
    }

    createTaskInstance(parameters: ParameterNode, schedule?: TaskSchedule): new (name: string, template: CloudSyncTaskTemplate, parameters: ParameterNode, schedule: TaskSchedule) => TaskInstance {
        // Return the TaskInstance constructor function
        return TaskInstance;
    }
}
