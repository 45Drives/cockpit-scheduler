declare const cockpit: any;
import { probeDaemon } from './daemonClient';

export type Backend = 'daemon' | 'legacy';

export async function chooseBackend(): Promise<{ backend: Backend; isRoot: boolean }> {
    const u = await cockpit.user(); // { id, name, ... }
    const isRoot = (u?.id === 0 || u?.name === 'root');

    // If root, always use legacy regardless of daemon presence
    if (isRoot) {
        return { backend: 'legacy', isRoot };
    }

    const hasDaemon = await probeDaemon();
    return { backend: hasDaemon ? 'daemon' : 'legacy', isRoot };
}
