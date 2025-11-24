declare const cockpit: any;
export type Backend = 'daemon' | 'legacy';

export interface BackendChoice {
    backend: Backend;
    isRoot: boolean;
}

export async function chooseBackend(): Promise<BackendChoice> {
    // Always prefer the daemon if it responds
    try {
        const bus = cockpit.dbus('org.houston.Scheduler', { bus: 'system' });
        await bus.call('/org/houston/Scheduler', 'org.houston.Scheduler1', 'GetCapabilities', []);

        const u = await cockpit.user();
        const isRoot = (u?.id === 0 || u?.name === 'root');
        if (isRoot) {
            return { backend: 'legacy', isRoot: true };
        }

        return { backend: 'daemon', isRoot: false };
    } catch (e) {
        console.warn('daemon probe failed:', e);
    }

    // Fallback to legacy ONLY if daemon is unavailable
    const u = await cockpit.user();
    const isRoot = (u?.id === 0 || u?.name === 'root');
    return { backend: 'legacy', isRoot };
}