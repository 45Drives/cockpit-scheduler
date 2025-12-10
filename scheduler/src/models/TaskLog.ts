import { server, unwrap, Command } from '@45drives/houston-common-lib';
import { formatTemplateName } from '../composables/utility';
import { daemon } from '../utils/daemonClient';

const textDecoder = new TextDecoder('utf-8');

async function runCommand(
    argv: string[],
    opts: { superuser?: 'try' | 'require' } = { superuser: 'try' }
): Promise<{ stdout: string; stderr: string; exitStatus: number }> {
    const proc = await unwrap(
        server.execute(new Command(argv, opts))
    );

    const rawStdout: any = proc.stdout;
    const rawStderr: any = proc.stderr;

    const stdout =
        rawStdout instanceof Uint8Array
            ? textDecoder.decode(rawStdout)
            : String(rawStdout ?? '');

    const stderr =
        rawStderr instanceof Uint8Array
            ? textDecoder.decode(rawStderr)
            : String(rawStderr ?? '');

    return { stdout, stderr, exitStatus: proc.exitStatus };
}

const errorString = (e: any) => e?.message ?? String(e);

export class TaskExecutionLog {
    entries: TaskExecutionResult[];

    constructor(entries: TaskExecutionResult[]) {
        this.entries = entries;
    }

    async fullUnitNameForLogs(ti: TaskInstanceType): Promise<string> {
        const templateName = formatTemplateName(ti.template.name);
        const base = `houston_scheduler_${templateName}_${ti.name}`;
        const scope = (ti as any).scope as ('user' | 'system' | undefined);

        if (scope === 'user') {
            const cockpitUser = await (window as any).cockpit.user();
            const uid: number = cockpitUser?.id;
            return `${base}_u${uid}`;
        }
        return base; // legacy/system
    }

    /**
     * Get logs for a task.
     * - If untilTime is falsy: return ALL logs for this unit.
     * - If untilTime is truthy: return logs up to that time
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
                const { stdout } = await runCommand(logCommand, { superuser: 'try' });
                return (stdout || '').trim();
            }

            // Optional: logs up to a specific time if desired
            const command = [
                'journalctl',
                '-u', serviceUnit,
                '--until', untilTime,
                '--no-pager',
                '--all'
            ];
            const { stdout } = await runCommand(command, { superuser: 'try' });
            const taskLogData = (stdout || '').trim();
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

                const props = new Map(
                    (show || '').split(/\r?\n/).map((line) => {
                        const i = line.indexOf('=');
                        return i > 0 ? [line.slice(0, i), line.slice(i + 1)] : [line, ''];
                    })
                );
                const rawResult = (props.get('Result') || '').toString().toLowerCase();
                const exitCode = (rawResult === 'success') ? 0 : 1;

                const startTime = props.get('ActiveEnterTimestamp') || '';
                const finishTime =
                    props.get('InactiveEnterTimestamp') ||
                    props.get('ExecMainExitTimestamp') ||
                    '';

                const output = '';
                return new TaskExecutionResult(exitCode, output, startTime, finishTime);
            }

            // --- LEGACY path (system units)
            const showCmd = [
                'systemctl', 'show', `${unit}.service`,
                '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp,ActiveEnterTimestamp,InactiveEnterTimestamp',
                '--no-pager',
            ];
            const showRes = await runCommand(showCmd, { superuser: 'try' });
            const kv = Object.fromEntries(
                (showRes.stdout || '')
                    .split('\n')
                    .filter((l: string) => l.includes('='))
                    .map((l: string) => l.split('=', 2))
            );

            const rawStatus = kv['ExecMainStatus'];
            const exitCode = Number.isFinite(Number(rawStatus)) ? Number(rawStatus) : 0;

            const startTime =
                kv['ExecMainStartTimestamp'] ||
                kv['ActiveEnterTimestamp'] ||
                '';

            const finishTime =
                kv['ExecMainExitTimestamp'] ||
                kv['InactiveEnterTimestamp'] ||
                '';

            let output = '';
            const baseLogCmd = [
                'journalctl', '-q', '--output=cat',
                '-u', `${unit}.service`,
                '--no-pager', '--all',
            ];

            if (startTime) {
                const logCmd = [...baseLogCmd, '--since', startTime];
                try {
                    const logRes = await runCommand(logCmd, { superuser: 'try' });
                    output = (logRes.stdout || '').replace(/^-- Logs begin at.*\n?/m, '');
                } catch (e) {
                    const msg = errorString(e);
                    if (!/No journal files were opened|not seeing messages/i.test(msg)) {
                        console.warn('journalctl (since) failed:', msg);
                    }
                }
            }

            // Fallback: if we still have nothing, just grab the last 200 lines
            if (!output) {
                try {
                    const fallbackCmd = [...baseLogCmd, '-n', '200'];
                    const logRes = await runCommand(fallbackCmd, { superuser: 'try' });
                    output = (logRes.stdout || '').replace(/^-- Logs begin at.*\n?/m, '');
                } catch (e) {
                    const msg = errorString(e);
                    if (!/No journal files were opened|not seeing messages/i.test(msg)) {
                        console.warn('journalctl (fallback) failed:', msg);
                    }
                }
            }

            return new TaskExecutionResult(exitCode, output, startTime, finishTime);
        } catch (e) {
            console.warn('getLatestEntryFor failed:', errorString(e));
            return false;
        }
    }

    async wasTaskRecentlyCompleted(taskInstance: TaskInstanceType): Promise<boolean> {
        const latestEntry = await this.getLatestEntryFor(taskInstance);

        if (!latestEntry) {
            return false;
        }

        if (typeof latestEntry.exitCode === 'number' && latestEntry.exitCode !== 0) {
            return false;
        }

        // If we can't get a timestamp, but the exit code was 0, treat it as completed.
        const tsSource = latestEntry.finishDate || latestEntry.startDate;
        if (!tsSource) {
            return true;
        }

        const finishDate = new Date(tsSource).getTime();
        if (!Number.isFinite(finishDate)) {
            return true;
        }

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
