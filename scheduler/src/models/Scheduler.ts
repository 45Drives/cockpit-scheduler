import { server, unwrap, Command, File } from "@45drives/houston-common-lib"
import { TaskInstance, TaskTemplate, TaskSchedule, ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskScheduleInterval, RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate, CloudSyncTaskTemplate, CustomTaskTemplate } from './Tasks';
import { ParameterNode, StringParameter, SelectionParameter, IntParameter, BoolParameter, ObjectParameter } from './Parameters';
import { createStandaloneTask, createTaskFiles, createScheduleForTask, removeTask, runTask, formatTemplateName, stopTask } from '../composables/utility';
import { TaskExecutionLog, TaskExecutionResult } from './TaskLog';
// commenting out chooseBackend until daemon mode is airtight
// import { chooseBackend } from '../utils/bootstrapBackend';
import { daemon } from '../utils/daemonClient';
// @ts-ignore
import get_tasks_script from '../scripts/get-task-instances.py?raw';

const textDecoder = new TextDecoder("utf-8");

const errorString = (e: any) => e?.message ?? String(e);

export async function runCommand(
    argv: string[],
    opts: { superuser?: "try" | "require" } = { superuser: "try" }
): Promise<{ stdout: string; stderr: string; exitStatus: number }> {
    const proc = await unwrap(
        server.execute(new Command(argv, opts))
    );

    const rawStdout: any = proc.stdout;
    const rawStderr: any = proc.stderr;

    const stdout =
        rawStdout instanceof Uint8Array
            ? textDecoder.decode(rawStdout)
            : String(rawStdout ?? "");

    let stderr: string;
    if (typeof rawStderr === "string") {
        stderr = rawStderr;
    } else if (rawStderr instanceof Uint8Array) {
        stderr = textDecoder.decode(rawStderr);
    } else {
        stderr = "";
    }

    return { stdout, stderr, exitStatus: proc.exitStatus };
}

export class Scheduler implements SchedulerType {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }

    private backend: 'daemon' | 'legacy' = 'legacy';
    private backendInitialized = false;

    async init() {
        if (this.backendInitialized) return;
        // const picked = await chooseBackend();
        // this.backend = picked.backend;

        // Force legacy backend for this build
        this.backend = 'legacy';
        this.backendInitialized = true;
    }

    private async ensureBackend() {
        if (!this.backendInitialized) {
            try {
                await this.init();
            } catch (e) {
                console.warn('ensureBackend: falling back to legacy:', e);
                this.backend = 'legacy';
                this.backendInitialized = true;
            }
        }
    }

    private statusCache = new Map<string, { ts: number; st: any }>();

    private async fetchStatus(ti: TaskInstanceType): Promise<any> {
        const tplKey = this.templateKey(ti, this.normalizeTemplateKey(ti.template.name));
        const key = `${tplKey}:${ti.name}`;
        const now = Date.now();

        const hit = this.statusCache.get(key);
        if (hit && now - hit.ts < 1000) { // 1 second TTL is plenty for UI polling
            return hit.st;
        }

        const st = await daemon.getStatus(tplKey, ti.name);
        this.statusCache.set(key, { ts: now, st });
        return st;
    }


    // === Helpers for daemon branch ===
    private async readTextRoot(path: string): Promise<string> {
        const file = new File(server, path);
        const content = await unwrap(file.read({ superuser: "try" }));
        return content ?? "";
    }

    private isDaemon(): boolean {
        // return this.backend === 'daemon';
        return false;
    }


    private templateKey(ti: TaskInstanceType, hint?: string): string {
        return (ti as any)._templateKey
            || (hint ? this.normalizeTemplateKey(hint) : '')
            || this.normalizeTemplateKey(ti.template.name);
    }

    // single source of truth for unit names
    private async unitNameFor(ti: TaskInstanceType): Promise<string> {
        const key = this.templateKey(ti);
        const scope = (ti as any).scope as ('user' | 'system' | undefined);

        // system/legacy never has _u<uid>, and legacy backend always behaves like "system"
        if (scope === 'system' || !this.isDaemon()) {
            return `houston_scheduler_${key}_${ti.name}`;
        }

        const uid: number = (await (window as any).cockpit.user())?.id;
        return `houston_scheduler_${key}_${ti.name}_u${uid}`;
    }

    private async unitNameFromParts(templateKey: string, taskName: string, scope: 'user' | 'system') {
        if (scope === 'system' || !this.isDaemon())
            return `houston_scheduler_${templateKey}_${taskName}`;
        const uid: number = (await (window as any).cockpit.user())?.id;
        return `houston_scheduler_${templateKey}_${taskName}_u${uid}`;
    }

    private usToMs(us: number): number | 0 {
        return us && Number.isFinite(us) ? Math.floor(us / 1000) : 0;
    }

    private parseListTasks(raw: any): any[] {
        try {
            if (Array.isArray(raw)) {
                if (raw.length === 1 && typeof raw[0] === 'string') {
                    return JSON.parse(raw[0] || '[]');
                }
                return raw;
            }
            const s = typeof raw === 'string' ? raw :
                (raw && typeof raw === 'object' && typeof (raw as any).value === 'string') ? (raw as any).value :
                    (raw && typeof raw.toString === 'function') ? raw.toString() : '';
            return JSON.parse(s || '[]');
        } catch (e) {
            console.warn('ListTasks parse failed:', e, raw);
            return [];
        }
    }

 /*
  * Unified, view-friendly status + timestamps
  * - statusText: (“Active (Pending)”, etc.)
  * - lastRunMs: Date.now()-compatible ms (picked from timer/service)
  * - nextRunMs: optional ms for “Next run” 
  */
    async getDisplayMeta(ti: TaskInstanceType): Promise<{
        unit: string;
        statusText: string;
        lastRunMs: number;       // 0 if unknown
        nextRunMs?: number;      // 0/undefined if unknown
    }> {
        await this.ensureBackend();

        const log = new TaskExecutionLog([]);
        const tplKey = this.templateKey(ti, this.normalizeTemplateKey(ti.template.name));
        const unit = await this.unitNameFor(ti);

        let timerOut = '', serviceOut = '';
        const preferTimer = !!ti?.schedule?.enabled;

        // Helper: choose which blob to feed into parseTaskStatus
        const pickStatusSource = (t: ReturnType<Scheduler['parseShow']>, s: ReturnType<Scheduler['parseShow']>) => {
            // If the service is clearly running or failed, always show that
            if (s.active === 'active' && s.sub === 'running') return serviceOut;
            if (s.active === 'failed' || s.sub === 'failed') return serviceOut;

            // Otherwise, default: timer for scheduled tasks, service for unscheduled
            return preferTimer ? timerOut : serviceOut;
        };

        if (this.isDaemon()) {
            try {
                const st: any = await this.fetchStatus(ti);
                // daemon returns .unit, .timer, .service
                const u = String(st?.unit || unit);
                timerOut = String(st?.timer || '');
                serviceOut = String(st?.service || '');

                const t = this.parseShow(timerOut);
                const s = this.parseShow(serviceOut);

                const source = pickStatusSource(t, s);
                const statusText = await this.parseTaskStatus(source, u, log, ti);

                const lastRunUs = t.lastTriggerUSec || s.serviceExitUSec || s.serviceStartUSec || 0;
                const nextRunUs = t.nextElapseUSec || 0;

                return {
                    unit: u,
                    statusText: String(statusText || '—'),
                    lastRunMs: this.usToMs(Number(lastRunUs)),
                    nextRunMs: this.usToMs(Number(nextRunUs)),
                };
            } catch {
                // fall back to legacy path below
            }
        }

        // Legacy/direct path: query timer (optional) and service (required)
        try {
            // Timer is optional for manual-only tasks
            try {
                const { stdout, stderr, exitStatus } = await runCommand(
                    [
                        'systemctl', 'show', `${unit}.timer`, '--no-pager',
                        '--property', 'LoadState,ActiveState,SubState,Result,LastTriggerUSec,NextElapseUSecRealtime,MergedUnit',
                    ],
                    { superuser: 'try' }
                );

                if (exitStatus === 0) {
                    timerOut = stdout;
                } else if (!/not found/i.test(stdout) && !/not found/i.test(stderr)) {
                    console.warn(`getDisplayMeta(timer ${unit}):`, stderr || stdout);
                }
            } catch (e) {
                console.warn(`getDisplayMeta(timer ${unit}) error:`, errorString(e));
            }

            // Service is required
            const { stdout, stderr, exitStatus } = await runCommand(
                [
                    'systemctl', 'show', `${unit}.service`, '--no-pager',
                    '--property', 'LoadState,ActiveState,SubState,Result,ActiveEnterTimestampUSec,ActiveEnterTimestamp,ExecMainStartTimestampUSec,ExecMainStartTimestamp,ExecMainExitTimestampUSec,ExecMainExitTimestamp,InactiveEnterTimestampUSec,InactiveEnterTimestamp,MergedUnit',
                ],
                { superuser: 'try' }
            );

            if (exitStatus !== 0) {
                throw new Error(stderr || stdout || `systemctl show ${unit}.service failed with ${exitStatus}`);
            }

            serviceOut = stdout;

            const t = this.parseShow(timerOut);
            const s = this.parseShow(serviceOut);

            const source = pickStatusSource(t, s);
            const statusText = await this.parseTaskStatus(source, unit, log, ti);

            const lastRunUs = t.lastTriggerUSec || s.serviceExitUSec || s.serviceStartUSec || 0;
            const nextRunUs = t.nextElapseUSec || 0;

            return {
                unit,
                statusText: String(statusText || '—'),
                lastRunMs: this.usToMs(Number(lastRunUs)),
                nextRunMs: this.usToMs(nextRunUs),
            };
        } catch (e) {
            console.warn(`getDisplayMeta(service ${unit}) failed:`, errorString(e));
            return { unit, statusText: '—', lastRunMs: 0 };
        }
    }

    formatLocal(ms?: number): string {
        if (!ms) return '—';
        const d = new Date(ms);

        // Weekday (short) in current locale
        const weekday = new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(d);

        // Get a real tz abbreviation (ADT/EDT/etc), falling back from long name
        const tzShort = (() => {
            // Try Intl short first (force en-US to improve chances of getting an acronym)
            const parts = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' }).formatToParts(d);
            let v = parts.find(p => p.type === 'timeZoneName')?.value ?? '';

            // Fallback if it's just "GMT-3" or empty: build acronym from "(Atlantic Daylight Time)"
            if (/^GMT[+-]/i.test(v) || v === '') {
                const m = d.toString().match(/\(([^)]+)\)$/); // "... (Atlantic Daylight Time)"
                if (m && m[1]) {
                    const abbr = m[1].split(/\s+/).map(w => w[0]).join('');
                    if (abbr && abbr.length <= 5) v = abbr; // ADT, EDT, AST, PST, etc.
                }
            }
            return v;
        })();

        const y = d.getFullYear();
        const mo = String(d.getMonth() + 1).padStart(2, '0');
        const da = String(d.getDate()).padStart(2, '0');
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        const ss = String(d.getSeconds()).padStart(2, '0');

        return `${weekday} ${y}-${mo}-${da} ${hh}:${mm}:${ss}${tzShort ? ' ' + tzShort : ''}`;
    }

    private normalizeTemplateKey(x: any): string {
        const s = String(x ?? '').trim();
        if (!s) return s;
        // accept exact matches
        const known = new Set([
            'ZfsReplicationTask',
            'AutomatedSnapshotTask',
            'RsyncTask',
            'ScrubTask',
            'SmartTest',
            'CloudSyncTask',
            'CustomTask',
        ]);
        if (known.has(s)) return s;

        // tolerate case/underscore/space variations
        const key = s.replace(/[\s_-]+/g, '').toLowerCase();
        const map: Record<string, string> = {
            zfsreplicationtask: 'ZfsReplicationTask',
            automatedsnapshottask: 'AutomatedSnapshotTask',
            rsynctask: 'RsyncTask',
            scrubtask: 'ScrubTask',
            smarttest: 'SmartTest',
            cloudsynctask: 'CloudSyncTask',
            customtask: 'CustomTask',
        };
        return map[key] ?? s;
    }

    private resolveTemplate(templateName: string) {
        switch (templateName) {
            case 'ZfsReplicationTask': return new ZFSReplicationTaskTemplate();
            case 'AutomatedSnapshotTask': return new AutomatedSnapshotTaskTemplate();
            case 'RsyncTask': return new RsyncTaskTemplate();
            case 'ScrubTask': return new ScrubTaskTemplate();
            case 'SmartTest': return new SmartTestTemplate();
            case 'CloudSyncTask': return new CloudSyncTaskTemplate();
            case 'CustomTask': return new CustomTaskTemplate();
            default: throw new Error(`Unknown template: ${templateName}`);
        }
    }

    private toPlain<T>(x: T): T {
        return JSON.parse(JSON.stringify(x));
    }

    private async isAdminUser(): Promise<boolean> {
        const u = await (window as any).cockpit.user();
        return u?.id === 0 || (u?.groups || []).some((g: string) => g === 'wheel' || g === 'sudo' || g === 'admin' || g === 'adm');
    }


    private setScope(inst: TaskInstance, scope: 'user' | 'system') {
        (inst as any).scope = scope; // typed thanks to augmentation, harmless otherwise
    }

    private safeBuildParamNode(schema: ParameterNode, params: Record<string, any>): ParameterNode {
        try {
            return this.createParameterNodeFromSchema(schema, params);
        } catch (e) {
            console.warn('Parameter schema hydration failed, falling back to loose node:', e);
            return this.createLooseNodeFromFlatParams(params);
        }
    }

    private createLooseNodeFromFlatParams(params: Record<string, any>): ParameterNode {
        const root = new ParameterNode('Parameters', 'root');
        const boolRe = /^(true|false)$/i;
        for (const [k, v] of Object.entries(params)) {
            const s = String(v ?? '');
            if (boolRe.test(s)) {
                const p = new BoolParameter(k, k);
                p.value = /^true$/i.test(s);
                root.addChild(p);
            } else if (/^-?\d+$/.test(s)) {
                const p = new IntParameter(k, k);
                p.value = parseInt(s, 10);
                root.addChild(p);
            } else {
                const p = new StringParameter(k, k);
                p.value = s;
                root.addChild(p);
            }
        }
        return root;
    }

    private async desiredScopeFor(inst: TaskInstanceType, forCreate = false): Promise<'user' | 'system' | 'auto'> {
        const explicit = (inst as any).scope;
        if (explicit === 'user' || explicit === 'system') return explicit;

        // For creates (no prior unit), be conservative
        if (forCreate) return (await this.isAdminUser()) ? 'auto' : 'user';

        // For updates, try to detect current scope via daemon
        try {
            const st: any = await daemon.getStatus(this.normalizeTemplateKey(inst.template.name), inst.name);
            const s = String(st?.scope || '');
            if (s === 'user' || s === 'system') return s as any;
        } catch {
            /* ignore */
        }
        return (await this.isAdminUser()) ? 'auto' : 'user';
    }


    // One canonical root (as requested)
    // private static readonly STATE_ROOT = '/var/lib/45drives/houston/scheduler';

    // Read a file if it exists; otherwise return ''
    private async readMaybe(path: string): Promise<string> {
        try { return await this.readTextRoot(path); } catch { return ''; }
    }

    // Try a list of paths and return the first non-empty
    private async readFirst(paths: string[]): Promise<string> {
        for (const p of paths) {
            const txt = await this.readMaybe(p);
            if (txt) return txt;
        }
        return '';
    }
   
    async loadTaskInstances() {
        await this.ensureBackend();
        this.taskInstances.splice(0, this.taskInstances.length);

        const coerceTemplateName = (tpl: any): string => {
            if (typeof tpl === 'string') return tpl;
            if (tpl && typeof tpl === 'object') return String(tpl.name || tpl.type || '');
            const output = String(tpl ?? '');
            // console.log('[Scheduler -> loadTaskInstances]: coerceTemplateName returns', output);
            return output;
        };

        const safeParseItems = (raw: any): any[] => {
            if (Array.isArray(raw)) return raw;
            let result = [];
            try { result = JSON.parse(String(raw || '[]')); } catch { result = []; }
            // console.log('[Scheduler -> loadTaskInstances]: safeParseItems returns', result);
            return result;
        };

        if (this.isDaemon()) {
            try {
                const { id: uid, name: username } = await (window as any).cockpit.user();

                const items = this.parseListTasks(await daemon.listTasks('user'));
                console.log('[sched] daemon user items:', items.length, items);

                for (const t of items) {
                    try {
                        if (!t?.name || !t?.template) continue;

                        const templateKey = this.normalizeTemplateKey(
                            typeof t.template === 'string' ? t.template : String(t.template?.name || t.template?.type || '')
                        );

                        console.log('[Scheduler -> loadTaskInstances]: templateKey', templateKey);
                        const tpl = this.resolveTemplate(templateKey);

                        console.log('[Scheduler -> loadTaskInstances]: tpl', tpl);

                        // Unit from daemon if present; otherwise derive
                        const unit = String(t.unit || await this.unitNameFromParts(templateKey, t.name, 'user'));
                        console.log('[Scheduler -> loadTaskInstances]: unit', unit);
                       
                        // *** TRUST the daemon’s data; only fall back to disk if missing ***
                        const paramsObj = (t.params ?? t.parameters ?? {});
                        const schedObj = (t.schedule ?? { enabled: false, intervals: [] });
                        const notes = (t.notes ?? '');

                        // if ((!paramsObj || !Object.keys(paramsObj).length) || !schedObj) {
                        //     const basePaths = [
                        //         `${Scheduler.STATE_ROOT}/${username}/${t.name}`,
                        //         `${Scheduler.STATE_ROOT}/${uid}/${t.name}`,
                        //     ];
                        //     const envText = await this.readFirst(basePaths.map(b => `${b}/${unit}.env`));
                        //     const jsonText = await this.readFirst(basePaths.map(b => `${b}/${unit}.json`));
                        //     if (envText) Object.assign(paramsObj, this.parseEnvTextToParams(envText));
                        //     if (jsonText) Object.assign(schedObj, JSON.parse(jsonText));
                        // }

                        const intervals = Array.isArray(schedObj.intervals)
                            ? schedObj.intervals.map((i: any) => new TaskScheduleInterval(i))
                            : [];
                        const schedule = new TaskSchedule(!!schedObj.enabled, intervals);

                        const paramNode = this.safeBuildParamNode(tpl.parameterSchema, paramsObj);

                        const inst = new TaskInstance(t.name, tpl, paramNode, schedule, notes);
                        (inst as any)._templateKey = templateKey;
                        this.setScope(inst, t.scope === 'system' ? 'system' : 'user'); // keep explicit

                        console.log('[sched] backend =', this.backend);
                        console.log('[sched] pushing TaskInstance:', t.name, templateKey, schedObj?.enabled);

                        this.taskInstances.push(inst);
                    } catch (e) {
                        console.warn('skip bad daemon task record:', e, t);
                    }
                }
            } catch (e) {
                console.warn('ListTasks(user) failed:', e);
            }

            // --- SYSTEM tasks (ADMIN ONLY): merge daemon + python, dedupe (prefer daemon)
            try {
                if (await this.isAdminUser()) {
                    const seenSys = new Set<string>();
                    const keyOf = (tpl: string, name: string) =>
                        `${this.normalizeTemplateKey(tpl)}:${name}`;

                    // 1) From daemon
                    try {
                        const rawSys = await daemon.listTasks('system');
                        const dItems = this.parseListTasks(rawSys);

                        for (const t of dItems) {
                            try {
                                if (!t?.name || !t?.template) continue;
                                const templateKey = this.normalizeTemplateKey(String(t.template));
                                const tpl = this.resolveTemplate(templateKey);

                                const intervals = (t.schedule?.intervals || []).map((i: any) => new TaskScheduleInterval(i));
                                const schedule = new TaskSchedule(!!t.schedule?.enabled, intervals);

                                const params = t.params ?? t.parameters ?? {};
                                const paramNode = this.safeBuildParamNode(tpl.parameterSchema, params);

                                const inst = new TaskInstance(t.name, tpl, paramNode, schedule, t.notes || '');
                                (inst as any)._templateKey = templateKey;
                                this.setScope(inst, 'system');

                                this.taskInstances.push(inst);
                                seenSys.add(keyOf(templateKey, t.name));
                            } catch (e) {
                                console.warn('skip bad daemon system record:', e);
                            }
                        }
                    } catch (e) {
                        console.warn('daemon.listTasks(system) failed:', e);
                    }
                }
            } catch (e) {
                console.warn('system task discovery (admin gate) failed:', e);
            }
            return;
        }

        // --- LEGACY backend ⇒ system tasks only
        try {
            const { stdout } = await runCommand(
                ['/usr/bin/env', 'python3', '-c', get_tasks_script],
                { superuser: 'try' }
            );
            const systemTasksData = safeParseItems(stdout);

            for (const task of systemTasksData) {
                try {
                    if (!task?.name || !task?.template) continue;

                    const templateKey = this.normalizeTemplateKey(coerceTemplateName(task.template));
                    const tpl = this.resolveTemplate(templateKey);

                    const paramNode = this.createParameterNodeFromSchema(tpl.parameterSchema, task.parameters || {});
                    const intervals = (task.schedule?.intervals || []).map((i: any) => new TaskScheduleInterval(i));
                    const schedule = new TaskSchedule(!!task.schedule?.enabled, intervals);

                    const inst = new TaskInstance(task.name, tpl, paramNode, schedule, task.notes || '');
                    (inst as any)._templateKey = templateKey;
                    this.setScope(inst, 'system');
                    this.taskInstances.push(inst);
                } catch (e) {
                    console.warn('skip bad legacy task record:', e);
                }
            }
        } catch (e) {
            console.error(errorString(e));
        }
    }


    // Main function to create a ParameterNode from JSON parameters based on a schema
    createParameterNodeFromSchema(schema: ParameterNode, parameters: any): ParameterNode {
        function cloneSchema(node: ParameterNode): ParameterNode {
            let newNode: ParameterNode;

            if (node instanceof StringParameter) {
                newNode = new StringParameter(node.label, node.key);
            } else if (node instanceof IntParameter) {
                newNode = new IntParameter(node.label, node.key);
            } else if (node instanceof BoolParameter) {
                newNode = new BoolParameter(node.label, node.key);
            } else if (node instanceof SelectionParameter) {
                newNode = new SelectionParameter(node.label, node.key);
            } else {
                newNode = new ParameterNode(node.label, node.key);
            }

            node.children.forEach(child => {
                newNode.addChild(cloneSchema(child));
            });

            return newNode;
        }

        const parameterRoot = cloneSchema(schema);

        function assignValues(node: ParameterNode, prefix = ''): void {
            const currentPrefix = prefix ? prefix + '_' : '';
            const fullKey = currentPrefix + node.key;
            // console.log(`Assigning value for key: ${fullKey}`);  
            if (parameters.hasOwnProperty(fullKey)) {
                let value = parameters[fullKey];
                // console.log(`Found value: ${value} for key: ${fullKey}`);  // Debug log to confirm values
                if (node instanceof StringParameter || node instanceof SelectionParameter) {
                    node.value = value;
                } else if (node instanceof IntParameter) {
                    node.value = parseInt(value);
                } else if (node instanceof BoolParameter) {
                    node.value = value === 'true';
                }
            }
            node.children.forEach(child => assignValues(child, fullKey));
        }

        assignValues(parameterRoot);
        return parameterRoot;
    }


    parseEnvKeyValues(envKeyValues: string[], templateName: string) {
        let envObject = envKeyValues.reduce((acc, curr) => {
            const [key, ...rest] = curr.split('=');
            const value = rest.join('=');
            acc[key] = value;
            return acc;
        }, {} as Record<string, string|number>);

      //  console.log('templateName:', templateName);

        function formatEnvOption(envObject, key, emptyValue = '', excludeValues = [0, '0', "''"], resetKeys: string[] = []) {
            if (envObject[key] && !excludeValues.includes(envObject[key])) {
                envObject[key] = `${envObject[key]}`;
            } else {
                envObject[key] = emptyValue;
                resetKeys.forEach(resetKey => envObject[resetKey] = emptyValue);
            }
        }

        switch (templateName) {
            case 'ZfsReplicationTask':
                if (envObject['zfsRepConfig_sendOptions_raw_flag'] === 'true') {
                    envObject['zfsRepConfig_sendOptions_compressed_flag'] = '';
                } else if (envObject['zfsRepConfig_sendOptions_compressed_flag'] === 'true') {
                    envObject['zfsRepConfig_sendOptions_raw_flag'] = '';
                }
                break;

            case 'RsyncTask':
                if (!envObject['rsyncConfig_target_info_host']) {
                    envObject['rsyncConfig_target_info_host'] = '';
                    envObject['rsyncConfig_target_info_port'] = '';
                    envObject['rsyncConfig_target_info_user'] = '';
                }
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_log_file_path');
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_bandwidth_limit_kbps');
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_include_pattern');
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_exclude_pattern');
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_custom_args');
                break;

            case 'CloudSyncTask':
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_log_file_path');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_bandwidth_limit_kbps');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_include_pattern');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_exclude_pattern');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_custom_args');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_transfers');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_max_transfer_size', '', [0, '0', "''"], ['cloudSyncConfig_rcloneOptions_max_transfer_size_unit']);
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_include_from_path');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_exclude_from_path');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_multithread_chunk_size', '', [0, '0', "''"], ['cloudSyncConfig_rcloneOptions_multithread_chunk_size_unit']);
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_multithread_cutoff', '', [0, '0', "''"], ['cloudSyncConfig_rcloneOptions_multithread_cutoff_unit']);
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_multithread_streams');
                formatEnvOption(envObject, 'cloudSyncConfig_rcloneOptions_multithread_write_buffer_size', '', [0, '0', "''"], ['cloudSyncConfig_rcloneOptions_multithread_write_buffer_size_unit']);
                break;

            default:
                break;
        }
      //  console.log('envObject After:', envObject);
        return envObject;
    }


    getScriptFromTemplateName(templateName: string) {
        switch (templateName) {
            case 'ZfsReplicationTask':
                return 'replication-script';
            case 'AutomatedSnapshotTask':
                return 'autosnap-script';
            case 'RsyncTask':
                return 'rsync-script';
            case 'SmartTest':
                return 'smart-test-script';
            case 'ScrubTask':
                return 'scrub-script';  
            case 'CloudSyncTask':
                return 'cloudsync-script';
            default:
                console.error('no script provided');
                break;
        }
    }

    async registerTaskInstance(taskInstance: TaskInstance) {
        await this.ensureBackend();
        // generate env file with key/value pairs (Task Parameters)
        const envKeyValues = taskInstance.parameters.asEnvKeyValues();
        //  console.log('envKeyVals Before Parse:', envKeyValues);
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);
        let scriptPath = '';
        const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
        envObject['taskName'] = taskInstance.name;

        if (templateName === 'CustomTask') {
            const children = taskInstance.parameters?.children;
            const pathParam = children?.find((child: any) => child.key === 'filePath');
            scriptPath = pathParam?.value || '/opt/45drives/houston/scheduler/scripts/undefined.py';
        } else {
            const scriptFileName = this.getScriptFromTemplateName(templateName);
            scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;
        }

        // === DAEMON path ===
        if (this.isDaemon()) {
            const scope = await this.desiredScopeFor(taskInstance, true);
            const scheduleForDbus = this.toPlain(taskInstance.schedule);
            await daemon.createTask(
                templateName,
                envObject,                          // pass the dict, not a text file
                scriptPath,
                scheduleForDbus,
                taskInstance.notes ?? '',
                scope
            );
            return; // stop here; no legacy file writes
        }

        // === LEGACY path  ===
        if (templateName === 'CloudSyncTask') {
            envObject['RCLONE_CONFIG'] = '/root/.config/rclone/rclone.conf';
            envObject['cloudSyncConfig_rclone_config_path'] = '/root/.config/rclone/rclone.conf';
        }

        // Remove empty values from envObject
        const filteredEnvObject = Object.fromEntries(
            Object.entries(envObject).filter(([_, value]) => value !== '' && value !== 0)
        );

        // Convert back to envKeyValuesString
        const envKeyValuesString = Object.entries(filteredEnvObject)
            .map(([key, value]) => `${key}=${value}`)
            .join('\n');

        const templateTimerPath = `/opt/45drives/houston/scheduler/templates/Schedule.timer`;
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const baseName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;
        const envFilePath = `/etc/systemd/system/${baseName}.env`;
        const jsonFilePath = `/etc/systemd/system/${baseName}.json`;
        const notesFilePath = `/etc/systemd/system/${baseName}.txt`;

        // Write env file
        const envFile = new File(server, envFilePath);
        await unwrap(envFile.write(envKeyValuesString, { superuser: 'try' }));
        console.log('env file created and content written successfully');

        // Write notes file if needed
        if (taskInstance.notes !== '') {
            const notesFile = new File(server, notesFilePath);
            await unwrap(notesFile.write(taskInstance.notes ?? '', { superuser: 'try' }));
            console.log('notes file created and content written successfully');
        }

        if (taskInstance.schedule.intervals.length < 1) {
            // No schedule: standalone service
            console.log('No schedules found, parameter file generated.');
            await createStandaloneTask(templateName, scriptPath, envFilePath);
        } else {
            // Write schedule JSON
            const jsonFile = new File(server, jsonFilePath);
            const jsonString = JSON.stringify(taskInstance.schedule, null, 2);
            await unwrap(jsonFile.write(jsonString, { superuser: 'try' }));
            console.log('json file created and content written successfully');

            await createTaskFiles(templateName, scriptPath, envFilePath, templateTimerPath, jsonFilePath);
        }

    }

    async updateTaskInstance(taskInstance, opts?:{oldName?: string}) {
        await this.ensureBackend();
        //populate data from env file and then delete + recreate task files
        const envKeyValues = taskInstance.parameters.asEnvKeyValues();
        // console.log('envKeyVals:', envKeyValues);
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
        envObject['taskName'] = taskInstance.name;

        let scriptPath: string;
        if (templateName === 'CustomTask') {
            const pathParam = taskInstance.parameters?.children?.find((c: any) => c.key === 'path');
            scriptPath = pathParam?.value || '/opt/45drives/houston/scheduler/scripts/undefined.py';
        } else {
            const scriptFileName = this.getScriptFromTemplateName(templateName);
            scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;
        }

        // === DAEMON path ===
        if (this.isDaemon()) {
            const scope = await this.desiredScopeFor(taskInstance);
            const oldName = opts?.oldName ?? taskInstance.name;

            await daemon.updateTask(
                templateName,
                oldName,
                envObject,
                scriptPath,
                taskInstance.schedule,
                taskInstance.notes ?? '',
                scope
            );

            return;
        }

        // === LEGACY path  ===
        if (templateName === 'CloudSyncTask') {
            envObject['RCLONE_CONFIG'] = '/root/.config/rclone/rclone.conf';
            envObject['cloudSyncConfig_rclone_config_path'] = '/root/.config/rclone/rclone.conf';
        }

        // Remove empty values
        const filteredEnvObject = Object.fromEntries(
            Object.entries(envObject).filter(([_, value]) => value !== '' && value !== 0)
        );

        const envKeyValuesString = Object.entries(filteredEnvObject)
            .map(([key, value]) => `${key}=${value}`)
            .join('\n');

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const baseName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;
        const envFilePath = `/etc/systemd/system/${baseName}.env`;

        // Update env file
        const envFile = new File(server, envFilePath);
        await unwrap(envFile.replace(envKeyValuesString, { superuser: 'try' }));
        console.log('env file updated successfully');

        // Regenerate the systemd units from the env
        await createStandaloneTask(templateName, scriptPath, envFilePath);

        // Reload the systemd daemon
        await runCommand(['systemctl', 'daemon-reload'], { superuser: 'try' });

    }

    // maybe using this later, not sure.
    // private async renameLegacyTaskFiles(templateName: string, oldName: string, newName: string, wantEnabled: boolean) {
    //     const prefix = 'houston_scheduler_';
    //     const etc = '/etc/systemd/system';
    //     const oldBase = `${prefix}${templateName}_${oldName}`;
    //     const newBase = `${prefix}${templateName}_${newName}`;

    //     const sh = (cmd: string) => legacy.useSpawn(['bash', '-lc', cmd], { superuser: 'try' }).promise();

    //     // was enabled? (don’t fail if unit missing)
    //     let wasEnabled = false;
    //     try {
    //         const st = await legacy.useSpawn(['bash', '-lc', `systemctl is-enabled ${oldBase}.timer`], { superuser: 'try' }).promise();
    //         wasEnabled = /enabled/.test(st.stdout || '');
    //     } catch { }

    //     // stop/disable old
    //     await sh(`systemctl stop ${oldBase}.timer ${oldBase}.service 2>/dev/null || true`);
    //     await sh(`systemctl disable ${oldBase}.timer 2>/dev/null || true`);

    //     // move state files if present
    //     await sh(`[ -e ${etc}/${oldBase}.env ]  && mv ${etc}/${oldBase}.env  ${etc}/${newBase}.env  || true`);
    //     await sh(`[ -e ${etc}/${oldBase}.json ] && mv ${etc}/${oldBase}.json ${etc}/${newBase}.json || true`);
    //     await sh(`[ -e ${etc}/${oldBase}.txt ]  && mv ${etc}/${oldBase}.txt  ${etc}/${newBase}.txt  || true`);

    //     // service/timer files are regenerated from templates (safer than mv due to embedded names)
    //     await sh(`rm -f ${etc}/${oldBase}.service ${etc}/${oldBase}.timer || true`);
    //     await sh(`systemctl daemon-reload`);

    //     // re-enable if it *was* enabled or the UI wants it enabled
    //     const enable = wantEnabled || wasEnabled;
    //     if (enable) {
    //         await sh(`systemctl enable --now ${newBase}.timer 2>/dev/null || true`);
    //     }
    // }


    async updateTaskNotes(taskInstance) {
        await this.ensureBackend();
        //populate data from env file and then delete + recreate task files
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        // --- DAEMON
        if (this.isDaemon()) {
            const scope = await this.desiredScopeFor(taskInstance);
            // Re-emit the task with updated notes (idempotent in daemon)
            const envKeyValues = taskInstance.parameters.asEnvKeyValues();
            const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
            envObject['taskName'] = taskInstance.name;

            let scriptPath = '';
            if (templateName === 'CustomTask') {
                const pathParam = taskInstance.parameters?.children?.find((c: any) => c.key === 'path');
                scriptPath = pathParam?.value || '/opt/45drives/houston/scheduler/scripts/undefined.py';
            } else {
                const scriptFileName = this.getScriptFromTemplateName(templateName);
                scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;
            }

            await daemon.createTask(
                templateName, 
                envObject, 
                scriptPath, 
                taskInstance.schedule, 
                taskInstance.notes ?? '', 
                scope
            );
            return;
        }

        // === LEGACY path  ===
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const notesFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.txt`;

        console.log('notesFilePath:', notesFilePath);

        const notesFile = new File(server, notesFilePath);
        await unwrap(notesFile.replace(taskInstance.notes ?? '', { superuser: 'try' }));
        console.log('notes file updated successfully');
    }

    async unregisterTaskInstance(taskInstance: TaskInstanceType) {
        await this.ensureBackend();
        //delete task + associated files
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        if (this.isDaemon()) {
            await daemon.deleteTask(templateName, taskInstance.name);
            return;
        }

        // === LEGACY path  ===
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;
        if (taskInstance.schedule.enabled) {
            await this.disableSchedule(taskInstance);
        }
        await removeTask(fullTaskName);
        console.log(`${fullTaskName} removed`);
    }
    
    async runTaskNow(taskInstance: TaskInstanceType): Promise<string> {
        await this.ensureBackend();
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        // Helper: poll until the service is no longer running
        const waitForFinalStatus = async (): Promise<string> => {
            let finalStatus = 'Unknown';

            while (true) {
                const status = await this.getServiceStatus(taskInstance);
                if (status) {
                    finalStatus = status;
                }

                if (
                    status === 'Completed' ||
                    status === 'Inactive (Disabled)' || // covers manual stop
                    status === 'Failed'
                ) {
                    break;
                }

                await new Promise(r => setTimeout(r, 1000));
            }

            return finalStatus;
        };

        if (this.isDaemon()) {
            await daemon.runNow(templateName, taskInstance.name);
            const finalStatus = await waitForFinalStatus();
            console.log(
                `Task ${templateName}_${taskInstance.name} finished with status: ${finalStatus}`
            );
            return finalStatus;
        }

        // === LEGACY path  ===
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        console.log(`Running ${fullTaskName}...`);
        try {
            await runCommand(['systemctl', 'reset-failed', `${fullTaskName}.service`], { superuser: 'try' });
        } catch {
            // best-effort; ignore if it fails
        }
        await runTask(fullTaskName);

        const finalStatus = await waitForFinalStatus();
        console.log(`Task ${fullTaskName} completed with status: ${finalStatus}`);
        return finalStatus;
    }

    async stopTaskNow(taskInstance: TaskInstanceType) {
        await this.ensureBackend();
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        // === DAEMON path ===
        if (this.isDaemon()) {
            await daemon.stopTask(templateName, taskInstance.name);
            return;
        }

        // === LEGACY path ===
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        console.log(`Stopping ${fullTaskName}...`);
        await stopTask(fullTaskName);
        console.log(`Task ${fullTaskName} stopped.`);
    }

    async getTimerStatus(ti: TaskInstanceType): Promise<string | false> {
        await this.ensureBackend();
        const log = new TaskExecutionLog([]);
        const tplKey = this.templateKey(ti, this.normalizeTemplateKey(ti.template.name));

        if (this.isDaemon()) {
            try {
                const st: any = await this.fetchStatus(ti);
                const unit = String(st?.unit || await this.unitNameFor(ti));
                const output = String(st?.timer || '');
                return this.parseTaskStatus(output, unit, log, ti);
            } catch (e) {
                console.warn('GetStatus(timer) failed:', e);
                return false;
            }
        }

        // Legacy / direct systemctl path
        const unit = await this.unitNameFor(ti);
        try {
            const { stdout, stderr, exitStatus } = await runCommand(
                [
                    'systemctl', 'show', `${unit}.timer`, '--no-pager',
                    '--property',
                    'LoadState,ActiveState,SubState,Result,LastTriggerUSec,LastTrigger,NextElapseUSecRealtime,MergedUnit',
                ],
                { superuser: 'try' }
            );

            if (exitStatus !== 0) {
                if (/not found/i.test(stdout) || /not found/i.test(stderr)) {
                    return this.parseTaskStatus('', unit, log, ti);
                }
                console.warn(`getTimerStatus(${unit}):`, stderr || stdout);
                return false;
            }

            return this.parseTaskStatus(stdout || '', unit, log, ti);
        } catch (e: any) {
            console.warn(`getTimerStatus(${unit}) error:`, errorString(e));
            return false;
        }

    }
    

    async getServiceStatus(ti: TaskInstanceType): Promise<string | false> {
        await this.ensureBackend();
        const log = new TaskExecutionLog([]);
        const tplKey = this.templateKey(ti, this.normalizeTemplateKey(ti.template.name));

        if (this.isDaemon()) {
            try {
                const st: any = await this.fetchStatus(ti);
                const unit = String(st?.unit || await this.unitNameFor(ti));      // <— NEW
                const output = String(st?.service || '');
                return this.parseTaskStatus(output, unit, log, ti);
            } catch {
                const unit = await this.unitNameFor(ti);                          // <— NEW
                return this.parseTaskStatus('', unit, log, ti);
            }
        }

        // Legacy / direct systemctl path
        const unit = await this.unitNameFor(ti);
        try {
            const { stdout, stderr, exitStatus } = await runCommand(
                [
                    'systemctl', 'show', `${unit}.service`, '--no-pager',
                    '--property',
                    'LoadState,ActiveState,SubState,Result,ActiveEnterTimestampUSec,ActiveEnterTimestamp,ExecMainStartTimestampUSec,ExecMainStartTimestamp,MergedUnit',
                ],
                { superuser: 'try' }
            );

            if (exitStatus !== 0) {
                if (/not found/i.test(stdout) || /LoadState=not-found/.test(stdout)) {
                    return this.parseTaskStatus('', unit, log, ti);
                }
                console.warn(`getServiceStatus(${unit}):`, stderr || stdout);
                return false;
            }

            return this.parseTaskStatus(stdout || '', unit, log, ti);
        } catch (e: any) {
            console.warn(`getServiceStatus(${unit}) error:`, errorString(e));
            return false;
        }

    }

    private parseShow(output: string) {
        const m = new Map<string, string>();
        for (const line of (output || '').split(/\r?\n/)) {
            const i = line.indexOf('=');
            if (i > 0) m.set(line.slice(0, i), line.slice(i + 1));
        }

        const num = (k: string) => {
            const v = m.get(k);
            const n = v ? Number(v) : NaN;
            return Number.isFinite(n) && n > 0 ? n : 0;
        };

        // If USec (microseconds) is missing, fall back to the wallclock string and parse it.
        // Date.parse → ms since epoch; multiply by 1000 to get µs so callers stay consistent.
        const ts = (numKey: string, strKey: string) => {
            const u = num(numKey);
            if (u) return u;
            const s = m.get(strKey);
            if (s) {
                const ms = Date.parse(s);
                if (Number.isFinite(ms)) return ms * 1000;
            }
            return 0;
        };

        return {
            load: m.get('LoadState') || '',
            active: m.get('ActiveState') || '',
            sub: m.get('SubState') || '',
            result: m.get('Result') || '',
            // timers
            lastTriggerUSec: ts('LastTriggerUSec', 'LastTrigger'),
            nextElapseUSec: num('NextElapseUSecRealtime'),
            // services (prefer ExecMainStart, fall back to ActiveEnter)
            serviceStartUSec:
                ts('ExecMainStartTimestampUSec', 'ExecMainStartTimestamp') ||
                ts('ActiveEnterTimestampUSec', 'ActiveEnterTimestamp'),
            // services (exit time if available)
            serviceExitUSec:
                ts('ExecMainExitTimestampUSec', 'ExecMainExitTimestamp') ||
                ts('InactiveEnterTimestampUSec', 'InactiveEnterTimestamp'),
        };
    }

    private async parseTaskStatus(
        output: string,
        unit: string,
        log: TaskExecutionLog,
        ti: TaskInstanceType
    ): Promise<string | false> {
        try {
            // Fast path: systemctl show
            if (output.includes('ActiveState=')) {
                const s = this.parseShow(output);

                if (s.active === 'active' && s.sub === 'waiting') return 'Active (Pending)';
                if (s.active === 'active' && s.sub === 'running') return 'Active (Running)';

                if (s.active === 'inactive' && s.sub === 'dead') {
                    const hasRun = !!s.serviceStartUSec; // non-zero only after the service has actually started

                    // Brand-new / never-run units should *not* be considered completed
                    if (!hasRun) {
                        return 'Inactive (Disabled)';
                    }

                    // For units that *have* run at least once, trust systemd first
                    if (s.result === 'success') {
                        return 'Completed';
                    }

                    let recentlyCompleted = false;
                    try {
                        recentlyCompleted = await log.wasTaskRecentlyCompleted(ti);
                    } catch (_) {
                        // swallow
                    }
                    return recentlyCompleted ? 'Completed' : 'Inactive (Disabled)';
                }

                if (s.active === 'failed' || s.sub === 'failed') return 'Failed';
                const base = s.active || 'unknown';
                return s.sub ? `${base} (${s.sub})` : base;
            }

            // Fallback: systemctl status text
            const m = output.match(/^\s*Active:\s*([a-z]+)\s*\(([^)]*)\)/im);
            if (!m) return 'Unit inactive or not found.';

            const stateText = `${m[1]} (${m[2]})`;
            switch (stateText) {
                case 'activating (start)': return 'Starting...';
                case 'active (waiting)': return 'Active (Pending)';
                case 'active (running)': return 'Active (Running)';
                case 'inactive (dead)': {
                    const unitEsc = unit.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const succeededRegex = new RegExp(`${unitEsc}\\.service: Succeeded`, 'm');
                    const noJournal = /No journal files were opened|You are currently not seeing messages/.test(output);
                    if (succeededRegex.test(output)) return 'Completed';

                    let recentlyCompleted = false;
                    try {
                        if (!noJournal) {
                            recentlyCompleted = await log.wasTaskRecentlyCompleted(ti);
                        }
                    } catch (_) {
                        /* swallow */
                    }
                    return recentlyCompleted ? 'Completed' : 'Inactive (Disabled)';
                }
                default:
                    return stateText;
            }
        } catch (e) {
            console.error(`Error parsing status for ${unit}:`, e);
            return false;
        }
    }

    async getTaskProgress(taskInstance: TaskInstanceType): Promise<number | null> {
        await this.ensureBackend();
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        // === DAEMON path ===
        if (this.isDaemon()) {
            try {
                const st: any = await daemon.getStatus(templateName, taskInstance.name);
                const txt = String(st?.service || '');

                const match = txt.match(/(\d+)%/);
                return match ? parseInt(match[1], 10) : null;
            } catch {
                return null;
            }
        }

        // === LEGACY path ===
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        try {
            const { stdout } = await runCommand(
                ['systemctl', 'show', `${fullTaskName}.service`, '--property=StatusText', '--value'],
                { superuser: 'try' }
            );
            const txt = (stdout || '').trim();
            const match = txt.match(/(\d+)%/);
            return match ? parseInt(match[1], 10) : null;
        } catch {
            return null;
        }
    }



    async enableSchedule(taskInstance) {
        await this.ensureBackend();
        if (this.isDaemon()) {
            await daemon.enableSchedule(this.normalizeTemplateKey(taskInstance.template.name), taskInstance.name, true);
            taskInstance.schedule.enabled = true;
            return;
        }

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        try {
            const timerName = `${fullTaskName}.timer`;

            // systemctl enable
            await runCommand(['systemctl', 'enable', timerName], { superuser: 'try' });

            console.log(`${timerName} has been enabled and started`);
            taskInstance.schedule.enabled = true;

            await this.updateSchedule(taskInstance);
        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }

    async disableSchedule(taskInstance) {
        await this.ensureBackend();
        if (this.isDaemon()) {
            await daemon.enableSchedule(this.normalizeTemplateKey(taskInstance.template.name), taskInstance.name, false);
            taskInstance.schedule.enabled = false;
            return;
        }

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        try {
            const timerName = `${fullTaskName}.timer`;
            const serviceName = `${fullTaskName}.service`;

            // Stop and disable timer
            await runCommand(['systemctl', 'stop', timerName], { superuser: 'try' });
            await runCommand(['systemctl', 'disable', timerName], { superuser: 'try' });

            console.log(`${timerName} has been stopped and disabled`);
            taskInstance.schedule.enabled = false;

            try {
                // Stop and disable service; reset failed state
                await runCommand(['systemctl', 'stop', serviceName], { superuser: 'try' });
                await runCommand(['systemctl', 'disable', serviceName], { superuser: 'try' });
                await runCommand(['systemctl', 'reset-failed', serviceName], { superuser: 'try' });
            } catch (e) {
                console.warn(`Stopping/cleaning ${serviceName} returned:`, errorString(e));
            }

            await this.updateSchedule(taskInstance);
        } catch (error) {
            console.error(errorString(error));
            return false;
        }

    }

    async updateSchedule(taskInstance) {
        await this.ensureBackend();
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        if (this.isDaemon()) {
            const scope = await this.desiredScopeFor(taskInstance);
            const envKeyValues = taskInstance.parameters.asEnvKeyValues();
            const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
            envObject['taskName'] = taskInstance.name;

            const scriptFileName = this.getScriptFromTemplateName(templateName);
            const scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;

            const scheduleForDbus = this.toPlain(taskInstance.schedule);
            await daemon.createTask(
                templateName, 
                envObject, 
                scriptPath, 
                scheduleForDbus, 
                taskInstance.notes ?? '', 
                scope
            );
            await daemon.enableSchedule(templateName, taskInstance.name, !!taskInstance.schedule.enabled);
            return;
        }

        const templateTimerPath = `/opt/45drives/houston/scheduler/templates/Schedule.timer`;

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;
        const jsonFilePath = `/etc/systemd/system/${fullTaskName}.json`;

        const jsonFile = new File(server, jsonFilePath);
        const jsonString = JSON.stringify(taskInstance.schedule, null, 2);
        await unwrap(jsonFile.replace(jsonString, { superuser: 'try' }));
        console.log('json file created and content written successfully');

        await createScheduleForTask(fullTaskName, templateTimerPath, jsonFilePath);

        // Reload the system daemon and restart timer
        await runCommand(['systemctl', 'daemon-reload'], { superuser: 'try' });
        await runCommand(['systemctl', 'restart', `${fullTaskName}.timer`], { superuser: 'try' });
    }

    async deleteSchedule(taskInstance: TaskInstanceType) {
        await this.ensureBackend();
        const templateName = this.normalizeTemplateKey(taskInstance.template.name);

        // === DAEMON path ===
        if (this.isDaemon()) {
            await daemon.clearSchedule(templateName, taskInstance.name);
            taskInstance.schedule.enabled = false;
            taskInstance.schedule.intervals = [];
            return true;
        }
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        const timerUnit = `${fullTaskName}.timer`;
        const jsonPath = `/etc/systemd/system/${fullTaskName}.json`;
        const timerPath = `/etc/systemd/system/${timerUnit}`;

        try {
            const stateful: Array<Promise<any>> = [];

            // Stop / disable timer (ignore errors)
            await runCommand(['systemctl', 'stop', timerUnit], { superuser: 'try' }).catch(() => { });
            await runCommand(['systemctl', 'disable', timerUnit], { superuser: 'try' }).catch(() => { });

            // Remove timer + schedule json
            await runCommand(['rm', '-f', timerPath], { superuser: 'try' });
            await runCommand(['rm', '-f', jsonPath], { superuser: 'try' });

            // Clean up state and reload systemd
            await runCommand(['systemctl', 'reset-failed'], { superuser: 'try' }).catch(() => { });
            await runCommand(['systemctl', 'daemon-reload'], { superuser: 'try' });

            taskInstance.schedule.enabled = false;
            taskInstance.schedule.intervals = [];

            console.log(`Schedule removed for ${fullTaskName}`);
            return true;
        } catch (e) {
            console.error(errorString(e));
            return false;
        }
    }

    parseIntervalIntoString(interval) {
        const elements: string[] = [];

        function getMonthName(number) {
            const months = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'];
            return months[number - 1] || 'undefined';
        }

        function getDaySuffix(day) {
            if (day > 3 && day < 21) return 'th';
            switch (day % 10) {
                case 1: return 'st';
                case 2: return 'nd';
                case 3: return 'rd';
                default: return 'th';
            }
        }

        function formatUnit(value, type) {
            if (value === '*') {
                return type === 'minute' ? 'every minute' :
                    type === 'hour' ? 'every hour' : `every ${type}`;
            } else if (value.startsWith('*/')) {
                const interval = value.slice(2);
                return `every ${interval} ${type}${interval > 1 ? 's' : ''}`;
            } else if (value.includes('/')) {
                const [base, step] = value.split('/');
                if (type === 'day') {
                    return `every ${step} days starting on the ${base}${getDaySuffix(parseInt(base))}`;
                }
                return `every ${step} ${type}${step > 1 ? 's' : ''} starting from ${base}`;
            } else if (value === '0' && type === 'minute') {
                return 'at the start of the hour';
            } else if (value === '0' && type === 'hour') {
                return 'at midnight';
            } else if (type === 'day') {
                return `on the ${value}${getDaySuffix(parseInt(value))} of the month`;
            } else if (type === 'month') {
                return `in ${getMonthName(parseInt(value))}`;
            }
            return `at ${value} ${type}`;
        }

        const formattedMinute = interval.minute ? formatUnit(interval.minute.value.toString(), 'minute') : null;
        const formattedHour = interval.hour ? formatUnit(interval.hour.value.toString(), 'hour') : null;

        // Special case for "at midnight"
        if (formattedMinute === null && formattedHour === 'at midnight') {
            elements.push('at midnight');
        } else {
            if (formattedMinute) elements.push(formattedMinute);
            if (formattedHour) elements.push(formattedHour);
        }

        const day = interval.day ? formatUnit(interval.day.value.toString(), 'day') : "every day";
        const month = interval.month ? formatUnit(interval.month.value.toString(), 'month') : "every month";
        const year = interval.year ? formatUnit(interval.year.value.toString(), 'year') : "every year";

        // Push only non-null values
        if (day) elements.push(day);
        if (month) elements.push(month);
        if (year) elements.push(year)

        if (interval.dayOfWeek && interval.dayOfWeek.length > 0) {
            elements.push(`on ${interval.dayOfWeek.join(', ')}`);
        }

        return elements.filter(e => e).join(', ');
    }

    // One function to produce: "Weekly — Fri @ 13:00", "Daily — @ 11:22 (starts Aug 18, 2025)",
    // "Hourly — every 15 min", "Monthly — on 18 @ 11:22", etc.
    describeInterval(interval: any): string {
        const v = (k: 'minute' | 'hour' | 'day' | 'month' | 'year') =>
            interval?.[k]?.value?.toString?.() ?? '*';

        const pad2 = (n: string | number) => String(n).padStart(2, '0');
        const minute = v('minute'), hour = v('hour'), day = v('day'),
            month = v('month'), year = v('year');

        // --- Day-of-week normalization (accepts "Fri", "Friday", 5, "5")
        const rawDows: any[] = Array.isArray(interval?.dayOfWeek) ? interval.dayOfWeek : [];
        const toDowIndex = (x: any): number => {
            if (typeof x === 'number') return x;
            const s = String(x).trim();
            if (/^\d+$/.test(s)) { const n = Number(s); return (n >= 0 && n <= 6) ? n : NaN; }
            const short = s.slice(0, 3).toLowerCase();
            const map: Record<string, number> = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
            return map[short] ?? NaN;
        };
        const dows: number[] = rawDows.map(toDowIndex).filter((n) => Number.isFinite(n)) as number[];

        const dowName = (n: number) => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][n] ?? String(n);
        const monthName = (m: number) => ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m - 1];

        const isStar = (s: string) => s === '*';
        const isStep = (s: string) => typeof s === 'string' && s.includes('/');
        const stepN = (s: string) => (s.split('/')[1] ?? '').trim();
        const isFixed = (s: string) => !isStar(s) && !isStep(s);

        const hhmm = () =>
            (hour !== '*' && minute !== '*') ? `${pad2(hour)}:${pad2(minute)}`
                : (hour !== '*' && minute === '*') ? `${pad2(hour)}:00`
                    : '';

        // --- WEEKLY (any DOW wins)
        if (dows.length) {
            const when = hhmm();
            return `Weekly — ${dows.map((d) => dowName(d)).join(', ')}${when ? ` @ ${when}` : ''}`;
        }

        // --- HOURLY (every N minutes / every N hours / :MM each hour)
        if (isStar(hour) && /^\*\/\d+$/.test(minute) && isStar(day) && isStar(month)) {
            return `Hourly — every ${minute.slice(2)} min`;
        }
        if (isStep(hour) && isStar(day) && isStar(month)) {
            const n = stepN(hour);
            return `Hourly — every ${n} hours${(minute !== '*' && !isStep(minute)) ? ` @ :${pad2(minute)}` : ''}`;
        }
        if (isStar(hour) && minute !== '*' && !isStep(minute) && isStar(day) && isStar(month)) {
            return `Hourly — at :${pad2(minute)}`;
        }

        // --- DAILY with explicit start date (never "One-time")
        if (isFixed(year) && isFixed(month) && isFixed(day)) {
            const when = hhmm();
            const start = `${monthName(Number(month))} ${day}, ${year}`;
            return `Daily — ${when ? `@ ${when} ` : ''}(starts ${start})`;
        }

        // --- MONTHLY (day-of-month drives)
        if (!isStar(day) && !isStep(day) && isStar(year)) {
            const when = hhmm();
            if (isStep(month)) {
                return `Monthly — on ${day} every ${stepN(month)} months${when ? ` @ ${when}` : ''}`;
            }
            if (!isStar(month)) {
                return `Monthly — on ${day} in ${monthName(Number(month))}${when ? ` @ ${when}` : ''}`;
            }
            return `Monthly — on ${day}${when ? ` @ ${when}` : ''}`;
        }

        // --- DAILY (default recurring daily)
        const when = hhmm();
        if (isStep(day) && isStar(month)) {
            return `Daily — every ${stepN(day)} days${when ? ` @ ${when}` : ''}`;
        }
        if (isStar(day) && isStar(month)) {
            return `Daily — ${when ? `@ ${when}` : 'any time'}`;
        }

        // --- If month is constrained but not DOW: treat as monthly cadence
        if (!isStar(month)) {
            if (isStep(month)) return `Monthly — every ${stepN(month)} months${when ? ` @ ${when}` : ''}`;
            return `Monthly — in ${monthName(Number(month))}${when ? ` @ ${when}` : ''}`;
        }

        // Fallback: pick a sensible bucket (daily)
        return `Daily — ${when ? `@ ${when}` : 'any time'}`;
    }


}
