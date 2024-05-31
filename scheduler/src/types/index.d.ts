interface SchedulerType {
	taskTemplates: TaskTemplateType[];
	taskInstances: TaskInstanceType[];

	async loadTaskInstances(): void;
	createParameterNodeFromSchema(schema: ParameterNode, parameters: any) : ParameterNode;
	async registerTaskInstance(taskInstance: TaskInstance): void;
	async updateTaskInstance(taskInstance: TaskInstance): void;
	async runTaskNow(taskInstance: TaskInstance): void;
	async unregisterTaskInstance(taskInstance: TaskInstance): void;
	async getTaskStatusFor(taskInstance: TaskInstance): string;
	async enableSchedule(taskInstance: TaskInstance): void;
	async disableSchedule(taskInstance: TaskInstance): void;
	async updateSchedule(taskInstance: TaskInstance): void;
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
	async getLatestEntryFor(taskInstance: TaskInstance): string;
}

interface TaskExecutionResultType {
	exitCode: number;
	output: string;
	startDate: string;
	finishDate: string;
}

type ConfirmationCallback = (param?: any) => void;