import { logToClient, setClientLogModule, type ClientLogLevel } from '@45drives/houston-common-lib';

setClientLogModule('scheduler');

const SENSITIVE_ENV = /pass|secret|token|_key$/i;

function envMap(task: any): Record<string, string> {
    const out: Record<string, string> = {};
    try {
        for (const pair of task?.parameters?.asEnvKeyValues?.() ?? []) {
            const idx = String(pair).indexOf('=');
            if (idx <= 0) continue;
            out[String(pair).slice(0, idx)] = String(pair).slice(idx + 1);
        }
    } catch {
        /* malformed parameter tree — the description degrades to the template name */
    }
    return out;
}

export interface TaskTargetSummary {
    /** "local" when nothing leaves this machine. */
    kind: 'rsync' | 'zfs-replication' | 'cloud' | 'local';
    remoteHost?: string;
    remote?: string;
    source?: string;
    destination?: string;
    /** True when the remote is reached over a WireShield tunnel address. */
    viaVpn?: boolean;
    summary: string;
}

/** WireShield hands out 10.44.0.0/16 tunnel addresses. */
function isTunnelAddress(host?: string): boolean {
    return !!host && /^10\.44\./.test(host);
}

function zfsEndpoint(env: Record<string, string>, prefix: string): { host: string; text: string } {
    const host = env[`${prefix}_host`] || '';
    const user = env[`${prefix}_user`] || 'root';
    const pool = env[`${prefix}_pool`] || '';
    const dataset = env[`${prefix}_dataset`] || '';
    const path = pool && dataset ? `${pool}/${dataset}` : pool || dataset;
    return { host, text: host ? `${user}@${host}:${path}` : path };
}

/** Describes where a task sends data, for the client-side log viewer. */
export function describeTaskTarget(task: any): TaskTargetSummary {
    const template = task?.template?.name ?? '';
    const env = envMap(task);

    if (template === 'Rsync Task') {
        const host = env['rsyncConfig_target_info_host'] || '';
        const user = env['rsyncConfig_target_info_user'] || 'root';
        const remotePath = env['rsyncConfig_target_info_path'] || '';
        const localPath = env['rsyncConfig_local_path'] || '';
        const pull = (env['rsyncConfig_direction'] || 'push') === 'pull';
        const remote = `${user}@${host}:${remotePath}`;
        return {
            kind: host ? 'rsync' : 'local',
            remoteHost: host || undefined,
            source: pull ? remote : localPath,
            destination: pull ? localPath : remote,
            viaVpn: isTunnelAddress(host),
            summary: pull
                ? `rsync pull from ${remote} into ${localPath}`
                : `rsync push from ${localPath} to ${remote}`,
        };
    }

    if (template === 'ZFS Replication Task') {
        const src = zfsEndpoint(env, 'zfsRepConfig_sourceDataset');
        const dst = zfsEndpoint(env, 'zfsRepConfig_destDataset');
        const remoteHost = dst.host || src.host;
        return {
            kind: remoteHost ? 'zfs-replication' : 'local',
            remoteHost: remoteHost || undefined,
            source: src.text,
            destination: dst.text,
            viaVpn: isTunnelAddress(remoteHost),
            summary: `ZFS replication from ${src.text} to ${dst.text}`,
        };
    }

    if (template === 'Cloud Sync Task') {
        const remoteName = env['cloudSyncConfig_rclone_remote'] || '';
        const provider = env['cloudSyncConfig_provider'] || '';
        const localPath = env['cloudSyncConfig_local_path'] || '';
        const targetPath = env['cloudSyncConfig_target_path'] || '';
        const pull = (env['cloudSyncConfig_direction'] || 'push') === 'pull';
        const remote = `${remoteName}:${targetPath}`;
        return {
            kind: 'cloud',
            remote: remoteName || undefined,
            source: pull ? remote : localPath,
            destination: pull ? localPath : remote,
            summary: pull
                ? `cloud sync pull from ${remote} (${provider}) into ${localPath}`
                : `cloud sync push from ${localPath} to ${remote} (${provider})`,
        };
    }

    return { kind: 'local', summary: template || 'task' };
}

function scheduleSummary(task: any): string | undefined {
    const intervals = task?.schedule?.intervals;
    if (!Array.isArray(intervals) || intervals.length === 0) return undefined;
    return `${intervals.length} interval(s)`;
}

/** Emits a scheduler event to the desktop client's log viewer. */
export function logTaskEvent(
    event: string,
    task: any,
    extra: Record<string, unknown> = {},
    level: ClientLogLevel = 'info'
): void {
    const target = describeTaskTarget(task);
    const safeEnv = Object.fromEntries(
        Object.entries(envMap(task)).filter(([k, v]) => v !== '' && !SENSITIVE_ENV.test(k))
    );

    logToClient(
        event,
        {
            task: task?.name ?? '',
            template: task?.template?.name ?? '',
            targetKind: target.kind,
            remoteHost: target.remoteHost,
            remote: target.remote,
            source: target.source,
            destination: target.destination,
            viaVpn: target.viaVpn,
            schedule: scheduleSummary(task),
            parameters: safeEnv,
            ...extra,
        },
        level,
        `${task?.name ?? 'task'} — ${target.summary}`
    );
}

export { logToClient };
