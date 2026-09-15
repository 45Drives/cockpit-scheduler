// Kept free of imports so tests can load this module without a build step.

// Date.parse rejects the abbreviations systemd emits outside the US zones.
const TZ_OFFSET_HOURS: Record<string, number> = {
    UTC: 0, GMT: 0, EST: -5, EDT: -4, CST: -6, CDT: -5, MST: -7, MDT: -6,
    PST: -8, PDT: -7, AST: -4, ADT: -3, NST: -3.5, NDT: -2.5,
};

/**
 * systemd renders *USec properties as raw microseconds on some versions and as
 * a formatted timestamp ("Tue 2026-09-15 11:00:00 EDT") on others. Returns µs.
 */
export function parseSystemdTimestampUSec(raw: string | undefined): number {
    if (!raw) return 0;
    const value = raw.trim();
    if (!value) return 0;

    // Check numeric first: Date.parse("0") would otherwise yield the year 2000.
    const asNumber = Number(value);
    if (Number.isFinite(asNumber)) return asNumber > 0 ? asNumber : 0;

    const native = Date.parse(value);
    if (Number.isFinite(native)) return native * 1000;

    const m = value.match(/^(?:\w{3}\s+)?(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\s+([A-Z]{2,4})$/);
    if (!m) return 0;
    const offsetHours = TZ_OFFSET_HOURS[m[7]];
    if (typeof offsetHours !== 'number') return 0;
    const utcMs = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) - offsetHours * 3600_000;
    return Number.isFinite(utcMs) ? utcMs * 1000 : 0;
}

/**
 * The `.lastrun` marker holds "<epoch> <outcome>", written by task_lastrun.py.
 * Markers predating the outcome field hold a bare epoch, so a missing outcome
 * means "unknown" rather than failure.
 */
export function parseLastRunMarker(raw: string | undefined): { ms: number; outcome: string } {
    const [epochToken, outcomeToken] = (raw || '').trim().split(/\s+/);
    const epoch = parseInt(epochToken, 10);
    if (!Number.isFinite(epoch) || epoch <= 0) return { ms: 0, outcome: '' };
    return { ms: epoch * 1000, outcome: (outcomeToken || '').toLowerCase() };
}
