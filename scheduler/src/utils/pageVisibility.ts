/**
 * Cockpit hides an inactive page's iframe rather than destroying it, so
 * `onUnmounted` never fires and any running timer keeps spawning bridge
 * commands for a page nobody is looking at. `cockpit.hidden` is the shell's
 * own signal for that state.
 */
export function isPageHidden(): boolean {
    const c: any = (globalThis as any).cockpit;
    if (c && typeof c.hidden === 'boolean') return c.hidden;
    return typeof document !== 'undefined' && document.hidden === true;
}

/** Subscribe to Cockpit's visibility signal. Returns an unsubscribe function. */
export function onPageVisibilityChange(fn: (hidden: boolean) => void): () => void {
    const c: any = (globalThis as any).cockpit;
    const handler = () => fn(isPageHidden());

    if (c && typeof c.addEventListener === 'function') {
        c.addEventListener('visibilitychange', handler);
        return () => c.removeEventListener('visibilitychange', handler);
    }

    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
}
