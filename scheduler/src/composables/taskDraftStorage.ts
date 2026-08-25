const DRAFT_KEY = 'scheduler-task-draft';
const VPN_HOST_KEY = 'scheduler-vpn-host';
const SESSION_KEY = 'scheduler-draft-session';
const DRAFT_MAX_AGE_MS = 60 * 60 * 1000;

function read(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
}

/** Returns the stored draft, discarding it first if it is stale or corrupt. */
export function readSavedDraft(): any | null {
    const raw = read(DRAFT_KEY);
    if (!raw) return null;
    try {
        const draft = JSON.parse(raw);
        if ((draft?._savedAt || 0) > Date.now() - DRAFT_MAX_AGE_MS) return draft;
    } catch { /* corrupt draft, fall through to removal */ }
    try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
    return null;
}

export function hasSavedDraft(): boolean {
    return !!readSavedDraft() || !!read(VPN_HOST_KEY);
}

export function saveDraft(snapshot: Record<string, unknown>): void {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ ...snapshot, _savedAt: Date.now() })); } catch { /* ignore */ }
}

/** Reads and consumes the one-shot host handed over by WireShield. */
export function takeVpnHost(): string | null {
    const host = read(VPN_HOST_KEY);
    if (host) {
        try { localStorage.removeItem(VPN_HOST_KEY); } catch { /* ignore */ }
    }
    return host;
}

/**
 * Flags the stored draft as part of the current browsing session (a WireShield
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
