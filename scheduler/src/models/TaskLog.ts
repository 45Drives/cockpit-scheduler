import { legacy } from '@45drives/houston-common-lib';
import { formatTemplateName } from '../composables/utility';
import { daemon } from '../utils/daemonClient';

const { useSpawn, errorString } = legacy;

export class TaskExecutionLog {
    entries: TaskExecutionResult[];

    constructor(entries: TaskExecutionResult[]) {
        this.entries = entries;
    }

    async fullUnitNameForLogs(ti: TaskInstanceType): Promise<string> {
        const templateName = formatTemplateName(ti.template.name);
        const base = `houston_scheduler_${templateName}_${ti.name}`;
        // Prefer explicit scope if you set it when loading tasks:
        const scope = (ti as any).scope as ('user' | 'system' | undefined);

        if (scope === 'user') {
            const cockpitUser = await (window as any).cockpit.user();
            const uid: number = cockpitUser?.id;
            return `${base}_u${uid}`;
        }
        return base; // legacy/system
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
            const taskLogData = result.stdout!.trim();
            // console.log('taskLogData:', taskLogData);

            return taskLogData;
        } catch (error) {
            console.error(errorString(error));
            return '';
        }
    }

    async getLatestEntryFor(taskInstance: TaskInstanceType) {
        try {
            const unit = await this.fullUnitNameForLogs(taskInstance);
            const isUserScope = (taskInstance as any).scope === 'user';

            // --- DAEMON path (user units): avoid journalctl; parse show()
            if (isUserScope) {
                const templateName = formatTemplateName(taskInstance.template.name);
                const st: any = await daemon.getStatus(templateName, taskInstance.name);
                const show = String(st?.service || '');

                // Pull a few properties we asked the daemon to include
                const props = new Map(
                    (show || '').split(/\r?\n/).map((line) => {
                        const i = line.indexOf('=');
                        return i > 0 ? [line.slice(0, i), line.slice(i + 1)] : [line, ''];
                    })
                );
                const rawResult = (props.get('Result') || '').toString().toLowerCase();
                // Map success → 0, anything else → 1 (no ExecMainStatus available here)
                const exitCode = (rawResult === 'success') ? 0 : 1;
                const startTime = props.get('ActiveEnterTimestamp') || '';
                const finishTime = '';
                const output = '';
                return new TaskExecutionResult(exitCode, output, startTime, finishTime);
            }

            // --- LEGACY path (system units)
            const showCmd = ['systemctl', 'show', `${unit}.service`,
                '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp',
                '--no-pager'];
            const showState = useSpawn(showCmd, { superuser: 'try' });
            const showRes: any = await showState.promise();
            const kv = Object.fromEntries(
                (showRes.stdout || '')
                    .split('\n')
                    .filter((l: string) => l.includes('='))
                    .map((l: string) => l.split('=', 2))
            );

            const rawStatus = kv['ExecMainStatus'];
            const exitCode = Number.isFinite(Number(rawStatus)) ? Number(rawStatus) : 0;

            const startTime = kv['ExecMainStartTimestamp'] || '';
            const finishTime = kv['ExecMainExitTimestamp'] || '';

            let output = '';
            if (startTime) {
                const logCmd = [
                    'journalctl', '-q', '--output=cat',
                    '-u', `${unit}.service`,
                    '--since', startTime,
                    '--no-pager', '--all'
                ];
                try {
                    const logState = useSpawn(logCmd, { superuser: 'try' });
                    const logRes: any = await logState.promise();
                    output = (logRes.stdout || '').replace(/^-- Logs begin at.*\n?/m, '');
                } catch (e) {
                    // Don’t spam; lack of journal perms is normal on some setups
                    const msg = errorString(e);
                    if (!/No journal files were opened|not seeing messages/i.test(msg)) {
                        console.warn('journalctl failed:', msg);
                    }
                }
            }

            return new TaskExecutionResult(exitCode, output, startTime, finishTime);
        } catch (e) {
            // Only warn on truly unexpected failures
            console.warn('getLatestEntryFor failed:', errorString(e));
            return false;
        }
    }

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
