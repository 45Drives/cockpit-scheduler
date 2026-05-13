// useRcloneProviders.ts
import { ref, type Ref } from 'vue';
import { server, unwrap, Command } from '@45drives/houston-common-lib';
//@ts-ignore
import getRcloneProviderOptionsScript from '../scripts/get-rclone-provider-options.py?raw';

import { cloudSyncProviders } from '../models/CloudSync';

const textDecoder = new TextDecoder('utf-8');

async function runCommand(
  argv: string[],
  opts: { superuser?: 'try' | 'require' } = { superuser: 'try' }
): Promise<{ stdout: string; stderr: string; exitStatus: number }> {
  const proc = await unwrap(
    server.execute(new Command(argv, opts))
  );
  const rawStdout: any = proc.stdout;
  const rawStderr: any = proc.stderr;
  const stdout =
    rawStdout instanceof Uint8Array
      ? textDecoder.decode(rawStdout)
      : String(rawStdout ?? '');
  const stderr =
    rawStderr instanceof Uint8Array
      ? textDecoder.decode(rawStderr)
      : String(rawStderr ?? '');
  return { stdout, stderr, exitStatus: proc.exitStatus };
}

export interface RcloneOptionExample {
  value: string;
  help: string;
}

export interface RcloneOption {
  name: string;
  help: string;
  default: any;
  type: string;       // 'string' | 'bool' | 'int' | 'select' | 'sizesuffix' | 'duration'
  required: boolean;
  is_password: boolean;
  advanced: boolean;
  exclusive: boolean;
  examples?: RcloneOptionExample[];
  providers?: string[];  // sub-providers this option applies to (e.g. ["AWS", "Ceph"])
}

export interface RcloneProviderInfo {
  name: string;
  description: string;
  options: RcloneOption[];
}

// Cached providers data - only fetch once
let cachedProviders: Record<string, RcloneProviderInfo> | null = null;
let fetchPromise: Promise<Record<string, RcloneProviderInfo>> | null = null;

async function fetchProvidersFromRclone(): Promise<Record<string, RcloneProviderInfo>> {
  if (cachedProviders) return cachedProviders;
  if (fetchPromise) return fetchPromise;

  fetchPromise = (async () => {
    try {
      const args = ['/usr/bin/env', 'python3', '-c', getRcloneProviderOptionsScript];
      const { stdout } = await runCommand(args, { superuser: 'try' });
      const parsed = JSON.parse(stdout || '{}');
      if (parsed.error) {
        console.error('[useRcloneProviders] rclone error:', parsed.error);
        return {};
      }
      cachedProviders = parsed;
      return parsed;
    } catch (e) {
      console.error('[useRcloneProviders] fetch failed:', e);
      return {};
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

export function useRcloneProviders() {
  const allProviders = ref<Record<string, RcloneProviderInfo>>({});
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load() {
    loading.value = true;
    error.value = null;
    try {
      allProviders.value = await fetchProvidersFromRclone();
    } catch (e: any) {
      error.value = e?.message ?? String(e);
    } finally {
      loading.value = false;
    }
  }

  // Build a map from rclone provider prefix → Set of parameter names defined in CloudSync.ts.
  // Options matching these names are shown as "basic"; everything else is "advanced".
  // Mapping: rclone prefix → CloudSync.ts key(s) for that provider type.
  const prefixToCloudSyncKeys: Record<string, string[]> = {
    'dropbox': ['dropbox'],
    'drive': ['drive'],
    'gcs': ['google cloud storage'],
    'azureblob': ['azureblob'],
    'b2': ['b2'],
    's3': ['s3-Wasabi', 's3-AWS', 's3-Ceph', 's3-IDrive'],
    'storj': ['storj'],
  };

  function getBasicParamNames(providerType: string): Set<string> {
    const keys = prefixToCloudSyncKeys[providerType] ?? [];
    const names = new Set<string>();
    for (const key of keys) {
      const provider = cloudSyncProviders[key];
      if (provider) {
        for (const paramName of Object.keys(provider.providerParams.parameters)) {
          names.add(paramName);
        }
      }
    }
    return names;
  }

  function getProviderOptions(providerType: string, subProvider?: string): RcloneOption[] {
    const opts = allProviders.value[providerType]?.options ?? [];
    const filtered = subProvider
      ? opts.filter(o => {
          if (!o.providers || o.providers.length === 0) return true;
          return o.providers.some(p => p.toLowerCase() === subProvider.toLowerCase());
        })
      : opts;
    // Override advanced flag: options defined in CloudSync.ts are basic, all others are advanced
    const basicNames = getBasicParamNames(providerType);
    return filtered.map(o => {
      if (basicNames.has(o.name)) {
        return o.advanced ? { ...o, advanced: false } : o;
      }
      return o.advanced ? o : { ...o, advanced: true };
    });
  }

  function getBasicOptions(providerType: string, subProvider?: string): RcloneOption[] {
    return getProviderOptions(providerType, subProvider).filter(o => !o.advanced);
  }

  function getAdvancedOptions(providerType: string, subProvider?: string): RcloneOption[] {
    return getProviderOptions(providerType, subProvider).filter(o => o.advanced);
  }

  return {
    allProviders,
    loading,
    error,
    load,
    getProviderOptions,
    getBasicOptions,
    getAdvancedOptions,
  };
}
