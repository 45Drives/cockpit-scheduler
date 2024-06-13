import { useSpawn, errorString } from '@45drives/cockpit-helpers';
import { formatTemplateName } from '../composables/utility';

export class TaskExecutionLog {
    entries: TaskExecutionResult[];

    constructor(entries: TaskExecutionResult[]) {
        this.entries = entries;
    }

    async getEntriesFor(taskInstance, untilTime) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;
    
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}`;
    
        try {
            if (!untilTime) {
                console.log("No until time provided");
                // Fallback to get the most recent log entries if no start time is available
                const logCommand = ['journalctl', '-r', '-u', fullTaskName, '--no-pager', '--all', '-n', '1']; // Limit to the most recent log entry
                const logState = useSpawn(logCommand, {superuser: 'try'});
                const logResult = await logState.promise();
                return logResult.stdout;
            }
    
            const command = ['journalctl', '-u', fullTaskName, '--until', untilTime, '--no-pager', '--all'];
            const state = useSpawn(command, { superuser: 'try' });
            const result = await state.promise();
            const taskLogData = result.stdout.trim();
            // console.log('taskLogData:', taskLogData);

            return taskLogData;
        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }
    

    async getLatestEntryFor(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;
    
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}`;
    
        try {
            const execCommand = ['systemctl', 'show', fullTaskName, '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp'];
            const execState = useSpawn(execCommand, {superuser: 'try'});
            const execResult = await execState.promise();
    
            const properties = Object.fromEntries(execResult.stdout.split('\n').filter(line => line.includes('=')).map(line => line.split('=')));
            const exitCode = properties['ExecMainStatus'] || '0';
            const startTime = properties['ExecMainStartTimestamp'] || '';
            const finishTime = properties['ExecMainExitTimestamp'] || '';
    
            let output = "";
            if (startTime) {
                const logCommand = ['journalctl', '-u', fullTaskName, '--since', startTime, '--no-pager', '--all'];
                const logState = useSpawn(logCommand, {superuser: 'try'});
                const logResult = await logState.promise();
                output = logResult.stdout;
            } else {
                output = "Task hasn't run since boot or is disabled.";
                // Fallback to get the most recent log entries if no start time is available
                // const logCommand = ['journalctl', '-r', '-u', fullTaskName, '--no-pager', '--all', '-n', '1']; // Limit to the most recent log entry
                // const logState = useSpawn(logCommand, {superuser: 'try'});
                // const logResult = await logState.promise();
                // output = logResult.stdout || "Task hasn't run since boot or is disabled.";
            }
    
            const latestEntry = new TaskExecutionResult(exitCode, output, startTime, finishTime);
            // console.log('latest entry:', latestEntry);
            return latestEntry;
        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }
}

export class TaskExecutionResult {
    exitCode: number;
    output: string;
    startDate: string;
    finishDate: string;

    constructor(exitCode: number, output: string, startDate: string, finishDate: string) {
        this.exitCode = exitCode;
        this.output = output;
        this.startDate = startDate;
        this.finishDate = finishDate;
    }
}