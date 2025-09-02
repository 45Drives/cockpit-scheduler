declare const cockpit: any;
import { probeDaemon } from './daemonClient';

export type Backend = 'daemon' | 'legacy';

export async function chooseBackend(): Promise<{ backend: Backend; isRoot: boolean; }> {
    const u = await cockpit.user();                  // { id, name, ... }
    const isRoot = (u?.id === 0 || u?.name === 'root');
    const hasDaemon = await probeDaemon();
    return { backend: hasDaemon ? 'daemon' : 'legacy', isRoot };
}