#!/usr/bin/env node
/**
 * Checks the pure parsers in systemdParsing.ts. Node strips the types, so this
 * runs against shipping source with no build step.
 *
 * The .lastrun marker is a cross-language contract: task_lastrun.py writes it and
 * parseLastRunMarker reads it. pytest covers the writer; this covers the reader.
 *
 * Usage: node tests/parser-harness.mjs
 */

import { parseSystemdTimestampUSec, parseLastRunMarker, pairRunTimestamps, isUnitRunning, parseRestartCount } from '../scheduler/src/models/systemdParsing.ts';

let failures = 0;
function check(label, actual, expected) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a === e) {
        console.log(`  ok    ${label}`);
    } else {
        failures++;
        console.log(`  FAIL  ${label}\n          expected ${e}\n          actual   ${a}`);
    }
}

// Expectations are written as the UTC instant the local wall time refers to, so
// they stay independent of the offset table being verified.
const us = (ms) => ms * 1000;

console.log('\nsystemd timestamp parsing');
check('raw microseconds pass through', parseSystemdTimestampUSec('1789488167000000'), 1789488167000000);
check('"0" is not year 2000', parseSystemdTimestampUSec('0'), 0);
check('negative is clamped', parseSystemdTimestampUSec('-5'), 0);
check('empty string', parseSystemdTimestampUSec(''), 0);
check('undefined', parseSystemdTimestampUSec(undefined), 0);
check('"n/a"', parseSystemdTimestampUSec('n/a'), 0);
check('unknown zone abbreviation', parseSystemdTimestampUSec('Tue 2026-09-15 12:02:47 XYZ'), 0);

console.log('\nzone abbreviations systemd emits');
check('ADT (UTC-3)', parseSystemdTimestampUSec('Tue 2026-09-15 12:02:47 ADT'), us(Date.UTC(2026, 8, 15, 15, 2, 47)));
check('AST (UTC-4)', parseSystemdTimestampUSec('Tue 2026-01-15 12:02:47 AST'), us(Date.UTC(2026, 0, 15, 16, 2, 47)));
check('NDT (UTC-2.5)', parseSystemdTimestampUSec('Tue 2026-09-15 12:02:47 NDT'), us(Date.UTC(2026, 8, 15, 14, 32, 47)));
check('NST (UTC-3.5)', parseSystemdTimestampUSec('Tue 2026-01-15 12:02:47 NST'), us(Date.UTC(2026, 0, 15, 15, 32, 47)));
check('EDT (UTC-4)', parseSystemdTimestampUSec('Tue 2026-09-15 12:02:47 EDT'), us(Date.UTC(2026, 8, 15, 16, 2, 47)));
check('UTC', parseSystemdTimestampUSec('Tue 2026-09-15 12:02:47 UTC'), us(Date.UTC(2026, 8, 15, 12, 2, 47)));
check('weekday prefix is optional', parseSystemdTimestampUSec('2026-09-15 12:02:47 ADT'), us(Date.UTC(2026, 8, 15, 15, 2, 47)));

console.log('\n.lastrun marker parsing');
check('success marker', parseLastRunMarker('1789488167 success'), { ms: 1789488167000, outcome: 'success' });
check('failed marker', parseLastRunMarker('1789488167 failed'), { ms: 1789488167000, outcome: 'failed' });
check('outcome is lowercased', parseLastRunMarker('1789488167 FAILED'), { ms: 1789488167000, outcome: 'failed' });
check('legacy bare epoch means unknown', parseLastRunMarker('1789488167'), { ms: 1789488167000, outcome: '' });
check('trailing newline tolerated', parseLastRunMarker('1789488167 success\n'), { ms: 1789488167000, outcome: 'success' });
check('empty marker', parseLastRunMarker(''), { ms: 0, outcome: '' });
check('garbage marker', parseLastRunMarker('not-a-number success'), { ms: 0, outcome: '' });
check('zero epoch', parseLastRunMarker('0 success'), { ms: 0, outcome: '' });

console.log('\nrun timestamp pairing');
check('ExecMain pair is preferred', pairRunTimestamps({
    ExecMainStartTimestamp: 'Fri 2026-09-18 17:50:30 UTC',
    ExecMainExitTimestamp: 'Fri 2026-09-18 18:50:19 UTC',
    ActiveEnterTimestamp: 'Fri 2026-09-18 17:50:31 UTC',
    InactiveEnterTimestamp: 'Fri 2026-09-18 18:50:20 UTC',
}, false), { startTime: 'Fri 2026-09-18 17:50:30 UTC', cycleStartTime: '', finishTime: 'Fri 2026-09-18 18:50:19 UTC' });
check('stale InactiveEnter is never paired with a newer ExecMainStart', pairRunTimestamps({
    ExecMainStartTimestamp: 'Fri 2026-09-18 18:50:30 UTC',
    ExecMainExitTimestamp: '',
    InactiveEnterTimestamp: 'Fri 2026-09-18 18:50:19 UTC',
}, false), { startTime: 'Fri 2026-09-18 18:50:30 UTC', cycleStartTime: '', finishTime: '' });
check('running unit reports no finish', pairRunTimestamps({
    ExecMainStartTimestamp: 'Fri 2026-09-18 18:50:30 UTC',
    ExecMainExitTimestamp: 'Fri 2026-09-18 18:50:19 UTC',
}, true), { startTime: 'Fri 2026-09-18 18:50:30 UTC', cycleStartTime: '', finishTime: '' });
check('falls back to the ActiveEnter pair as a unit', pairRunTimestamps({
    ActiveEnterTimestamp: 'Fri 2026-09-18 18:12:00 UTC',
    InactiveEnterTimestamp: 'Fri 2026-09-18 19:11:39 UTC',
}, false), { startTime: 'Fri 2026-09-18 18:12:00 UTC', cycleStartTime: '', finishTime: 'Fri 2026-09-18 19:11:39 UTC' });
check('never run', pairRunTimestamps({}, false), { startTime: '', cycleStartTime: '', finishTime: '' });
check('active is running', isUnitRunning('active'), true);
check('activating is running', isUnitRunning('activating'), true);
check('failed is not running', isUnitRunning('failed'), false);
check('missing state is not running', isUnitRunning(undefined), false);

console.log('\nrun cycle start (survives Restart=on-failure)');
check('cycle start spans retries', pairRunTimestamps({
    InactiveExitTimestamp: 'Fri 2026-09-18 12:00:00 UTC',
    ExecMainStartTimestamp: 'Fri 2026-09-18 18:50:30 UTC',
    ExecMainExitTimestamp: 'Fri 2026-09-18 19:11:39 UTC',
}, false), {
    startTime: 'Fri 2026-09-18 18:50:30 UTC',
    cycleStartTime: 'Fri 2026-09-18 12:00:00 UTC',
    finishTime: 'Fri 2026-09-18 19:11:39 UTC',
});
check('cycle start after attempt start is discarded', pairRunTimestamps({
    InactiveExitTimestamp: 'Fri 2026-09-18 19:00:00 UTC',
    ExecMainStartTimestamp: 'Fri 2026-09-18 18:50:30 UTC',
    ExecMainExitTimestamp: 'Fri 2026-09-18 19:11:39 UTC',
}, false).cycleStartTime, '');
check('no restarts', parseRestartCount('0'), 0);
check('two restarts', parseRestartCount('2'), 2);
check('missing NRestarts', parseRestartCount(undefined), 0);
check('garbage NRestarts', parseRestartCount('n/a'), 0);

console.log(failures ? `\n${failures} failure(s)\n` : '\nall checks passed\n');
process.exit(failures ? 1 : 0);
