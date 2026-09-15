// useWireShieldInstalled.ts
import { computed, ref, type ComputedRef, type Ref } from 'vue';
import { execCommand } from '../utils/commandGate';

export const WIRESHIELD_MISSING_MESSAGE =
    'WireShield is not installed on this server. Install the WireShield package to set up an off-site connection.';

// null = not determined yet
const installed = ref<boolean | null>(null);
const missing = computed(() => installed.value === false);
let probe: Promise<boolean> | null = null;

// Plugin dir covers package/dev installs; the CLI covers a backend-only install.
const PROBE_SCRIPT = [
    'test -d /usr/share/cockpit/wireshield',
    'test -d /usr/local/share/cockpit/wireshield',
    'test -x /usr/sbin/wireshield-pair',
].join(' || ');

async function probeWireShield(): Promise<boolean> {
    const { exitStatus } = await execCommand(
        ['/usr/bin/env', 'bash', '-c', PROBE_SCRIPT],
        { superuser: 'try' },
        false
    );
    return exitStatus === 0;
}

export function useWireShieldInstalled(): {
    wireShieldInstalled: Ref<boolean | null>;
    wireShieldMissing: ComputedRef<boolean>;
} {
    if (!probe) {
        probe = probeWireShield()
            .then((found) => {
                installed.value = found;
                return found;
            })
            // A failed probe means "unknown", not "missing" — don't block the button.
            .catch(() => {
                installed.value = true;
                return true;
            });
    }

    return { wireShieldInstalled: installed, wireShieldMissing: missing };
}
