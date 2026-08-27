const REOPEN_SETTINGS_KEY = 'scheduler-reopen-settings';

/** Set before jumping to another Cockpit module so the Settings modal reopens on return. */
export function markSettingsReturn(): void {
    try { sessionStorage.setItem(REOPEN_SETTINGS_KEY, '1'); } catch { /* ignore */ }
}

export function takeSettingsReturn(): boolean {
    try {
        const pending = sessionStorage.getItem(REOPEN_SETTINGS_KEY) === '1';
        if (pending) sessionStorage.removeItem(REOPEN_SETTINGS_KEY);
        return pending;
    } catch {
        return false;
    }
}

/** Cockpit path of this module, e.g. `/scheduler` — derived so packaging renames don't break links. */
export function schedulerModulePath(): string {
    const match = window.location.pathname.match(/\/([^/]+)\/[^/]*\.html$/);
    return match ? `/${match[1]}` : '/scheduler';
}
