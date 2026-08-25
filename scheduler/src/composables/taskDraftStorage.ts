const DRAFT_KEY = 'scheduler-task-draft';
const VPN_HOST_KEY = 'scheduler-vpn-host';
const SESSION_KEY = 'scheduler-draft-session';
const DRAFT_MAX_AGE_MS = 60 * 60 * 1000;

function read(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
}

/** Drops a stale/corrupt draft, then reports whether a usable one is still stored. */
export function hasSavedDraft(): boolean {
    const draftStr = read(DRAFT_KEY);
    if (draftStr) {
        try {
            const savedAt = JSON.parse(draftStr)._savedAt || 0;
            if (savedAt > Date.now() - DRAFT_MAX_AGE_MS) return true;
        } catch { /* corrupt draft, fall through to removal */ }
        try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
    }
    return !!read(VPN_HOST_KEY);
}

/**
 * Flags the stored draft as part of the current browsing session (a Wire Wizard
 * round trip). Session storage dies with the tab/webview, so a draft left over
 * from a previous run of the client app is never treated as an active round trip.
 */
export function markDraftSession(): void {
    try { sessionStorage.setItem(SESSION_KEY, '1'); } catch { /* ignore */ }
}

export function isDraftSessionActive(): boolean {
    try { return sessionStorage.getItem(SESSION_KEY) === '1'; } catch { return false; }
}

export function clearSavedDraft(): void {
    try {
        localStorage.removeItem(DRAFT_KEY);
        localStorage.removeItem(VPN_HOST_KEY);
        sessionStorage.removeItem(SESSION_KEY);
    } catch { /* ignore */ }
}
