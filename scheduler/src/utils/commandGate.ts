import { server, unwrap, Command } from '@45drives/houston-common-lib';

/**
 * cockpit-bridge allocates a process plus stdin/stdout/stderr pipes for every
 * `cockpit.spawn()` channel, and runs under a 1024 soft FD limit shared by the
 * whole Cockpit session. Overlapping pollers used to open channels faster than
 * they closed, which surfaced as `OSError: [Errno 24] Too many open files`.
 *
 * Every command this module runs is funnelled through one FIFO semaphore so the
 * bridge can never see more than `MAX_CONCURRENT_COMMANDS` live channels from
 * the scheduler, no matter how many timers, rows or views are active.
 */
const MAX_CONCURRENT_COMMANDS = 6;

let active = 0;
let peakActive = 0;
const waiters: Array<() => void> = [];

function acquire(): Promise<void> {
    if (active < MAX_CONCURRENT_COMMANDS) {
        active++;
        peakActive = Math.max(peakActive, active);
        return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
        waiters.push(() => {
            active++;
            peakActive = Math.max(peakActive, active);
            resolve();
        });
    });
}

function release(): void {
    active = Math.max(0, active - 1);
    const next = waiters.shift();
    if (next) next();
}

/** Run `fn` while holding one of the bridge's command slots. */
export async function withCommandSlot<T>(fn: () => Promise<T>): Promise<T> {
    await acquire();
    try {
        return await fn();
    } finally {
        release();
    }
}

/** Diagnostics for the settings/debug panel. */
export function commandGateStats(): { active: number; queued: number; limit: number; peakActive: number } {
    return { active, queued: waiters.length, limit: MAX_CONCURRENT_COMMANDS, peakActive };
}

// Read-only hook so the gate can be watched from devtools during FD testing.
(globalThis as any).__schedulerCommandGate = commandGateStats;

const textDecoder = new TextDecoder('utf-8');

function decode(raw: any): string {
    if (raw instanceof Uint8Array) return textDecoder.decode(raw);
    return String(raw ?? '');
}

export type CommandOpts = {
    superuser?: 'try' | 'require';
    directory?: string;
    environ?: Record<string, string>;
};

export interface GatedCommandResult {
    stdout: string;
    stderr: string;
    exitStatus: number;
    proc: any;
}

/**
 * Spawn a command through the shared gate and wait for it to exit. The spawn is
 * only created once a slot is free, so queued work costs no file descriptors.
 */
export function execCommand(
    argv: string[],
    opts: CommandOpts = { superuser: 'try' },
    failIfNonZero: boolean = true
): Promise<GatedCommandResult> {
    return withCommandSlot(async () => {
        const proc: any = await unwrap(server.execute(new Command(argv, opts as any), failIfNonZero));
        return {
            stdout: decode(proc.stdout),
            stderr: typeof proc.stderr === 'string' ? proc.stderr : decode(proc.stderr),
            exitStatus: proc.exitStatus,
            proc,
        };
    });
}

/**
 * Gated equivalent of `server.spawnProcess()` for commands that need stdin.
 * The channel is always closed, including on the error path, so a failed write
 * or a rejected wait can't strand the bridge's pipes.
 */
export function execCommandWithStdin(
    argv: string[],
    stdin: string,
    opts: CommandOpts = { superuser: 'try' },
    failIfNonZero: boolean = false
): Promise<GatedCommandResult> {
    return withCommandSlot(async () => {
        const child = server.spawnProcess(new Command(argv, opts as any));
        try {
            child.write(new TextEncoder().encode(stdin), false);
            const proc: any = await unwrap(child.wait(failIfNonZero));
            return {
                stdout: decode(proc.stdout),
                stderr: typeof proc.stderr === 'string' ? proc.stderr : decode(proc.stderr),
                exitStatus: proc.exitStatus,
                proc,
            };
        } finally {
            try { child.close(); } catch { /* already reaped */ }
        }
    });
}
