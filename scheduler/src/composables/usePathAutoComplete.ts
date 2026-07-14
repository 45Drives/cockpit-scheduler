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

export interface PathAutoCompleteOpts {
  dirsOnly?: boolean;
  remoteHost?: Ref<string>;
  remoteUser?: Ref<string>;
}

export function usePathAutoComplete(pathRef: Ref<string>, opts?: PathAutoCompleteOpts) {
  const suggestions = ref<PathEntry[]>([]);
  const loading = ref(false);
  const showSuggestions = ref(false);

  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let lastQuery = '';

  // Reset cache when remote host changes so suggestions re-fetch
  if (opts?.remoteHost) {
    watch(opts.remoteHost, () => {
      lastQuery = '';
      suggestions.value = [];
    });
  }

  async function fetchSuggestions(partial: string) {
    if (!partial || !partial.startsWith('/')) {
      suggestions.value = [];
      return;
    }

    // Don't re-fetch for the same query
    const host = opts?.remoteHost?.value || '';
    const user = opts?.remoteUser?.value || 'root';
    const queryKey = `${host}:${user}:${partial}`;
    if (queryKey === lastQuery) return;
    lastQuery = queryKey;

    loading.value = true;
    try {
      let args: string[];
      if (host) {
        // Validate host/user don't contain dangerous characters
        if (/[;&|`$\\"\n]/.test(host) || /[;&|`$\\"\n]/.test(user)) {
          suggestions.value = [];
          loading.value = false;
          return;
        }
        // Run the list-directory script on the remote host via SSH
        const dirsFlag = opts?.dirsOnly ? ' --dirs-only' : '';
        const sshTarget = `${user}@${host}`;
        // Shell-escape by replacing ' with '\'' for safe embedding in single-quoted strings
        const shellEscape = (s: string) => s.replace(/'/g, "'\\''");
        const escapedScript = shellEscape(listDirectoryScript);
        const escapedPartial = shellEscape(partial);
        const remoteCmd = `python3 -c '${escapedScript}' '${escapedPartial}'${dirsFlag}`;
        args = ['/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', sshTarget, remoteCmd];
      } else {
        args = ['/usr/bin/env', 'python3', '-c', listDirectoryScript, partial];
        if (opts?.dirsOnly) args.push('--dirs-only');
      }

      const { stdout, exitStatus } = await runCommand(args, { superuser: 'try' });
      if (exitStatus !== 0) {
        suggestions.value = [];
        showSuggestions.value = false;
        return;
      }
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
