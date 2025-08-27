import { defineStore } from 'pinia'

export const useClientContextStore = defineStore('clientCtx', {
    state: () => ({ clientId: '' as string }),
    actions: {
        hydrateFromUrl() {
            try {
                const url = new URL(window.location.href)
                // A) if someone ever moves ? before #
                const fromSearch = url.searchParams.get('client_id')
                if (fromSearch) { this.clientId = fromSearch; return }

                // B) hash-router form: #/path?client_id=...
                const hash = url.hash || ''
                const i = hash.indexOf('?')
                if (i !== -1) {
                    const hp = new URLSearchParams(hash.slice(i + 1))
                    const fromHash = hp.get('client_id')
                    if (fromHash) { this.clientId = fromHash; return }
                }
            } catch {/* noop */ }
        }
    }
})