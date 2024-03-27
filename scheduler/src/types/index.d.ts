interface Scheduler {
	taskTemplates: TaskTemplate[];
	taskInstances: TaskInstance[];
}

interface TaskTemplate {
	name: string;
	parameterSchema: ParameterNode;
}

interface TaskInstance {
	name: string;
	template: TaskTemplate;
	parameters: ParameterNode;
	schedule: TaskSchedule;
}

interface TaskSchedule {
	enabled: boolean;
	intervals: TaskScheduleInterval[];
}

interface TaskScheduleInterval {
	value: number;
	unit: 'seconds'|'minutes'|'hours'|'days'|'weeks'|'months'|'years';
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

interface ParameterNode {
	label: string;
	key: string;
	children: ParameterNode[];
}

interface SelectionParameter extends ParameterNode {
	value: string;
	options: SelectionOption[];
}

interface SelectionOption {
    value: string | number | boolean;
    label: string;
}

interface StringParameter extends ParameterNode {
	value: string;
}

interface BoolParameter extends ParameterNode {
	value: boolean;
}

interface IntParameter extends ParameterNode {
	value: number;
}

interface ZfsDatasetParameter extends ParameterNode {
	children: []
}
  
interface TaskExecutionLog {
	entries: TaskExecutionResult[];
}

interface TaskExecutionResult {
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
