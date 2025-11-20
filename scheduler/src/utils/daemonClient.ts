import { chooseBackend } from "./bootstrapBackend";

declare const cockpit: any;

export async function probeDaemon(): Promise<boolean> {
    try {
        const u = await cockpit.user();
        if (u?.id === 0 || u?.name === 'root') return false;

        const bus = cockpit.dbus('org.houston.Scheduler', { bus: 'system' });
        await bus.call('/org/houston/Scheduler', 'org.houston.Scheduler1', 'GetCapabilities', []);
        return true;
    } catch {
        return false;
    }
}

export const daemon = {
    call(method: string, args: any[] = []) {
        const bus = cockpit.dbus('org.houston.Scheduler', { bus: 'system' });
        return bus.call('/org/houston/Scheduler', 'org.houston.Scheduler1', method, args);
    },
    createTask: (tpl, env, script, schedule, notes = '', run_as = 'auto') =>
        daemon.call('CreateTask', [tpl, env, script, JSON.stringify(schedule || {}), notes, run_as]),
    updateTask: (tpl, oldName, env, script, schedule, notes = '', run_as = 'auto') =>
        daemon.call('UpdateTask', [tpl, oldName, env, script, JSON.stringify(schedule || {}), notes, run_as]),
    runNow: (tpl: string, name: string) =>
        daemon.call('RunNow', [tpl, name]),
    enableSchedule: (tpl: string, name: string, enabled: boolean) =>
        daemon.call('EnableSchedule', [tpl, name, enabled ? 'true' : 'false']),
    deleteTask: (tpl: string, name: string) =>
        daemon.call('DeleteTask', [tpl, name]),
    listTasks: (scope: 'user' | 'system') =>
        daemon.call('ListTasks', [scope]),
    listClientBackupFolders: () =>
        daemon.call('ListClientBackupFolders', []),
    getStatus: (tpl: string, name: string) =>
        daemon.call('GetStatus', [tpl, name]) // returns { scope, unit, service, timer }
};