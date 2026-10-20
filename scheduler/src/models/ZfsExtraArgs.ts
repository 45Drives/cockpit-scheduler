// Mirrors EXTRA_SEND_FLAGS / EXTRA_RECV_FLAGS in replication/planner.py, which re-checks at run time.
// tests/extra-args-parity.mjs holds the two in agreement.
const EXTRA_SEND_FLAGS: Record<string, boolean> = {
    '-p': false, '--props': false, '-b': false, '--backup': false, '-h': false, '--holds': false,
    '-e': false, '--embed': false, '-L': false, '--large-block': false, '-c': false, '--compressed': false,
};
const EXTRA_RECV_FLAGS: Record<string, boolean> = { '-o': true, '-x': true, '-u': false, '-h': false };
const EXTRA_FLAG_ALIASES: Record<string, string> = {
    '--props': '-p', '--backup': '-b', '--holds': '-h',
    '--embed': '-e', '--large-block': '-L', '--compressed': '-c',
};
const EXTRA_ENCRYPTION_PROPS = ['encryption', 'keyformat', 'keylocation', 'pbkdf2iters'];

function extraValueProblem(flag: string, value: string): string | null {
    if (!value || value.startsWith('-')) return `${flag} needs a value`;
    const [prop, ...rest] = value.split('=');
    if (flag === '-o' && rest.length === 0) return `-o expects property=value, got "${value}"`;
    if (flag === '-x' && rest.length > 0) return `-x expects a property name, got "${value}"`;
    if (!prop) return `${flag} needs a property name`;
    if (prop === 'origin') return `${flag} origin is not allowed`;
    if (EXTRA_ENCRYPTION_PROPS.includes(prop)) return `${flag} ${prop} is not allowed; encryption settings can't be changed by a replication task`;
    if (prop.startsWith('com.45drives_scheduler:')) return `${flag} ${prop} is not allowed; the task relies on this property`;
    return null;
}

function extraArgsProblem(text: string, allowed: Record<string, boolean>): string | null {
    const trimmed = text.trim();
    if (!trimmed) return null;
    // Quotes and shell metacharacters would be mangled by the systemd env file.
    if (!/^[A-Za-z0-9 =._:\/@+,-]*$/.test(trimmed)) {
        return 'only letters, digits, spaces and = . _ : / @ + , - are allowed';
    }
    const seenFlags = new Set<string>();
    const propOwner = new Map<string, string>();
    const noteFlag = (flag: string): string | null => {
        const canonical = EXTRA_FLAG_ALIASES[flag] ?? flag;
        if (seenFlags.has(canonical)) return `${canonical} is given more than once`;
        seenFlags.add(canonical);
        return null;
    };
    const noteProp = (flag: string, value: string): string | null => {
        const prop = value.split('=')[0];
        const previous = propOwner.get(prop);
        if (previous === flag) return `property ${prop} is given more than once`;
        if (previous) return `property ${prop} can't be both set with -o and excluded with -x`;
        propOwner.set(prop, flag);
        return null;
    };
    const tokens = trimmed.split(/\s+/);
    for (let i = 0; i < tokens.length; i++) {
        const tok = tokens[i];
        if (tok.startsWith('--')) {
            const [name, ...rest] = tok.split('=');
            if (!(name in allowed)) return `${name} is not an allowed option`;
            if (rest.length > 0) return `${name} does not take a value`;
            const dup = noteFlag(name);
            if (dup) return dup;
        } else if (tok.startsWith('-') && tok.length > 1) {
            const letters = tok.slice(1);
            for (let j = 0; j < letters.length; j++) {
                const flag = `-${letters[j]}`;
                if (!(flag in allowed)) return `${flag} is not an allowed option`;
                if (allowed[flag]) {
                    let value = letters.slice(j + 1);
                    if (!value) {
                        i++;
                        if (i >= tokens.length) return `${flag} needs a value`;
                        value = tokens[i];
                    }
                    const problem = extraValueProblem(flag, value) ?? noteProp(flag, value);
                    if (problem) return problem;
                    break;
                }
                const dup = noteFlag(flag);
                if (dup) return dup;
            }
        } else {
            return `unexpected argument "${tok}"; only options are allowed here`;
        }
    }
    return null;
}

// Only call on text extraArgsProblem accepted: every token is then an allowed boolean flag or cluster.
function canonicalSendFlags(text: string): Set<string> {
    const flags = new Set<string>();
    for (const tok of text.trim().split(/\s+/)) {
        if (tok.startsWith('--')) flags.add(EXTRA_FLAG_ALIASES[tok] ?? tok);
        else if (tok.startsWith('-')) for (const ch of tok.slice(1)) flags.add(`-${ch}`);
    }
    return flags;
}

export function extraSendArgsProblem(
    text: string, recursive: boolean, raw: boolean = false, compressed: boolean = false,
): string | null {
    const problem = extraArgsProblem(text, EXTRA_SEND_FLAGS);
    if (problem) return problem;
    const flags = canonicalSendFlags(text);
    if (recursive && flags.has('-p')) return '-p is already included by Send Recursive';
    for (const flag of ['-L', '-c', '-e']) {
        if (raw && flags.has(flag)) return `${flag} is already implied by Send Raw`;
    }
    for (const flag of ['-L', '-c']) {
        if (compressed && flags.has(flag)) return `${flag} is already included by Send Compressed`;
    }
    if (raw && !recursive && flags.has('-h') && !flags.has('-p')) return '-h with Send Raw also needs -p (or Send Recursive)';
    return null;
}

export function extraRecvArgsProblem(text: string): string | null {
    return extraArgsProblem(text, EXTRA_RECV_FLAGS);
}
