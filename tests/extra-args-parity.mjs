#!/usr/bin/env node
/**
 * Prints the form's verdict for each extra-zfs-args case, so pytest can hold the UI and
 * replication/planner.py to the same answers. Node strips the types; no build step.
 *
 * stdin:  [{"field": "send"|"recv", "text": "...", "recursive": bool, "raw": bool, "compressed": bool}, ...]
 * stdout: [null | "problem message", ...]   (same order)
 *
 * Usage: driven by tests/test_extra_args_matrix.py
 */

import { extraRecvArgsProblem, extraSendArgsProblem } from '../scheduler/src/models/ZfsExtraArgs.ts';

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const cases = JSON.parse(Buffer.concat(chunks).toString('utf8'));

const verdicts = cases.map(({ field, text, recursive, raw, compressed }) =>
    field === 'send' ? extraSendArgsProblem(text, !!recursive, !!raw, !!compressed) : extraRecvArgsProblem(text)
);
process.stdout.write(JSON.stringify(verdicts));
