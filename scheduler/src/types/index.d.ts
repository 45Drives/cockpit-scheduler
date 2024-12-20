interface SchedulerType {
	taskTemplates: TaskTemplateType[];
	taskInstances: TaskInstanceType[];

	async loadTaskInstances(): void;
	createParameterNodeFromSchema(schema: ParameterNode, parameters: any): ParameterNode;
	async registerTaskInstance(taskInstance: TaskInstanceType): void;
	async updateTaskInstance(taskInstance: TaskInstanceType): void;
	async runTaskNow(taskInstance: TaskInstanceType): void;
	async unregisterTaskInstance(taskInstance: TaskInstanceType): void;
	async getServiceStatus(taskInstance: TaskInstanceType): Promise<string | false>
	async getTimerStatus(taskInstance: TaskInstanceType): Promise<string | false>
	async enableSchedule(taskInstance: TaskInstanceType): void;
	async disableSchedule(taskInstance: TaskInstanceType): void;
	async updateSchedule(taskInstance: TaskInstanceType): void;
	parseIntervalIntoString(interval: TaskScheduleInterval): string;
}

interface TaskTemplateType {
	name: string;
	parameterSchema: ParameterNodeType;

	createTaskInstance(parameters: ParameterNode): TaskInstance;
}

interface TaskInstanceType {
	name: string;
	template: TaskTemplateType;
	parameters: ParameterNodeType;
	schedule: TaskScheduleType;
}

type TimeUnit = 'minute' | 'hour' | 'day' | 'month' | 'year';
type DayOfWeek = 'Sun' | 'Mon' | 'Tue' | 'Wed' | 'Thu' | 'Fri' | 'Sat';

interface TimeComponentType {
	value: string;
}

interface TaskScheduleType {
	enabled: boolean;
	intervals: TaskScheduleIntervalType[];
}

type TaskScheduleIntervalType = {
	[K in TimeUnit]?: TimeComponentType;
} & {
	dayOfWeek?: (DayOfWeek)[];
};

interface LocationType {
	host: string;
	port: number;
	user?: string;
	root: string;
	path: string;
}

interface ParameterNodeType {
	label: string;
	key: string;
	children: ParameterNodeType[];
	value?: any;

	addChild(child: ParameterNode): ParameterNode;
	asEnvKeyValues(): string[];
}

interface SelectionParameterType extends ParameterNodeType {
	value: string;
	options: SelectionOptionType[];

	addOption(option: SelectionOption);
	asEnvKeyValues(): string[];
}

interface SelectionOptionType {
	value: string | number | boolean;
	label: string;
}

interface StringParameterType extends ParameterNodeType {
	value: string;

	asEnvKeyValues(): string[];
}

interface BoolParameterType extends ParameterNodeType {
	value: boolean;

	asEnvKeyValues(): string[];
}

interface IntParameterType extends ParameterNodeType {
	value: number;

	asEnvKeyValues(): string[];
}

interface TaskExecutionLogType {
	entries: TaskExecutionResultType[];

	async getEntriesFor(taskInstance: TaskInstance, untilTime: string): string;
	async getLatestEntryFor(taskInstance: TaskInstance): TaskExecutionResult;
	async getLatestEntryFor(taskInstance: TaskInstance): TaskExecutionResult;
}

interface TaskExecutionResultType {
	exitCode: number;
	output: string;
	startDate: string;
	finishDate: string;
}

type ConfirmationCallback = (param?: any) => void;

interface DiskData {
	name: string;
	capacity: string;
	model: string;
	type: string;
	health: string;
	phy_path: string;
	sd_path: string;
	vdev_path: string;
	serial: string;
	temp: string;
}

interface DiskDetails {
	diskName: string;
	diskPath: string;
}

interface CloudSyncRemoteType {
	name: string;
	type: string;
	authParams: CloudAuthParameterType;
}

interface CloudAuthParameterType {
	parameters: {
		[key: string]: CloudSyncParameter;
	};
	provider?: string;
	oAuthSupported?: boolean;
}

interface CloudSyncParameterType {
	value: any;
	type: 'string' | 'bool' | 'int' | 'select' | 'object';
	allowedValues?: string[];
	defaultValue?: string | number | boolean | object;
}

interface RemoteManagerType {
	cloudSyncRemotes: CloudSyncRemoteType[];

	async getRemotes(): void;
	async getRemoteByName(remoteName: string): Promise<CloudSyncRemote | null>;
	createRemote(label: string, key: string, name: string, type: string, parameters: any): CloudSyncRemote;
	editRemote(key: string, newLabel: string, oldName: string, newType: string, parameters: any): CloudSyncRemote
	deleteRemote(key: string): Promise<boolean>;
}

