// A task's systemd exit status is the wrapper script's status (almost always 1), so it says
// nothing about what actually went wrong. The real cause is one line buried in the journal.
// These helpers lift that line out so notifications and the log view can name the failure.

export interface TaskFailureReason {
	/** Plain-language cause, short enough for a notification body. */
	summary: string;
	/** The log line the summary was derived from. */
	detail?: string;
}

const SIGNATURES: { pattern: RegExp; summary: string }[] = [
	// Capacity
	{ pattern: /no space left on device/i, summary: 'The destination ran out of disk space.' },
	{ pattern: /disk quota exceeded/i, summary: 'The destination disk quota was exceeded.' },
	{ pattern: /read-only file system/i, summary: 'The destination is mounted read-only.' },
	{ pattern: /out of space|would exceed (?:the )?quota|storage quota (?:exceeded|reached)/i, summary: 'The destination is out of available space or quota.' },

	// Connectivity / SSH
	{ pattern: /host key verification failed/i, summary: 'SSH host key verification failed for the destination server.' },
	{ pattern: /permission denied \(publickey/i, summary: 'The destination server rejected the SSH key.' },
	{ pattern: /connection refused/i, summary: 'The destination server refused the connection.' },
	{ pattern: /connection timed out|operation timed out|timed out waiting for/i, summary: 'The connection to the destination server timed out.' },
	{ pattern: /no route to host|network is unreachable|could not resolve hostname|name or service not known/i, summary: 'The destination server could not be reached.' },
	{ pattern: /connection (?:closed|reset) by/i, summary: 'The destination server closed the connection unexpectedly.' },

	// Paths / permissions
	{ pattern: /change_dir .*failed: no such file or directory/i, summary: 'The source folder no longer exists.' },
	{ pattern: /(?:mkdir|opendir|link_stat|send_files|write failed on|failed to open).*permission denied/i, summary: 'Permission was denied while reading or writing files.' },
	{ pattern: /permission denied/i, summary: 'Permission was denied.' },
	{ pattern: /no such file or directory/i, summary: 'A file or folder in the transfer no longer exists.' },

	// ZFS replication
	{ pattern: /dataset does not exist/i, summary: 'The ZFS dataset does not exist.' },
	{ pattern: /destination .*has been modified/i, summary: 'The destination dataset changed since the last run, so the incremental send was refused.' },
	{ pattern: /could not find any snapshots to send|no snapshots? (?:found|to send)/i, summary: 'There were no snapshots available to replicate.' },
	{ pattern: /pool i\/o failure|cannot receive/i, summary: 'The destination pool rejected the replication stream.' },

	// Cloud
	{ pattern: /401 unauthorized|403 forbidden|invalid credentials|authentication failed|accessdenied/i, summary: 'The cloud provider rejected the stored credentials.' },
	{ pattern: /didn't find section in config file|could not find remote|unknown remote/i, summary: 'The cloud remote is missing from the rclone configuration.' },
	{ pattern: /bucket .*does not exist|nosuchbucket/i, summary: 'The destination bucket does not exist.' },

	// Host health
	{ pattern: /out of memory|killed process|oom-killer/i, summary: 'The task was killed because the server ran out of memory.' },
	{ pattern: /input\/output error/i, summary: 'A disk I/O error occurred — the underlying storage may be failing.' },
];

// rsync's own status, printed by the wrapper script. systemd only ever sees the wrapper's.
const RSYNC_EXIT_CODES: Record<number, string> = {
	1: 'rsync reported a syntax or usage error.',
	2: 'rsync protocol incompatibility with the destination.',
	3: 'rsync could not select the requested files or directories.',
	5: 'rsync failed to start the client-server protocol.',
	10: 'rsync hit a socket I/O error.',
	11: 'rsync hit a file I/O error.',
	12: 'rsync hit an error in the data stream.',
	13: 'rsync reported an error with program diagnostics.',
	22: 'rsync failed to allocate memory.',
	23: 'Some files could not be transferred.',
	24: 'Some source files vanished before they could be copied.',
	30: 'rsync timed out sending or receiving data.',
	35: 'rsync timed out waiting for a connection.',
};

/**
 * Scan journal output for a recognizable cause of failure.
 * Returns null when nothing in the log is recognizable.
 */
export function describeTaskFailure(output: string | undefined | null): TaskFailureReason | null {
	const text = String(output || '');
	if (!text.trim()) return null;

	for (const { pattern, summary } of SIGNATURES) {
		const match = pattern.exec(text);
		if (match) return { summary, detail: lineContaining(text, match.index) };
	}

	const wrapped = /\b(rsync|rclone)\s+exited\s+with\s+code\s+(\d+)/i.exec(text);
	if (wrapped) {
		const code = Number(wrapped[2]);
		const summary = wrapped[1].toLowerCase() === 'rsync'
			? RSYNC_EXIT_CODES[code] ?? `rsync exited with code ${code}.`
			: `rclone exited with code ${code}.`;
		return { summary, detail: lineContaining(text, wrapped.index) };
	}

	return null;
}

/** Notification body: the cause when we can name it, the exit code when we can't. */
export function failureNotificationText(taskName: string, output: string | undefined | null, exitCode: number | null): string {
	const reason = describeTaskFailure(output);
	if (reason) return `Task ${taskName} failed: ${reason.summary}`;
	return exitCode !== null
		? `Task ${taskName} failed (exit code ${exitCode}). Open the task log for details.`
		: `Task ${taskName} failed. Open the task log for details.`;
}

function lineContaining(text: string, index: number): string {
	const start = text.lastIndexOf('\n', index) + 1;
	const end = text.indexOf('\n', index);
	return text.slice(start, end === -1 ? undefined : end).trim();
}
