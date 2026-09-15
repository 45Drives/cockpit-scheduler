import { formatTemplateName } from '../composables/utility';
import { daemon } from '../utils/daemonClient';
import { execCommand } from '../utils/commandGate';

async function runCommand(
    argv: string[],
    opts: { superuser?: 'try' | 'require' } = { superuser: 'try' },
    failIfNonZero = true
): Promise<{ stdout: string; stderr: string; exitStatus: number }> {
    const { stdout, stderr, exitStatus } = await execCommand(argv, opts, failIfNonZero);
    return { stdout, stderr, exitStatus };
}

const errorString = (e: any) => e?.message ?? String(e);

function trimToLatestRunBlock(output: string): string {
    const text = (output || '').replace(/^-- Logs begin at.*\n?/m, '');
    if (!text) return '';

    const lines = text.split('\n');
    let startIdx = -1;
    for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i] || '';
        if (line.includes('Starting Service for ')) {
            startIdx = i;
            break;
        }
    }

    if (startIdx < 0) {
        return text;
    }

    return lines.slice(startIdx).join('\n');
}

/**
 * Maps formatted template names to the debug log file written by each script.
 * These are the /tmp/ logs that always exist even when the journal is empty.
 */
const DEBUG_LOG_MAP: Record<string, string> = {
    ZfsReplicationTask: '/tmp/zfs_rep_debug.log',
    AutomatedSnapshotTask: '/tmp/autosnap_debug.log',
    RsyncTask: '/tmp/rsync_task_debug.log',
    CloudSyncTask: '/tmp/cloudsync_debug.log',
    ScrubTask: '/tmp/scrub_debug.log',
    SmartTest: '/tmp/smart_test_debug.log',
    CustomTask: '/tmp/custom_task_debug.log',
};

/**
 * Scripts write per-task logs as <base>_<taskName>.log and fall back to
 * <base>.log when taskName is unset, so probe both.
 */
function debugLogCandidates(basePath: string, taskName: string): string[] {
    const base = basePath.replace(/\.log$/, '');
    return taskName ? [`${base}_${taskName}.log`, basePath] : [basePath];
}

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

    /**
     * `systemctl show` output the status poller already fetched this tick.
     * Static because the poller, the view and getDisplayMeta each hold their own
     * TaskExecutionLog, so a per-instance cache would never be read back.
     */
    private static primedServiceShow = new Map<string, { at: number; kv: Record<string, string> }>();
    private static readonly PRIME_TTL_MS = 2000;

    /** Which debug-log candidate actually exists, so polling stops re-probing the other. */
    private static debugLogPath = new Map<string, string>();

    private static parseShowKv(stdout: string): Record<string, string> {
        return Object.fromEntries(
            (stdout || '')
                .split('\n')
                .filter((l: string) => l.includes('='))
                .map((l: string) => l.split('=', 2))
        );
    }

    primeServiceShow(unit: string, stdout: string): void {
        const now = Date.now();
        const cache = TaskExecutionLog.primedServiceShow;
        for (const [key, val] of cache) {
            if (now - val.at >= TaskExecutionLog.PRIME_TTL_MS) cache.delete(key);
        }
        cache.set(unit, { at: now, kv: TaskExecutionLog.parseShowKv(stdout) });
    }

    /**
     * Run-state metadata only (exit code + timestamps). Costs one `systemctl
     * show` and never touches journalctl, so it is safe to call on a poll
     * interval for every visible task.
     */
    private async fetchRunMeta(taskInstance: TaskInstanceType): Promise<{
        unit: string;
        exitCode: number;
        startTime: string;
        finishTime: string;
        invocationId: string;
        journalAvailable: boolean;
    }> {
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

            return {
                unit,
                exitCode: rawResult === 'success' ? 0 : 1,
                startTime: props.get('ActiveEnterTimestamp') || '',
                finishTime:
                    props.get('InactiveEnterTimestamp') ||
                    props.get('ExecMainExitTimestamp') ||
                    '',
                invocationId: '',
                journalAvailable: false,
            };
        }

        // --- LEGACY path (system units)
        const primed = TaskExecutionLog.primedServiceShow.get(unit);
        let kv: Record<string, string>;

        if (primed && Date.now() - primed.at < TaskExecutionLog.PRIME_TTL_MS && primed.kv['ExecMainStatus'] !== undefined) {
            kv = primed.kv;
        } else {
            const showCmd = [
                'systemctl', 'show', `${unit}.service`,
                '-p', 'ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp,ActiveEnterTimestamp,InactiveEnterTimestamp,InvocationID',
                '--no-pager',
            ];
            const showRes = await runCommand(showCmd, { superuser: 'try' });
            kv = TaskExecutionLog.parseShowKv(showRes.stdout);
        }

        const rawStatus = kv['ExecMainStatus'];

        return {
            unit,
            exitCode: Number.isFinite(Number(rawStatus)) ? Number(rawStatus) : 0,
            startTime: kv['ExecMainStartTimestamp'] || kv['ActiveEnterTimestamp'] || '',
            finishTime: kv['ExecMainExitTimestamp'] || kv['InactiveEnterTimestamp'] || '',
            invocationId: (kv['InvocationID'] || '').trim(),
            journalAvailable: true,
        };
    }

    /**
     * Cheap variant of {@link getLatestEntryFor} for status polling: exit code
     * and timestamps without the journal body.
     */
    async getLatestStatusFor(taskInstance: TaskInstanceType): Promise<TaskExecutionResult | false> {
        try {
            const meta = await this.fetchRunMeta(taskInstance);
            return new TaskExecutionResult(meta.exitCode, '', meta.startTime, meta.finishTime);
        } catch (e) {
            console.warn('getLatestStatusFor failed:', errorString(e));
            return false;
        }
    }

    async getLatestEntryFor(taskInstance: TaskInstanceType) {
        try {
            const { unit, exitCode, startTime, finishTime, invocationId, journalAvailable } =
                await this.fetchRunMeta(taskInstance);

            if (!journalAvailable) {
                return new TaskExecutionResult(exitCode, '', startTime, finishTime);
            }

            let output = '';
            const baseLogCmd = [
                'journalctl', '-q', '--output=cat',
                '-u', `${unit}.service`,
                '--no-pager', '--all',
            ];

            // Ordered cheapest-correct first: the --since query is what the log
            // viewer has always displayed, so it stays the primary source and
            // the invocation query only runs when it produces nothing.
            if (startTime) {
                const logCmd = [...baseLogCmd, '--since', startTime];
                try {
                    const logRes = await runCommand(logCmd, { superuser: 'try' });
                    output = trimToLatestRunBlock(logRes.stdout || '');
                } catch (e) {
                    const msg = errorString(e);
                    if (!/No journal files were opened|not seeing messages/i.test(msg)) {
                        console.warn('journalctl (since) failed:', msg);
                    }
                }
            }

            if (invocationId && !output) {
                try {
                    const byInvocationCmd = ['journalctl', '-q', '--output=cat', '--no-pager', '--all', `_SYSTEMD_INVOCATION_ID=${invocationId}`];
                    const logRes = await runCommand(byInvocationCmd, { superuser: 'try' });
                    output = (logRes.stdout || '').replace(/^-- Logs begin at.*\n?/m, '');
                } catch (e) {
                    const msg = errorString(e);
                    if (!/No journal files were opened|not seeing messages/i.test(msg)) {
                        console.warn('journalctl (invocation) failed:', msg);
                    }
                }
            }

            // Fallback: if we still have nothing, just grab the last 200 lines
            if (!output) {
                try {
                    const fallbackCmd = [...baseLogCmd, '-n', '200'];
                    const logRes = await runCommand(fallbackCmd, { superuser: 'try' });
                    output = trimToLatestRunBlock(logRes.stdout || '');
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

    /**
     * Read the /tmp/ debug log for a task's template.
     * Returns the last `lines` lines, or an empty string if unavailable.
     */
    async getDebugLog(taskInstance: TaskInstanceType, lines = 200): Promise<string> {
        const templateName = formatTemplateName(taskInstance.template.name);
        const logPath = DEBUG_LOG_MAP[templateName];
        if (!logPath) {
            return `No debug log path configured for template "${templateName}".`;
        }
        const candidates = debugLogCandidates(logPath, taskInstance.name);
        const cacheKey = `${logPath}|${taskInstance.name}`;
        const known = TaskExecutionLog.debugLogPath.get(cacheKey);
        for (const path of known ? [known] : candidates) {
            // A missing candidate is normal, so don't let it surface as an error.
            const { stdout, exitStatus } = await runCommand(
                ['tail', '-n', String(lines), path],
                { superuser: 'try' },
                false,
            );
            if (exitStatus !== 0) continue;
            const content = (stdout || '').trim();
            if (content) {
                TaskExecutionLog.debugLogPath.set(cacheKey, path);
                return content;
            }
        }
        TaskExecutionLog.debugLogPath.delete(cacheKey);
        return `(no debug log content found at ${candidates.join(' or ')})`;
    }

    async wasTaskRecentlyCompleted(taskInstance: TaskInstanceType): Promise<boolean> {
        // Status-only probe: this runs on every poll tick, so it must not pull
        // the journal body.
        const latestEntry = await this.getLatestStatusFor(taskInstance);

        if (!latestEntry) return false;

        if (typeof latestEntry.exitCode === 'number' && latestEntry.exitCode !== 0) {
            return false;
        }

        // Require at least *some* timestamp to consider it a real run
        const tsSource = latestEntry.finishDate || latestEntry.startDate;
        if (!tsSource) {
            return false;
        }

        const finishDate = new Date(tsSource).getTime();
        if (!Number.isFinite(finishDate)) {
            return false;
        }

        const currentTime = Date.now();
        const threshold = 10 * 60 * 1000; // 10 minutes

        return (currentTime - finishDate) <= threshold;
    }

    /**
     * Clear journal logs for a specific task's service unit.
     * Uses journalctl --rotate + --vacuum-time to clear, then verifies.
     * Note: journalctl vacuum is system-wide but we rotate first so the
     * per-unit logs are flushed to separate journal files.
     */
    async clearLogsForTask(taskInstance: TaskInstanceType): Promise<{ success: boolean; message: string }> {
        const templateName = formatTemplateName(taskInstance.template.name);
        const serviceUnit = `houston_scheduler_${templateName}_${taskInstance.name}.service`;

        try {
            // Rotate current journal so entries are flushed
            await runCommand(['journalctl', '--rotate'], { superuser: 'try' });

            // Vacuum this unit's logs specifically (journalctl doesn't support per-unit vacuum,
            // so we just rotate and clear the debug log)
            const debugLogPath = DEBUG_LOG_MAP[templateName];
            if (debugLogPath) {
                for (const path of debugLogCandidates(debugLogPath, taskInstance.name)) {
                    await runCommand(['truncate', '-s', '0', path], { superuser: 'try' }).catch(() => {});
                }
            }

            return { success: true, message: `Cleared debug log for ${taskInstance.name}. Journal entries remain in system journal.` };
        } catch (e) {
            return { success: false, message: errorString(e) };
        }
    }

    /**
     * Vacuum ALL houston_scheduler journal logs older than the specified number of days.
     */
    async vacuumAllSchedulerLogs(retentionDays: number = 0): Promise<{ success: boolean; message: string }> {
        try {
            await runCommand(['journalctl', '--rotate'], { superuser: 'try' });

            if (retentionDays > 0) {
                await runCommand(
                    ['journalctl', '--vacuum-time', `${retentionDays}d`],
                    { superuser: 'try' }
                );
                return { success: true, message: `Vacuumed system journal entries older than ${retentionDays} day(s).` };
            } else {
                // Clear all scheduler debug logs
                for (const logPath of Object.values(DEBUG_LOG_MAP)) {
                    await runCommand(['truncate', '-s', '0', logPath], { superuser: 'try' }).catch(() => {});
                }
                return { success: true, message: 'Cleared all scheduler debug logs.' };
            }
        } catch (e) {
            return { success: false, message: errorString(e) };
        }
    }

}

export class TaskExecutionResult {
    exitCode: number;
    output: string;
    startDate: string | number;
    finishDate: string | number;

    constructor(exitCode: number, output: string, startDate: string | number, finishDate: string | number) {
        this.exitCode = exitCode;
        this.output = output;
        this.startDate = startDate;
        this.finishDate = finishDate;
    }
}
