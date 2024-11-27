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
                const logState = useSpawn(logCommand, { superuser: 'try' });
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

    //original logs function

    //original logs function
    async getLatestEntryFor(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;

        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}`;

        try {
            const execCommand = ['systemctl', 'show', fullTaskName, '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp'];
            const execState = useSpawn(execCommand, { superuser: 'try' });
            const execResult = await execState.promise();

            const properties = Object.fromEntries(execResult.stdout.split('\n').filter(line => line.includes('=')).map(line => line.split('=')));
            const exitCode = properties['ExecMainStatus'] || '0';
            const startTime = properties['ExecMainStartTimestamp'] || '';
            const finishTime = properties['ExecMainExitTimestamp'] || '';

            let output = "";
            if (startTime) {
                const logCommand = ['journalctl', '-u', fullTaskName, '--since', startTime, '--no-pager', '--all'];
                const logState = useSpawn(logCommand, { superuser: 'try' });
                const logResult = await logState.promise();
                output = logResult.stdout;
            } else {
                output = "No executions found.";
                
                // Fallback to get the most recent log entries if no start time is available
              /*   const logCommand = ['journalctl', '-r', '-u', fullTaskName, '--no-pager', '--all', '-n', '1']; // Limit to the most recent log entry
                const logState = useSpawn(logCommand, {superuser: 'try'});
                const logResult = await logState.promise();
                output = logResult.stdout || "Task hasn't run since boot or is disabled."; */
            }

            const latestEntry = new TaskExecutionResult(exitCode, output, startTime, finishTime);
            // console.log('latest entry:', latestEntry);
            return latestEntry;
        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }

    // async getLatestEntryFor(taskInstance) {
    //     const houstonSchedulerPrefix = 'houston_scheduler_';
    //     const templateName = formatTemplateName(taskInstance.template.name);
    //     const taskName = taskInstance.name;

    //     const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}.service`;

    //     try {
    //         // Check systemd properties first
    //         const execCommand = ['systemctl', 'show', fullTaskName, '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp'];
    //         const execState = useSpawn(execCommand, { superuser: 'try' });
    //         const execResult = await execState.promise();

    //         const properties = Object.fromEntries(execResult.stdout.split('\n').filter(line => line.includes('=')).map(line => line.split('=')));
    //         const exitCode = properties['ExecMainStatus'] || '0';
    //         const startTime = properties['ExecMainStartTimestamp'] || '';
    //         const finishTime = properties['ExecMainExitTimestamp'] || '';

    //         let output = "";
    //         if (!startTime) {
    //             // // If no start time from systemctl, fetch the last run from journalctl logs
    //             // const logCommand = ['journalctl', '-r', '-u', fullTaskName, '--no-pager', '--all', '-n', '1'];
    //             // const logState = useSpawn(logCommand, { superuser: 'try' });
    //             // const logResult = await logState.promise();
    //             // output = logResult.stdout || "No previous run found or logs are unavailable.";
    //             // Fetch the most recent journal entry for the service
    //             const logCommand = ['journalctl', '-r', '-u', fullTaskName, '--no-pager', '--all', '-n', '1'];
    //             const logState = useSpawn(logCommand, { superuser: 'try' });
    //             const logResult = await logState.promise();

    //             // Extract the timestamp from the last log entry
    //             let output = logResult.stdout;
    //             let timestampRegex = /\w+\s+\d+\s+\d+:\d+:\d+/; // Regex to match date and time in logs (e.g., 'Oct 07 11:40:01')
    //             let timestampMatch = output.match(timestampRegex);
    //             let lastRunTime = timestampMatch ? timestampMatch[0] : "No recent run";

    //             // Return the last run time along with other details
    //             const latestEntry = new TaskExecutionResult(0, output, 'Run on '+lastRunTime, lastRunTime);
    //             return latestEntry;

    //         } else {
    //             const logCommand = ['journalctl', '-u', fullTaskName, '--since', startTime, '--no-pager', '--all'];
    //             const logState = useSpawn(logCommand, { superuser: 'try' });
    //             const logResult = await logState.promise();
    //             output = logResult.stdout;
    //             const latestEntry = new TaskExecutionResult(exitCode, output, startTime, finishTime);
    //             return latestEntry;
    //         }

    //     } catch (error) {
    //         console.error(errorString(error));
    //         return false;
    //     }
    // }


/*     async getLatestEntryFor(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;

        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}.service`;

        try {
            // Check systemd properties first
            const execCommand = ['systemctl', 'show', fullTaskName, '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp'];
            const execState = useSpawn(execCommand, { superuser: 'try' });
            const execResult = await execState.promise();

            const properties = Object.fromEntries(execResult.stdout.split('\n').filter(line => line.includes('=')).map(line => line.split('=')));
            const exitCode = properties['ExecMainStatus'] || '0';
            const startTime = properties['ExecMainStartTimestamp'] || '';
            const finishTime = properties['ExecMainExitTimestamp'] || '';

            let output = "";
            let lastRunTime = '';

            if (!startTime) {
                // Fetch the most recent journal entry for the service
                const logCommand = ['journalctl', '-r', '-u', fullTaskName, '--no-pager', '--all', '-n', '1'];
                const logState = useSpawn(logCommand, { superuser: 'try' });
                const logResult = await logState.promise();

                // Extract the timestamp from the last log entry
                let logOutput = logResult.stdout;
                let timestampRegex = /\w+\s+\d+\s+\d+:\d+:\d+/; // Regex to match date and time in logs (e.g., 'Oct 07 11:40:01')
                let timestampMatch = logOutput.match(timestampRegex);
                lastRunTime = timestampMatch ? timestampMatch[0] : "No recent run";

                // Parse and format the last run timestamp
                if (lastRunTime !== "No recent run") {
                    let parsedDate = new Date(lastRunTime);
                    lastRunTime = parsedDate.toLocaleString('en-US', {
                        weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
                        hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short'
                    });
                }

            } else {
                let parsedDate = new Date(startTime);
                lastRunTime = parsedDate.toLocaleString('en-US', {
                    weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short'
                });
            }

            // Return the last run time along with other details
            const latestEntry = new TaskExecutionResult(exitCode, output, lastRunTime, finishTime);
            return latestEntry;

        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }
 */


    async wasTaskRecentlyCompleted(taskInstance: TaskInstanceType): Promise<boolean> {
        const taskLog = new TaskExecutionLog([]);

        // Get the latest entry for the task
        const latestEntry = await taskLog.getLatestEntryFor(taskInstance);

        if (!latestEntry || !latestEntry.finishDate) {
            return false;  // No previous run or no finish date
        }

        const finishDate = new Date(latestEntry.finishDate).getTime();
        const currentTime = Date.now();

        // Define a threshold for "recently completed" (e.g., 10 minutes in milliseconds)
        const threshold = 10 * 60 * 1000;

        // Check if the task finished within the threshold
        return (currentTime - finishDate) <= threshold;
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