// useWireShieldInstalled.ts
import { computed, ref, type ComputedRef, type Ref } from 'vue';

const WIRESHIELD_PACKAGE = 'wireshield';

export const WIRESHIELD_MISSING_MESSAGE =
    'WireShield is not installed on this server. Install the WireShield package to set up an off-site connection.';

// null = not determined yet
const installed = ref<boolean | null>(null);
const missing = computed(() => installed.value === false);
let probe: Promise<boolean> | null = null;

async function probeWireShield(): Promise<boolean> {
    const manifests = (window as any).cockpit?.manifests;
    if (manifests && typeof manifests === 'object' && Object.keys(manifests).length > 0) {
        return Object.prototype.hasOwnProperty.call(manifests, WIRESHIELD_PACKAGE);
    }

    // Cockpit only serves package files that exist, so a 404 means "not installed".
    try {
        const res = await fetch(`/cockpit/@localhost/${WIRESHIELD_PACKAGE}/manifest.json`, {
            credentials: 'same-origin',
            cache: 'no-cache',
        });
        return res.ok;
    } catch {
        return false;
    }
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
            .catch(() => {
                installed.value = false;
                return false;
            });
    }

    return { wireShieldInstalled: installed, wireShieldMissing: missing };
}
