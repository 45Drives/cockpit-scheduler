// usePathAutoComplete.ts
import { ref, watch, type Ref } from 'vue';
import { server, unwrap, Command } from '@45drives/houston-common-lib';
//@ts-ignore
import listDirectoryScript from '../scripts/list-directory.py?raw';

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

export interface PathEntry {
  path: string;
  name: string;
  isDir: boolean;
}

export function usePathAutoComplete(pathRef: Ref<string>, opts?: { dirsOnly?: boolean }) {
  const suggestions = ref<PathEntry[]>([]);
  const loading = ref(false);
  const showSuggestions = ref(false);

  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let lastQuery = '';

  async function fetchSuggestions(partial: string) {
    if (!partial || !partial.startsWith('/')) {
      suggestions.value = [];
      return;
    }

    // Don't re-fetch for the same query
    if (partial === lastQuery) return;
    lastQuery = partial;

    loading.value = true;
    try {
      const args = ['/usr/bin/env', 'python3', '-c', listDirectoryScript, partial];
      if (opts?.dirsOnly) args.push('--dirs-only');

      const { stdout } = await runCommand(args, { superuser: 'try' });
      const parsed = JSON.parse(stdout || '[]');
      suggestions.value = parsed as PathEntry[];
      showSuggestions.value = suggestions.value.length > 0;
    } catch (e) {
      console.error('[usePathAutoComplete] fetch failed:', e);
      suggestions.value = [];
    } finally {
      loading.value = false;
    }
  }

  function onInput() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      fetchSuggestions(pathRef.value);
    }, 200);
  }

  function selectSuggestion(entry: PathEntry) {
    pathRef.value = entry.path;
    showSuggestions.value = false;
    lastQuery = entry.path;
    // If it's a directory, fetch its contents immediately
    if (entry.isDir) {
      fetchSuggestions(entry.path);
    }
  }

  function hideSuggestions() {
    // Small delay so click on suggestion can register
    setTimeout(() => {
      showSuggestions.value = false;
    }, 150);
  }

  function onFocus() {
    if (pathRef.value && pathRef.value.startsWith('/') && suggestions.value.length > 0) {
      showSuggestions.value = true;
    } else if (pathRef.value && pathRef.value.startsWith('/')) {
      fetchSuggestions(pathRef.value);
    }
  }

  return {
    suggestions,
    loading,
    showSuggestions,
    onInput,
    selectSuggestion,
    hideSuggestions,
    onFocus,
    fetchSuggestions,
  };
}
