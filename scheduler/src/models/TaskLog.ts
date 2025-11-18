import { legacy } from '@45drives/houston-common-lib';
import { formatTemplateName } from '../composables/utility';

const { useSpawn, errorString } = legacy;

export class TaskExecutionLog {
    entries: TaskExecutionResult[];

    constructor(entries: TaskExecutionResult[]) {
        this.entries = entries;
    }

    /**
     * Get logs for a task.
     * - If untilTime is falsy: return ALL logs for this unit.
     * - If untilTime is truthy: return logs up to that time (used if you
     *   ever want "logs up to X" elsewhere).
     */
    async getEntriesFor(taskInstance, untilTime?: string) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;

        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}`;
        const serviceUnit = `${fullTaskName}.service`;

        try {
            // Show ALL logs for this unit by default
            if (!untilTime) {
                const logCommand = [
                    'journalctl',
                    '-u', serviceUnit,
                    '--no-pager',
                    '--all'
                ];
                const logState = useSpawn(logCommand, { superuser: 'try' });
                const logResult = await logState.promise();
                return (logResult.stdout || '').trim();
            }

            // Optional: logs up to a specific time if desired
            const command = [
                'journalctl',
                '-u', serviceUnit,
                '--until', untilTime,
                '--no-pager',
                '--all'
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

    /**
     * Get the execution result for the most recent run:
     * - exit code
     * - start/finish timestamps (pretty-printed)
     * - FULL log for that run (from Starting to Stopped/Failed).
     */
    async getLatestEntryFor(taskInstance) {
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const taskName = taskInstance.name;
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskName}`;
        const serviceUnit = `${fullTaskName}.service`;

        let exitCode = 0;
        let rawExit = '';
        let rawOutput = '';

        function prettyTimestamp(ts: string): string {
            if (!ts) return ts;

            const d = new Date(ts);
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

            return `${wd} ${y}-${m}-${dd} ${hh}:${mm}:${ss}${tz ? ' ' + tz : ''}`;
        }

        // 1) Ask systemd for exit code + exit timestamp
        try {
            const execCommand = [
                'systemctl', 'show',
                serviceUnit,
                '-p', 'ExecMainStatus,ExecMainExitTimestamp'
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
            rawExit = properties['ExecMainExitTimestamp'] || '';
        } catch (e) {
            console.warn('Failed to read ExecMainStatus for', serviceUnit, errorString(e));
        }

        // 2) Fetch the tail of the journal and slice out the last run
        let startIso = '';
        let endIso = '';

        try {
            // Grab a reasonable tail for this unit; enough to include several runs
            const logCommand = [
                'journalctl',
                '-u', serviceUnit,
                '-n', '500',
                '--no-pager',
                '--output', 'short-iso'
            ];
            const logState = useSpawn(logCommand, { superuser: 'try' });
            const logResult = await logState.promise();
            const allOutput = logResult.stdout || '';

            const allLines = allOutput
                .split('\n')
                .filter(line => line.trim() && !line.startsWith('-- Logs begin at'));

            if (allLines.length === 0) {
                // No logs at all
                return new TaskExecutionResult(
                    exitCode,
                    '',
                    '',
                    prettyTimestamp(rawExit || '')
                );
            }

            // Find the last "Starting/Started Service for <taskName>" line
            const startMarkers = [
                'Starting Service for ',
                'Started Service for '
            ];

            let startIndex = 0; // fall back to the beginning if we don't find a marker
            for (let i = allLines.length - 1; i >= 0; i--) {
                const line = allLines[i];
                if (
                    startMarkers.some(m => line.includes(m)) &&
                    line.includes(taskName)
                ) {
                    startIndex = i;
                    break;
                }
            }

            const lastRunLines = allLines.slice(startIndex);

            // Extract ISO-ish timestamps (journalctl short-iso: first token before space)
            const firstLine = lastRunLines[0];
            const lastLine = lastRunLines[lastRunLines.length - 1];

            const extractIso = (line: string) => {
                const spaceIdx = line.indexOf(' ');
                return spaceIdx > 0 ? line.slice(0, spaceIdx) : '';
            };

            startIso = extractIso(firstLine);
            endIso = extractIso(lastLine);

            rawOutput = lastRunLines.join('\n');
        } catch (e) {
            console.warn('Failed to read/slice journal for', serviceUnit, errorString(e));
        }

        const startTime = prettyTimestamp(startIso);
        const finishTime = prettyTimestamp(rawExit || endIso || startIso);

        return new TaskExecutionResult(exitCode, rawOutput, startTime, finishTime);
    }

    async wasTaskRecentlyCompleted(taskInstance: TaskInstanceType): Promise<boolean> {
        const taskLog = new TaskExecutionLog([]);

        const latestEntry = await taskLog.getLatestEntryFor(taskInstance);

        if (!latestEntry || !latestEntry.finishDate) {
            return false;
        }

        const finishDate = new Date(latestEntry.finishDate).getTime();
        const currentTime = Date.now();

        const threshold = 10 * 60 * 1000; // 10 minutes

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
