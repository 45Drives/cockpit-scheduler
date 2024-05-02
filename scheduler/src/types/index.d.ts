interface SchedulerType {
	taskTemplates: TaskTemplateType[];
	taskInstances: TaskInstanceType[];
}

interface TaskTemplateType {
	name: string;
	parameterSchema: ParameterNodeType;
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
	// value: number | string;
	value: string;
}

interface TaskScheduleType {
	enabled: boolean;
	intervals: TaskScheduleIntervalType[];
}

type TaskScheduleIntervalType = {
    [K in TimeUnit]?: TimeComponentType; // Make each property optional
} & {
    dayOfWeek?: (DayOfWeek)[]; // Additional properties can be added like this
};

interface LocationType {
	host: string;
	port: number;
	user?: string;
	root: string;
	path: string;
}

type UIComponent = any;

interface ParameterNodeType {
	label: string;
	key: string;
	children: ParameterNodeType[];
	value?: any;
	uiComponent?: UIComponent;
}

interface SelectionParameterType extends ParameterNodeType {
	value: string;
	options: SelectionOptionType[];
}

interface SelectionOptionType {
    value: string | number | boolean;
    label: string;
}

interface StringParameterType extends ParameterNodeType {
	value: string;
}

interface BoolParameterType extends ParameterNodeType {
	value: boolean;
}

interface IntParameterType extends ParameterNodeType {
	value: number;
}

// interface ZfsDatasetParameterType extends ParameterNodeType {
// 	children: []
// }
  
interface TaskExecutionLogType {
	entries: TaskExecutionResultType[];
}

interface TaskExecutionResultType {
	exitCode: number;
	output: string;
	startDate: Date;
	finishDate: Date;
}

// interface ZFSReplicationTaskTemplate extends TaskTemplate {

// }


type ConfirmationCallback = (param?: any) => void;