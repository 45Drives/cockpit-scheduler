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
 * Pick a start/stop pair that belongs to the same run.
 *
 * ExecMain* and Active/InactiveEnter* advance on different edges: systemd clears
 * ExecMainExitTimestamp the moment a new main process is forked, while
 * InactiveEnterTimestamp keeps the *previous* cycle's value until the unit goes
 * inactive again. Reading the start from one family and the stop from the other
 * therefore pairs the current run's start with the previous run's stop, which
 * renders as a negative duration.
 *
 * `cycleStartTime` comes from InactiveExitTimestamp, which marks when the unit
 * left inactive. Restart=on-failure retries go active → deactivating →
 * activating/auto-restart without passing through inactive, so it survives them
 * while ExecMainStartTimestamp resets on each attempt. It is therefore the true
 * beginning of the whole run, and unlike the timer's LastTrigger it is also
 * correct for manual starts.
 */
export function pairRunTimestamps(
    kv: Record<string, string | undefined>,
    isRunning: boolean
): { startTime: string; cycleStartTime: string; finishTime: string } {
    const get = (key: string) => (kv[key] || '').trim();
    const execStart = get('ExecMainStartTimestamp');
    const execExit = get('ExecMainExitTimestamp');

    let startTime = execStart;
    let finishTime = execExit;

    if (!startTime && !finishTime) {
        startTime = get('ActiveEnterTimestamp');
        finishTime = get('InactiveEnterTimestamp');
    } else if (!startTime) {
        startTime = get('ActiveEnterTimestamp');
    }

    // A live run has no stop time yet; anything on file belongs to an older cycle.
    if (isRunning) finishTime = '';

    const startUs = parseSystemdTimestampUSec(startTime);
    const finishUs = parseSystemdTimestampUSec(finishTime);
    if (startUs && finishUs && finishUs < startUs) finishTime = '';

    let cycleStartTime = get('InactiveExitTimestamp');
    const cycleStartUs = parseSystemdTimestampUSec(cycleStartTime);
    if (cycleStartUs && startUs && cycleStartUs > startUs) cycleStartTime = '';

    return { startTime, cycleStartTime, finishTime };
}

/** systemd states in which the unit's main process may still be alive. */
export function isUnitRunning(activeState: string | undefined): boolean {
    const state = (activeState || '').trim().toLowerCase();
    return state === 'active' || state === 'activating' || state === 'reloading';
}

/** NRestarts counts auto-restarts within the current start cycle; systemd clears it on every explicit start. */
export function parseRestartCount(raw: string | undefined): number {
    const n = Number((raw || '').trim());
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
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
