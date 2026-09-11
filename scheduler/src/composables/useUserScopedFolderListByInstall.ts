// useUserScopedFolderListByInstall.ts
import { ref, watch, type Ref } from 'vue';
import { server, unwrap, Command } from '@45drives/houston-common-lib'

const DEBUG_TAG = '[useUserScopedFolderListByInstall]';
const log = (...a: any[]) => console.log(DEBUG_TAG, ...a);
const warn = (...a: any[]) => console.warn(DEBUG_TAG, ...a);
const err = (...a: any[]) => console.error(DEBUG_TAG, ...a);

const sanitize = (s: string) => s.replace(/["'`\\]/g, '');

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

async function runWithLog(label: string, argv: string[]) {
  const started = Date.now();
  try {
    const res = await runCommand(argv, { superuser: 'try' });
    if (res.stderr) {
      warn(label, 'stderr:', res.stderr.slice(0, 500));
    }
    return res;
  } catch (e: any) {
    const dt = Date.now() - started;
    err(label, 'FAILED in', dt + 'ms:', e?.message ?? String(e));
    throw e;
  }
}

async function listShareRoots(): Promise<Array<{ name: string; path: string }>> {
  const script = `
    set -euo pipefail
    out=""
    if command -v testparm >/dev/null 2>&1; then
      out="$(testparm -s 2>/dev/null || true)"
    fi
    if [ -z "$out" ] && [ -f /etc/samba/smb.conf ]; then
      out="$(cat /etc/samba/smb.conf)"
    fi
    if [ -z "$out" ] && [ -f /etc/cockpit/zfs/shares.conf ]; then
      out="$(cat /etc/cockpit/zfs/shares.conf)"
    fi

    awk '
      BEGIN{IGNORECASE=1; sec=""; name=""}
      /^\\[/ {
        sec=$0; gsub(/[][]/,"",sec);
        gsub(/^[ \\t]+|[ \\t]+$/,"",sec);
        name=sec; next
      }
      /^[ \\t]*path[ \\t]*=/ {
        n=index($0,"="); if (n>0) {
          p=substr($0,n+1); gsub(/^[ \\t]+|[ \\t]+$/,"",p);
          if (name!="" && name!="global") print name "|" p
        }
      }
    ' <<< "$out" | sed '/^$/d'
  `;
  const res = await runWithLog('listShareRoots', ['bash', '-lc', script]);
  const lines = (res.stdout || '').trim().split('\n').filter(Boolean);
  const parsed = lines.map(l => {
    const [name, path] = l.split('|');
    return { name, path };
  });
  return parsed;
}

// ⬇ add this (replaces resolveSmbUserByInstall)
async function readInstallMeta(pathAbs: string, installId: string): Promise<{
  smbUser: string; host: string; source: string; uuid: string
} | null> {
  const P = sanitize(pathAbs);
  const ID = sanitize(installId);
  const script = `
    set -euo pipefail
    R="$(realpath -m "${P}")" || exit 0
    [ -d "$R" ] || exit 0
    for U in "$R"/*; do
      [ -d "$U" ] || continue
      CJ="$U/.houston/client.json"
      [ -f "$CJ" ] || continue

      # Try jq first, fall back to awk if jq fails (e.g. invalid JSON from Windows backslashes)
      iid=""
      if command -v jq >/dev/null 2>&1; then
        iid="$(jq -r '.install_id // empty' "$CJ" 2>/dev/null || true)"
      fi
      if [ -z "$iid" ]; then
        iid="$(awk -v RS=',' -F'"' '$2=="install_id"{print $4; exit}' "$CJ" 2>/dev/null || true)"
      fi

      if [ "$iid" = "${ID}" ]; then
        su=""; hn=""; src=""
        if command -v jq >/dev/null 2>&1; then
          su="$(jq -r '.smb_user // empty' "$CJ" 2>/dev/null || true)"
          hn="$(jq -r '.host // empty'      "$CJ" 2>/dev/null || true)"
          src="$(jq -r '.source // empty'    "$CJ" 2>/dev/null || true)"
        fi
        if [ -z "$su" ]; then
          su="$(awk -v RS=',' -F'"' '$2=="smb_user"{print $4; exit}' "$CJ" 2>/dev/null || true)"
          hn="$(awk -v RS=',' -F'"' '$2=="host"{print $4; exit}'      "$CJ" 2>/dev/null || true)"
          src="$(awk -v RS=',' -F'"' '$2=="source"{print $4; exit}'    "$CJ" 2>/dev/null || true)"
        fi
        printf '%s|%s|%s|%s\n' "$su" "$hn" "$src" "$(basename "$U")"
        exit 0
      fi
    done
  `;
  const res = await runWithLog('readInstallMeta', ['bash', '-lc', script]);
  const out = (res.stdout || '').trim();
  if (!out) return null;
  const [smbUser, host, source, uuid] = out.split('|');
  return { smbUser, host, source, uuid };
}


// ⬇ new: list every {uuid,host,source} for this smb_user
async function readAllMetasForUser(pathAbs: string, smbUser: string): Promise<Array<{ uuid: string; host: string; source: string }>> {  const P = sanitize(pathAbs);
  const U = sanitize(smbUser);
  const script = `
    set -euo pipefail
    R="$(realpath -m "${P}")" || exit 0
    [ -d "$R" ] || exit 0
    for D in "$R"/*; do
      [ -d "$D" ] || continue
      CJ="$D/.houston/client.json"
      [ -f "$CJ" ] || continue

      # Try jq first, fall back to awk if jq fails (e.g. invalid JSON from Windows backslashes)
      su=""
      if command -v jq >/dev/null 2>&1; then
        su="$(jq -r '.smb_user // empty' "$CJ" 2>/dev/null || true)"
      fi
      if [ -z "$su" ]; then
        su="$(awk -v RS=',' -F'"' '$2=="smb_user"{print $4; exit}' "$CJ" 2>/dev/null || true)"
      fi
      [ "$su" = "${U}" ] || continue

      hn=""; src=""
      if command -v jq >/dev/null 2>&1; then
        hn="$(jq -r '.host // empty'      "$CJ" 2>/dev/null || true)"
        src="$(jq -r '.source // empty'    "$CJ" 2>/dev/null || true)"
      fi
      if [ -z "$hn" ]; then
        hn="$(awk -v RS=',' -F'"' '$2=="host"{print $4; exit}'      "$CJ" 2>/dev/null || true)"
        src="$(awk -v RS=',' -F'"' '$2=="source"{print $4; exit}'    "$CJ" 2>/dev/null || true)"
      fi

      printf '%s|%s|%s\n' "$(basename "$D")" "$hn" "$src"
    done | sed '/^$/d'
  `;
  const res = await runWithLog('readAllMetasForUser', ['bash', '-lc', script]);
  return (res.stdout || '')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map(line => {
      const [uuid, host, source] = line.split('|');
      return { uuid, host, source };
    });
}


/**
 * The client names this directory from bare `hostname` but records `hostname -s` (macOS) or
 * %COMPUTERNAME% (Windows) in client.json, so the marker can't be trusted to rebuild the
 * path — on a Mac it is missing the `.local` suffix. Read the real names off disk instead.
 * Returns uuid -> directory names.
 */
async function listHostDirs(root: string, uuids: string[]): Promise<Record<string, string[]>> {
  if (!uuids.length) return {};
  const res = await runWithLog('listHostDirs', [
    'bash', '-c',
    'R="$1"; shift; for u in "$@"; do for d in "$R/$u"/*/; do [ -d "$d" ] || continue; ' +
    'b="${d%/}"; printf "%s|%s\\n" "$u" "${b##*/}"; done; done; exit 0',
    '_', root, ...uuids,
  ]);
  const out: Record<string, string[]> = {};
  for (const line of (res.stdout || '').split('\n').filter(Boolean)) {
    const sep = line.indexOf('|');
    if (sep <= 0) continue;
    const uuid = line.slice(0, sep);
    (out[uuid] ??= []).push(line.slice(sep + 1));
  }
  return out;
}

/**
 * These paths are reconstructed from client.json metadata rather than read off disk, so any
 * drift between the client's sanitizer and ours yields a path that doesn't exist. Offering
 * one produces an rsync "No such file or directory" failure at run time, so drop them here.
 * Args go through argv, not the shell, so paths with quotes/backslashes survive intact.
 */
async function filterExistingDirs(dirs: string[]): Promise<string[]> {
  if (!dirs.length) return [];
  // Trailing `exit 0`: a missing final path would otherwise make the script exit 1.
  const res = await runWithLog('filterExistingDirs', [
    'bash', '-c', 'for p in "$@"; do [ -d "$p" ] && printf "%s\\n" "$p"; done; exit 0', '_', ...dirs,
  ]);
  return (res.stdout || '').split('\n').filter(Boolean);
}

/**
 * Auto-detect share root, resolve smb_user from installId,
 * then list folders belonging to that smb_user.
 */
export function useUserScopedFolderListByInstall(installIdRef: Ref<string>, depth = 2) {
  const hostName = ref<string>('');
  const shareRoot = ref<string>('');
  const smbUser = ref<string>('');
  const uuids = ref<string[]>([]);
  const absDirs = ref<string[]>([]);
  const relDirs = ref<string[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const ensureSlash = (p: string) => (p && !p.endsWith('/') ? `${p}/` : p);
  const underRoot = (p: string) => {
    const base = ensureSlash(shareRoot.value.replace(/\/+$/, ''));
    const full = ensureSlash((p || '').replace(/\/+$/, ''));
    return !base || full.startsWith(base);
  };

  async function refresh() {
    const installId = (installIdRef.value || '').trim();
    loading.value = true;
    error.value = null;

    try {
      if (!installId) {
        shareRoot.value = ''; smbUser.value = ''; uuids.value = []; absDirs.value = []; relDirs.value = [];
        return;
      }

      const roots = await listShareRoots();

      let chosenRoot = '';
      let user = '';
      let metaFromInstall: { smbUser: string; host: string; source: string; uuid: string } | null = null;

      for (const r of roots) {
        const m = await readInstallMeta(r.path, installId);
        if (m) {
          chosenRoot = r.path;
          user = m.smbUser;          // real smb_user, not install_id
          metaFromInstall = m;
          break;
        }
      }

      shareRoot.value = chosenRoot ? ensureSlash(chosenRoot) : '';
      smbUser.value = user;

      if (!shareRoot.value || !smbUser.value) {
        uuids.value = []; absDirs.value = []; relDirs.value = [];
        return;
      }

      // read every {uuid,host,source} for this smb_user
      const metas = await readAllMetasForUser(shareRoot.value, smbUser.value);

      // construct absolute/relative options directly from meta
      // Mirrors the client's sanitizeFilePath so paths match the directories it created.
      function normSegment(s: string) {
        return String(s || '')
          .replace(/[:*?"<>|]/g, '')
          .replace(/\\/g, '/')
          .replace(/\s+/g, ' ')
          .trim();
      }

      function normSource(src: string) {
        const noLead = normSegment(src).replace(/^\/+/, '');
        return noLead.endsWith('/') ? noLead : noLead + '/';
      }

      const rootNoSlash = shareRoot.value.replace(/\/+$/, '');
      const metaUuids = Array.from(new Set(metas.map(m => m.uuid).filter(Boolean)));
      const hostDirsByUuid = await listHostDirs(rootNoSlash, metaUuids);

      const abs: string[] = [];

      for (const m of metas) {
        // Fall back to the recorded host when nothing is on disk yet, so a backup that has
        // only written its marker still shows up rather than vanishing from the list.
        const hostDirs = hostDirsByUuid[m.uuid]?.length
          ? hostDirsByUuid[m.uuid]
          : [normSegment(m.host)];
        for (const hostDir of hostDirs) {
          abs.push(ensureSlash(`${rootNoSlash}/${m.uuid}/${hostDir}/${normSource(m.source)}`));
        }
      }

      const existing = await filterExistingDirs(Array.from(new Set(abs)));
      const rootPrefix = ensureSlash(rootNoSlash);

      absDirs.value = existing;
      relDirs.value = Array.from(new Set(existing.map(p => p.startsWith(rootPrefix) ? p.slice(rootPrefix.length) : p)));
      uuids.value = metaUuids;

    } catch (e: any) {
      error.value = e?.message ?? String(e);
      shareRoot.value = ''; smbUser.value = ''; uuids.value = []; absDirs.value = []; relDirs.value = [];
    } finally {
      loading.value = false;
    }
  }

  watch(installIdRef, () => { void refresh(); }, { immediate: true });

  return { shareRoot, smbUser, uuids, absDirs, relDirs, loading, error, refresh, underRoot };
}
