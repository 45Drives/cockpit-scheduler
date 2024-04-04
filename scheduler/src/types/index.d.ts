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

interface TaskScheduleType {
	enabled: boolean;
	intervals: TaskScheduleIntervalType[];
}

interface TaskScheduleIntervalType {
	value: number;
	unit: 'seconds'|'minutes'|'hours'|'days'|'weeks'|'months'|'years'|'dayOfWeek'|'dayOfMonth';
	// etc. ??? DayOfWeek, DayOfMonth, account for steps/lists/ranges?
	// presets: none | hourly | daily | weekly | monthly | yearly
}

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
	uiComponent?(): UIComponent;
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

interface ZfsDatasetParameterType extends ParameterNodeType {
	children: []
}
  
interface TaskExecutionLogType {
	entries: TaskExecutionResultType[];
}

interface TaskExecutionResultType {
	exitCode: number;
	output: string;
	startDate: Date;
	finishDate: Date;
}

interface ZFSReplicationTaskTemplate extends TaskTemplate {

}


type ConfirmationCallback = () => void;

//object for navigation (generic)
interface NavigationItem {
	name: string;
	tag: string;
	current: boolean;
	show: boolean;
}

type NavigationCallback = (item: NavigationItem) => void;
