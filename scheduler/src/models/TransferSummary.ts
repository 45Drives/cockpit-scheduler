/**
 * Parses the "===TASK_SUMMARY_START===...===TASK_SUMMARY_END===" block that
 * rsync-script.py, cloudsync-script.py, and the ZFS replication task print at
 * the end of a run (see system_files/.../scripts/transfer_summary.py). Journal
 * output can contain multiple runs concatenated together, so this always
 * reads the LAST block present.
 */
export interface TaskTransferSummary {
    status: string;
    started?: string;
    finished?: string;
    duration?: string;
    dataTransferred?: string;
    filesTransferred?: string;
    sendType?: string;
    direction?: string;
    snapshot?: string;
    waited?: string;
}

const SUMMARY_START = '===TASK_SUMMARY_START===';
const SUMMARY_END = '===TASK_SUMMARY_END===';

export function parseLatestTransferSummary(output: string): TaskTransferSummary | null {
    if (!output) return null;
    const startIdx = output.lastIndexOf(SUMMARY_START);
    if (startIdx === -1) return null;
    const endIdx = output.indexOf(SUMMARY_END, startIdx);
    if (endIdx === -1) return null;

    const block = output.slice(startIdx + SUMMARY_START.length, endIdx);
    const summary: TaskTransferSummary = { status: '' };

    for (const rawLine of block.split('\n')) {
        const line = rawLine.trim();
        if (!line) continue;
        const sepIdx = line.indexOf(':');
        if (sepIdx === -1) continue;
        const key = line.slice(0, sepIdx).trim();
        const value = line.slice(sepIdx + 1).trim();
        if (key === 'Status') summary.status = value;
        else if (key === 'Started') summary.started = value;
        else if (key === 'Finished') summary.finished = value;
        else if (key === 'Duration') summary.duration = value;
        else if (key === 'Data Transferred') summary.dataTransferred = value;
        else if (key === 'Files Transferred') summary.filesTransferred = value;
        else if (key === 'Send Type') summary.sendType = value;
        else if (key === 'Direction') summary.direction = value;
        else if (key === 'Snapshot') summary.snapshot = value;
        else if (key === 'Waited') summary.waited = value;
    }

    return summary.status ? summary : null;
}
