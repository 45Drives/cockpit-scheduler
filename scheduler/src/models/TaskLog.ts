import { legacy } from '@45drives/houston-common-lib';
import { formatTemplateName } from '../composables/utility';

const { useSpawn, errorString } = legacy;

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
        const serviceUnit = `${fullTaskName}.service`;   // <-- add this

        try {
            if (!untilTime) {
                // Show the last 200 lines for this unit by default
                const logCommand = [
                    'journalctl',
                    '-u', serviceUnit,
                    '--no-pager',
                    '--all',
                    '-n', '200'
                ];
                const logState = useSpawn(logCommand, { superuser: 'try' });
                const logResult = await logState.promise();
                return (logResult.stdout || '').trim();
            }

            const command = [
                'journalctl',
                '-u', serviceUnit,             // <-- use .service explicitly
                '--until', untilTime,
                '--no-pager', '--all'
            ];
            const state = useSpawn(command, { superuser: 'try' });
            const result = await state.promise();
            const taskLogData = result.stdout!.trim();
            return taskLogData;
        } catch (error) {
            console.error(errorString(error));
            return '';
        }
    }

    async getLatestEntryFor(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}`;
        const serviceUnit = `${fullTaskName}.service`;

        let exitCode = 0;
        let rawStart = '';
        let rawExit = '';
        let timestamp = '';
        let rawOutput = '';

        function prettyTimestamp(ts: string): string {
            if (!ts) return ts;

            const d = new Date(ts);
            // If the JS engine can't parse it, fall back to the original text
            if (isNaN(d.getTime())) return ts;

            const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;

            const fmt = new Intl.DateTimeFormat(undefined, {
                weekday: 'short',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false,
                timeZone: zone,
                timeZoneName: 'short',
            });

            const parts = fmt.formatToParts(d);
            const byType: Record<string, string> = {};
            for (const p of parts) {
                byType[p.type] = (byType[p.type] || '') + p.value;
            }

            const wd = (byType.weekday || '').replace(',', '');
            const y = byType.year || '';
            const m = byType.month || '';
            const dd = byType.day || '';
            const hh = byType.hour || '';
            const mm = byType.minute || '';
            const ss = byType.second || '';
            const tz = byType.timeZoneName || '';

            // e.g. "Mon 2025-11-17 11:45:31 AST"
            return `${wd} ${y}-${m}-${dd} ${hh}:${mm}:${ss}${tz ? ' ' + tz : ''}`;
        }

        // 1) Grab latest log line (for timestamp + raw output)
        try {
            const logCommand = [
                'journalctl',
                '-u', serviceUnit,
                '-n', '1',
                '--no-pager',
                '--output', 'short-iso'
            ];
            const logState = useSpawn(logCommand, { superuser: 'try' });
            const logResult = await logState.promise();
            rawOutput = logResult.stdout || '';

            const firstLine = rawOutput.split('\n').find(l => l.trim());
            if (firstLine) {
                const spaceIdx = firstLine.indexOf(' ');
                if (spaceIdx > 0) {
                    // e.g. "2025-11-17T10:49:34-0500"
                    timestamp = firstLine.slice(0, spaceIdx);
                }
            }
        } catch (e) {
            console.warn('Failed to read journal for', serviceUnit, errorString(e));
        }

        // 2) Ask systemd for ExecMain* timestamps
        try {
            const execCommand = [
                'systemctl', 'show',
                serviceUnit,
                '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp'
            ];
            const execState = useSpawn(execCommand, { superuser: 'try' });
            const execResult = await execState.promise();

            const properties = Object.fromEntries(
                (execResult.stdout || '')
                    .split('\n')
                    .filter(line => line.includes('='))
                    .map(line => {
                        const idx = line.indexOf('=');
                        return [line.slice(0, idx), line.slice(idx + 1)];
                    })
            );

            const rawStatus = properties['ExecMainStatus'] || '0';
            exitCode = parseInt(rawStatus, 10);

            rawStart = properties['ExecMainStartTimestamp'] || '';
            rawExit = properties['ExecMainExitTimestamp'] || '';
        } catch (e) {
            console.warn('Failed to read ExecMainStatus for', serviceUnit, errorString(e));
        }

        // Prefer systemd’s ExecMain*; if they’re empty (manual-only case),
        // fall back to the ISO timestamp, but pretty-print it.
        const startTime = prettyTimestamp(rawStart || timestamp || '');
        const finishTime = prettyTimestamp(rawExit || timestamp || '');

        const cleanedOutput = (rawOutput || '')
            .split('\n')
            .filter(line => !line.startsWith('-- Logs begin at'))
            .join('\n');

        return new TaskExecutionResult(exitCode, cleanedOutput, startTime, finishTime);
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
