import { ref } from 'vue';
import { legacy } from '@45drives/houston-common-lib';
import { TaskInstance, TaskTemplate, TaskSchedule, ZFSReplicationTaskTemplate, AutomatedSnapshotTaskTemplate, TaskScheduleInterval, RsyncTaskTemplate, ScrubTaskTemplate, SmartTestTemplate, CloudSyncTaskTemplate, CustomTaskTemplate } from './Tasks';
import { ParameterNode, StringParameter, SelectionParameter, IntParameter, BoolParameter, ObjectParameter } from './Parameters';
import { createStandaloneTask, createTaskFiles, createScheduleForTask, removeTask, runTask, formatTemplateName } from '../composables/utility';
import { TaskExecutionLog, TaskExecutionResult } from './TaskLog';
import { chooseBackend } from '../utils/bootstrapBackend';
import { daemon } from '../utils/daemonClient';

// @ts-ignore
import get_tasks_script from '../scripts/get-task-instances.py?raw';

const { BetterCockpitFile, errorString, useSpawn } = legacy;

export class Scheduler implements SchedulerType {
    taskTemplates: TaskTemplate[];
    taskInstances: TaskInstance[];

    constructor(taskTemplates: TaskTemplate[], taskInstances: TaskInstance[]) {
        this.taskTemplates = taskTemplates;
        this.taskInstances = taskInstances;
    }

    private backend: 'daemon' | 'legacy' = 'legacy';

    async init() { this.backend = (await chooseBackend()).backend; }


    private async ensureBackend(): Promise<void> {
        try {
            const picked = await chooseBackend();      // { backend: 'daemon' | 'legacy', isAdmin: boolean, ... }
            this.backend = picked.backend as any;
        } catch {
            this.backend = 'legacy' as any;
        }
    }


    // === Helpers for daemon branch ===
    private async readTextRoot(path: string): Promise<string> {
        const { useSpawn } = legacy;
        const state = useSpawn(['bash', '-lc', `cat '${path.replace(/'/g, `'\\''`)}'`], { superuser: 'try' });
        const out = await state.promise();
        return out.stdout ?? '';
    }

    private parseEnvTextToParams(envText: string): Record<string, string> {
        const params: Record<string, string> = {};
        envText.split(/\r?\n/).forEach((line) => {
            const s = line.trim();
            if (!s || s.startsWith('#')) return;
            const idx = s.indexOf('=');
            if (idx <= 0) return;
            const k = s.slice(0, idx);
            const v = s.slice(idx + 1);
            params[k] = v;
        });
        return params;
    }

    private isDaemon(): boolean { return this.backend === 'daemon'; }


    // NEW: canonical template key helper
    private templateKey(ti: TaskInstanceType, hint?: string): string {
        return (ti as any)._templateKey || hint || formatTemplateName(ti.template.name);
    }

    // NEW: single source of truth for unit names
    private async unitNameFor(ti: TaskInstanceType): Promise<string> {
        const key = this.templateKey(ti);
        const scope = (ti as any).scope as ('user' | 'system' | undefined);

        // system/legacy never has __u<uid>, and legacy backend always behaves like "system"
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


    // Inside Scheduler class
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

    private async readFirstExisting(paths: string[]): Promise<string> {
        for (const p of paths) {
            try {
                const txt = await this.readTextRoot(p);
                if (txt && txt.length) return txt;
            } catch { }
        }
        return '';
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
   
    async loadTaskInstances() {
        await this.ensureBackend();
        this.taskInstances.splice(0, this.taskInstances.length);

        const coerceTemplateName = (tpl: any): string => {
            if (typeof tpl === 'string') return tpl;
            if (tpl && typeof tpl === 'object') return String(tpl.name || tpl.type || '');
            return String(tpl ?? '');
        };

        const readFromKnownRoots = async (username: string, unit: string, taskName: string) => {
            // New layout: /var/lib/45drives/houston/scheduler/<user>/<taskName>/<unit>.(env|json|txt)
            // Legacy layout: /var/lib/45drives/houston/scheduler/<user>/<unit>/<unit>.(env|json|txt)
            const roots = [
                '/var/lib/45drives/houston/scheduler',
                '/var/lib/houston/scheduler', // fallback for older images, just in case
            ];
            const tryPaths = (rel: string) => roots.map(r => `${r}/${username}/${rel}`);

            const envText = await this.readFirstExisting([
                ...tryPaths(`${taskName}/${unit}.env`),
                ...tryPaths(`${unit}/${unit}.env`),
            ]);
            const jsonText = await this.readFirstExisting([
                ...tryPaths(`${taskName}/${unit}.json`),
                ...tryPaths(`${unit}/${unit}.json`),
            ]);
            const notes = await this.readFirstExisting([
                ...tryPaths(`${taskName}/${unit}.txt`),
                ...tryPaths(`${unit}/${unit}.txt`),
            ]);
            return { envText, jsonText, notes };
        };

        const toPlainObj = (x: any) => JSON.parse(JSON.stringify(x ?? {}));

        const safeParseItems = (raw: any): any[] => {
            if (Array.isArray(raw)) return raw;
            try { return JSON.parse(String(raw || '[]')); } catch { return []; }
        };

        if (this.backend === 'daemon') {
            // --- USER tasks via daemon
            try {
                const { name: username } = await (window as any).cockpit.user();
                // const items = safeParseItems(await daemon.listTasks('user'));
                const raw = await daemon.listTasks('user');
                let items: any[] = [];
                if (Array.isArray(raw)) {
                    items = raw;
                } else if (typeof raw === 'string') {
                    try { items = JSON.parse(raw); } catch { }
                } else if (raw && typeof raw.toString === 'function') {
                    try { items = JSON.parse(raw.toString()); } catch { }
                }

                for (const t of items) {
                    try {
                        if (!t?.name || !t?.template) continue;

                        const templateKey = this.normalizeTemplateKey(coerceTemplateName(t.template));
                        const tpl = this.resolveTemplate(templateKey);

                        const unit = String(t.unit || await this.unitNameFromParts(templateKey, t.name, 'user'));

                        const { envText, jsonText, notes } = await readFromKnownRoots(username, unit, t.name);

                        // Prefer parsed env; else fallback to daemon’s params (t.params), and last-resort t.parameters
                        const paramsFromEnv = this.parseEnvTextToParams(envText);
                        const paramsObj = Object.keys(paramsFromEnv).length
                            ? paramsFromEnv
                            : toPlainObj(t.params ?? t.parameters ?? {});

                        // Prefer file schedule if present; else daemon’s schedule
                        const sObj = (() => {
                            if (jsonText?.trim()) {
                                try { return JSON.parse(jsonText); } catch { }
                            }
                            return toPlainObj(t.schedule ?? { enabled: false, intervals: [] });
                        })();

                        const intervals = (sObj.intervals ?? []).map((i: any) => new TaskScheduleInterval(i));
                        const schedule = new TaskSchedule(!!sObj.enabled, intervals);

                        // ✅ Build the node from the flat params
                        const paramNode = this.safeBuildParamNode(tpl.parameterSchema, paramsObj);

                        const inst = new TaskInstance(t.name, tpl, paramNode, schedule, notes ?? (t.notes || ''));
                        (inst as any)._templateKey = templateKey;
                        this.setScope(inst, 'user');
                        this.taskInstances.push(inst);
                    } catch (e) {
                        console.warn('skip bad task record:', e);
                    }
                }
            } catch (e) {
                console.warn('ListTasks(user) failed:', e);
            }

            // --- SYSTEM/legacy tasks (admins only)
            try {
                if (await this.isAdminUser()) {
                    const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_tasks_script], { superuser: 'try' });
                    const out = (await state.promise()).stdout!;
                    const systemTasksData = safeParseItems(out);

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
                            console.warn('skip bad system task record:', e);
                        }
                    }
                }
            } catch (e) {
                console.warn('system task discovery failed:', e);
            }
            return;
        }

        // --- LEGACY backend ⇒ system tasks only
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_tasks_script], { superuser: 'try' });
            const out = (await state.promise()).stdout!;
            const systemTasksData = safeParseItems(out);

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
            const [key, value] = curr.split('=');
            acc[key] = value;
            return acc;
        }, {});

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
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_bandwidth_limit_kbps');
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_include_pattern');
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_exclude_pattern');
                formatEnvOption(envObject, 'rsyncConfig_rsyncOptions_custom_args');
                break;


            case 'CloudSyncTask':
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
        const templateName = formatTemplateName(taskInstance.template.name);
        let scriptPath = '';
        const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
        envObject['taskName'] = taskInstance.name;

        if (templateName === 'CustomTask') {
            const children = taskInstance.parameters?.children;
            const pathParam = children?.find((child: any) => child.key === 'path');
            scriptPath = pathParam?.value || '/opt/45drives/houston/scheduler/scripts/undefined.py';
        } else {
            const scriptFileName = this.getScriptFromTemplateName(templateName);
            scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;
        }

        // === DAEMON path ===
        if (this.backend === 'daemon') {
            const scheduleForDbus = this.toPlain(taskInstance.schedule);
            await daemon.createTask(
                templateName,
                envObject,                          // pass the dict, not a text file
                scriptPath,
                scheduleForDbus,
                taskInstance.notes ?? '',
                'auto'
            );
            return; // stop here; no legacy file writes
        }

        // === LEGACY path  ===
        if (templateName === 'CloudSyncTask') {
            // legacy writes system units that run as root
            envObject['RCLONE_CONFIG'] = '/root/.config/rclone/rclone.conf';
            // also provide the explicit hint your script can read
            envObject['cloudSyncConfig_rclone_config_path'] = '/root/.config/rclone/rclone.conf';
        }
        // Remove empty values from envObject
        const filteredEnvObject = Object.fromEntries(Object.entries(envObject).filter(([key, value]) => value !== '' && value !== 0));

        //  console.log('Filtered envObject:', filteredEnvObject);

        // Convert the parsed envObject back to envKeyValuesString
        const envKeyValuesString = Object.entries(filteredEnvObject).map(([key, value]) => `${key}=${value}`).join('\n');
        const templateTimerPath = `/opt/45drives/houston/scheduler/templates/Schedule.timer`;

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const envFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.env`;

        //  console.log('envFilePath:', envFilePath);
        // console.log('envKeyValuesString:', envKeyValuesString);

        const file = new BetterCockpitFile(envFilePath, {
            superuser: 'try',
        });

        file.replace(envKeyValuesString).then(() => {
            console.log('env file created and content written successfully');
            file.close();

        }).catch(error => {
            console.error("Error writing content to the file:", error);
            file.close();
        });

        const jsonFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.json`;
        // console.log('jsonFilePath:', jsonFilePath);

        //run script to generate notes file
        console.log("generating notes file");
        const notesFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.txt`;
        //const notes = taskInstance.notes
        const notes = taskInstance.notes
        const file3 = new BetterCockpitFile(notesFilePath, {
            superuser: 'try',
        }) 
        file3.replace(notes).then(() => {
            console.log('Notes file created and content written successfully');
            file3.close();

        }).catch(error => {
            console.error("Error writing content to the notes file:", error);
            file3.close();
        });


        //run script to generate service + timer via template, param env and schedule json
        if (taskInstance.schedule.intervals.length < 1) {
            //ignore schedule for now
            console.log('No schedules found, parameter file generated.');

            await createStandaloneTask(templateName, scriptPath, envFilePath);

        } else {
            // generate json file with enabled boolean + intervals (Schedule Intervals)
            // requires schedule data object
            // console.log('schedule:', taskInstance.schedule);

            const file2 = new BetterCockpitFile(jsonFilePath, {
                superuser: 'try',
            });

            const jsonString = JSON.stringify(taskInstance.schedule, null, 2);

            file2.replace(jsonString).then(() => {
                console.log('json file created and content written successfully');
                file2.close();
            }).catch(error => {
                console.error("Error writing content to the file:", error);
                file2.close();
            });

            await createTaskFiles(templateName, scriptPath, envFilePath, templateTimerPath, jsonFilePath);
        }
    }

    async updateTaskInstance(taskInstance) {
        await this.ensureBackend();
        //populate data from env file and then delete + recreate task files
        const envKeyValues = taskInstance.parameters.asEnvKeyValues();
        // console.log('envKeyVals:', envKeyValues);
        const templateName = formatTemplateName(taskInstance.template.name);

        const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
        envObject['taskName'] = taskInstance.name;

        const scriptFileName = this.getScriptFromTemplateName(templateName);
        const scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;

        if (this.backend === 'daemon') {
            await daemon.createTask(
                templateName,
                envObject,
                scriptPath,
                taskInstance.schedule,
                taskInstance.notes ?? '',
                'auto'
            );
            // If schedule.enabled changed, the daemon respects it on create; nothing else to do.
            return;
        }


        // === LEGACY path  ===
        if (templateName === 'CloudSyncTask') {
            envObject['RCLONE_CONFIG'] = '/root/.config/rclone/rclone.conf';
            envObject['cloudSyncConfig_rclone_config_path'] = '/root/.config/rclone/rclone.conf';
        }
        // Remove empty values from envObject
        const filteredEnvObject = Object.fromEntries(Object.entries(envObject).filter(([key, value]) => value !== '' && value !== 0));

        // console.log('Filtered envObject:', filteredEnvObject);

        // Convert the parsed envObject back to envKeyValuesString
        const envKeyValuesString = Object.entries(filteredEnvObject).map(([key, value]) => `${key}=${value}`).join('\n');

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const envFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.env`;

        // console.log('envFilePath:', envFilePath);

        const file = new BetterCockpitFile(envFilePath, {
            superuser: 'try',
        });

        file.replace(envKeyValuesString).then(() => {
            console.log('env file updated successfully');
            file.close();
        }).catch(error => {
            console.error("Error updating file:", error);
            file.close();
        });

        await createStandaloneTask(templateName, scriptPath, envFilePath);

        // Reload the system daemon
        let command = ['sudo', 'systemctl', 'daemon-reload'];
        let state = useSpawn(command, { superuser: 'try' });
        await state.promise();
    }

    async updateTaskNotes(taskInstance) {
        await this.ensureBackend();
        //populate data from env file and then delete + recreate task files
        const templateName = formatTemplateName(taskInstance.template.name);

        // --- DAEMON
        if (this.isDaemon()) {
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

            await daemon.createTask(templateName, envObject, scriptPath, taskInstance.schedule, taskInstance.notes ?? '', 'auto');
            return;
        }


        // === LEGACY path  ===
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const notesFilePath = `/etc/systemd/system/${houstonSchedulerPrefix}${templateName}_${taskInstance.name}.txt`;

        console.log('notesFilePath:', notesFilePath);

        const file = new BetterCockpitFile(notesFilePath, {
            superuser: 'try',
        });

        file.replace(taskInstance.notes).then(() => {
            console.log('notes file updated successfully');
            file.close();
        }).catch(error => {
            console.error("Error updating file:", error);
            file.close();
        });

        // Reload the system daemon
        let command = ['sudo', 'systemctl', 'daemon-reload'];
        let state = useSpawn(command, { superuser: 'try' });
        await state.promise();
    }

    async unregisterTaskInstance(taskInstance: TaskInstanceType) {
        await this.ensureBackend();
        //delete task + associated files
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);

        if (this.backend === 'daemon') {
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
    
    async runTaskNow(taskInstance: TaskInstanceType) {
        await this.ensureBackend();
        //execute service file now
        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);

        if (this.backend === 'daemon') {
            await daemon.runNow(templateName, taskInstance.name);
            return;
        }


        // === LEGACY path  ===
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        console.log(`Running ${fullTaskName}...`);
        await runTask(fullTaskName);
        console.log(`Task ${fullTaskName} completed.`);
        // return TaskExecutionResult;
    }

    async getTimerStatus(ti: TaskInstanceType): Promise<string | false> {
        await this.ensureBackend();
        const log = new TaskExecutionLog([]);
        const tplKey = this.templateKey(ti, formatTemplateName(ti.template.name));

        if (this.isDaemon()) {
            try {
                const st: any = await daemon.getStatus(tplKey, ti.name);
                const unit = String(st?.unit || await this.unitNameFor(ti));     // <— NEW
                const output = String(st?.timer || '');
                return this.parseTaskStatus(output, unit, log, ti);
            } catch (e) {
                console.warn('GetStatus(timer) failed:', e);
                return false;
            }
        }

        // Legacy / direct systemctl path
        const unit = await this.unitNameFor(ti);                              // <— NEW
        try {
            const state = useSpawn(
                ['systemctl', 'show', `${unit}.timer`, '--no-pager',
                    '--property', 'LoadState,ActiveState,SubState,Result,ActiveEnterTimestamp,MergedUnit'],
                { superuser: 'try' }
            );
            const res: any = await state.promise();
            return this.parseTaskStatus(res.stdout || '', unit, log, ti);
        } catch (e: any) {
            const stdout = e?.stdout ?? '';
            const stderr = e?.stderr ?? '';
            if (/not found/i.test(stderr) || /LoadState=not-found/.test(stdout)) {
                return this.parseTaskStatus('', unit, log, ti);
            }
            console.warn(`getTimerStatus(${unit}):`, (legacy?.errorString?.(e) ?? e));
            return false;
        }
    }


    async getServiceStatus(ti: TaskInstanceType): Promise<string | false> {
        await this.ensureBackend();
        const log = new TaskExecutionLog([]);
        const tplKey = this.templateKey(ti, formatTemplateName(ti.template.name));

        if (this.isDaemon()) {
            try {
                const st: any = await daemon.getStatus(tplKey, ti.name);
                const unit = String(st?.unit || await this.unitNameFor(ti));      // <— NEW
                const output = String(st?.service || '');
                return this.parseTaskStatus(output, unit, log, ti);
            } catch {
                const unit = await this.unitNameFor(ti);                          // <— NEW
                return this.parseTaskStatus('', unit, log, ti);
            }
        }

        // Legacy / direct systemctl path
        const unit = await this.unitNameFor(ti);                              // <— NEW
        try {
            const state = useSpawn(
                ['systemctl', 'show', `${unit}.service`, '--no-pager',
                    '--property', 'LoadState,ActiveState,SubState,Result,ActiveEnterTimestamp,MergedUnit'],
                { superuser: 'try' }
            );
            const res: any = await state.promise();
            return this.parseTaskStatus(res.stdout || '', unit, log, ti);
        } catch (e: any) {
            const stdout = e?.stdout ?? '';
            const stderr = e?.stderr ?? '';
            if (/not found/i.test(stderr) || /LoadState=not-found/.test(stdout)) {
                return this.parseTaskStatus('', unit, log, ti);
            }
            console.warn(`getServiceStatus(${unit}):`, (legacy?.errorString?.(e) ?? e));
            return false;
        }
    }


    private parseShow(output: string) {
        const m = new Map<string, string>();
        for (const line of (output || '').split(/\r?\n/)) {
            const i = line.indexOf('=');
            if (i > 0) m.set(line.slice(0, i), line.slice(i + 1));
        }
        // normalize a few fields we care about
        return {
            load: m.get('LoadState') || '',
            active: m.get('ActiveState') || '',
            sub: m.get('SubState') || '',
            result: m.get('Result') || '',
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
                    let recentlyCompleted = false;
                    try {
                        // IMPORTANT: the log helper must use system journal for system-scope units
                        // and user journal for user-scope units. If it doesn't, it will fail under root.
                        recentlyCompleted = await log.wasTaskRecentlyCompleted(ti);
                    } catch (_) {
                        // swallow — don’t turn a harmless lookup into a UI error
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

                    // 🔽 Add this guard so a failed journal probe never becomes a UI error
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


    async enableSchedule(taskInstance) {
        await this.ensureBackend();
        if (this.backend === 'daemon') {
            await daemon.enableSchedule(formatTemplateName(taskInstance.template.name), taskInstance.name, true);
            taskInstance.schedule.enabled = true;
            return;
        }

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        const timerName = `${fullTaskName}.timer`;
        try {
            // Reload the system daemon
            let command = ['sudo', 'systemctl', 'daemon-reload'];
            let state = useSpawn(command, { superuser: 'try' });
            await state.promise();

            // Start and Enable the timer
            command = ['sudo', 'systemctl', 'enable', timerName];
            state = useSpawn(command, { superuser: 'try' });
            await state.promise();

            console.log(`${timerName} has been enabled and started`);
            taskInstance.schedule.enabled = true;
          //  console.log('taskInstance after enable:', taskInstance);
            await this.updateSchedule(taskInstance);
        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }

    async disableSchedule(taskInstance) {
        await this.ensureBackend();
        if (this.backend === 'daemon') {
            await daemon.enableSchedule(formatTemplateName(taskInstance.template.name), taskInstance.name, false);
            taskInstance.schedule.enabled = false;
            return;
        }

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const templateName = formatTemplateName(taskInstance.template.name);
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;

        const timerName = `${fullTaskName}.timer`;
        try {
            // Reload systemd daemon
            let reloadCommand = ['sudo', 'systemctl', 'daemon-reload'];
            let reloadState = useSpawn(reloadCommand, { superuser: 'try' });
            await reloadState.promise();

            // Stop and Disable the timer
            let stopCommand = ['sudo', 'systemctl', 'stop', timerName];
            let stopState = useSpawn(stopCommand, { superuser: 'try' });
            await stopState.promise();


            let disableCommand = ['sudo', 'systemctl', 'disable', timerName];
            let disableState = useSpawn(disableCommand, { superuser: 'try' });
            await disableState.promise();
    
            console.log(`${timerName} has been stopped and disabled`);
            taskInstance.schedule.enabled = false;
          //  console.log('taskInstance after disable:', taskInstance);


            await this.updateSchedule(taskInstance);

        } catch (error) {
            console.error(errorString(error));
            return false;
        }
    }

    async updateSchedule(taskInstance) {
        await this.ensureBackend();
        const templateName = formatTemplateName(taskInstance.template.name);

        if (this.backend === 'daemon') {
            const envKeyValues = taskInstance.parameters.asEnvKeyValues();
            const envObject = this.parseEnvKeyValues(envKeyValues, templateName);
            envObject['taskName'] = taskInstance.name;

            const scriptFileName = this.getScriptFromTemplateName(templateName);
            const scriptPath = `/opt/45drives/houston/scheduler/scripts/${scriptFileName}.py`;

            const scheduleForDbus = this.toPlain(taskInstance.schedule);
            await daemon.createTask(templateName, envObject, scriptPath, scheduleForDbus, taskInstance.notes ?? '', 'auto');
            await daemon.enableSchedule(templateName, taskInstance.name, !!taskInstance.schedule.enabled);
            return;
        }

        const templateTimerPath = `/opt/45drives/houston/scheduler/templates/Schedule.timer`;

        const houstonSchedulerPrefix = 'houston_scheduler_';
        const fullTaskName = `${houstonSchedulerPrefix}${templateName}_${taskInstance.name}`;
        const jsonFilePath = `/etc/systemd/system/${fullTaskName}.json`;
      //  console.log('jsonFilePath:', jsonFilePath);

        const file = new BetterCockpitFile(jsonFilePath, {
            superuser: 'try',
        });

        const jsonString = JSON.stringify(taskInstance.schedule, null, 2);

        file.replace(jsonString).then(() => {
            console.log('json file created and content written successfully');
            file.close();
        }).catch(error => {
            console.error("Error writing content to the file:", error);
            file.close();
        });

        if (taskInstance.schedule.enabled) {
            await createScheduleForTask(fullTaskName, templateTimerPath, jsonFilePath);

            // Reload the system daemon
            let command = ['sudo', 'systemctl', 'daemon-reload'];
            let state = useSpawn(command, { superuser: 'try' });
            await state.promise();

            command = ['sudo', 'systemctl', 'restart', fullTaskName + '.timer'];
            state = useSpawn(command, { superuser: 'try' });
            await state.promise();
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
