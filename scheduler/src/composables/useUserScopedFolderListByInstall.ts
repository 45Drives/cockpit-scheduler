// useUserScopedFolderListByInstall.ts
import { ref, watch, type Ref } from 'vue';
import { legacy } from '@45drives/houston-common-lib';
const { useSpawn, errorString } = legacy;

const DEBUG_TAG = '[useUserScopedFolderListByInstall]';
const log = (...a: any[]) => console.log(DEBUG_TAG, ...a);
const warn = (...a: any[]) => console.warn(DEBUG_TAG, ...a);
const err = (...a: any[]) => console.error(DEBUG_TAG, ...a);

const sanitize = (s: string) => s.replace(/["'`\\]/g, '');

async function runWithLog(label: string, argv: string[]) {
  const started = Date.now();
  // log(label, 'spawn →', JSON.stringify(argv));
  const st = useSpawn(argv, { superuser: 'try', err: 'message' });
  try {
    const res = await st.promise();
    const dt = Date.now() - started;
    // log(label, 'done in', dt + 'ms', {
    //   code: (res as any)?.code,
    //   stdoutLen: (res.stdout || '').length,
    //   stderrLen: (res.stderr || '').length,
    // });
    if (res.stderr) {
      // Not fatal, but helpful if a command printed warnings
      warn(label, 'stderr:', res.stderr.slice(0, 500));
    }
    return res;
  } catch (e) {
    const dt = Date.now() - started;
    err(label, 'FAILED in', dt + 'ms:', errorString(e) || String(e));
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
  // log('listShareRoots →', parsed);
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

      if command -v jq >/dev/null 2>&1; then
        iid="$(jq -r '.install_id // empty' "$CJ" 2>/dev/null || true)"
        if [ "$iid" = "${ID}" ]; then
          su="$(jq -r '.smb_user // empty' "$CJ" 2>/dev/null || true)"
          hn="$(jq -r '.host // empty'      "$CJ" 2>/dev/null || true)"
          src="$(jq -r '.source // empty'    "$CJ" 2>/dev/null || true)"
          printf '%s|%s|%s|%s\n' "$su" "$hn" "$src" "$(basename "$U")"
          exit 0
        fi
      else
        # Fallback: split by commas, then by quotes; pick the record whose key ($2) matches.
        iid="$(awk -v RS=',' -F'"' '$2=="install_id"{print $4; exit}' "$CJ" || true)"
        if [ "$iid" = "${ID}" ]; then
          su="$(awk -v RS=',' -F'"' '$2=="smb_user"{print $4; exit}' "$CJ" || true)"
          hn="$(awk -v RS=',' -F'"' '$2=="host"{print $4; exit}'      "$CJ" || true)"
          src="$(awk -v RS=',' -F'"' '$2=="source"{print $4; exit}'    "$CJ" || true)"
          printf '%s|%s|%s|%s\n' "$su" "$hn" "$src" "$(basename "$U")"
          exit 0
        fi
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
async function readAllMetasForUser(pathAbs: string, smbUser: string): Promise<Array<{ uuid: string; host: string; source: string }>> {
  const P = sanitize(pathAbs);
  const U = sanitize(smbUser);
  const script = `
    set -euo pipefail
    R="$(realpath -m "${P}")" || exit 0
    [ -d "$R" ] || exit 0
    for D in "$R"/*; do
      [ -d "$D" ] || continue
      CJ="$D/.houston/client.json"
      [ -f "$CJ" ] || continue

      if command -v jq >/dev/null 2>&1; then
        su="$(jq -r '.smb_user // empty' "$CJ" 2>/dev/null || true)"
        [ "$su" = "${U}" ] || continue
        hn="$(jq -r '.host // empty'      "$CJ" 2>/dev/null || true)"
        src="$(jq -r '.source // empty'    "$CJ" 2>/dev/null || true)"
      else
        su="$(awk -v RS=',' -F'"' '$2=="smb_user"{print $4; exit}' "$CJ" || true)"
        [ "$su" = "${U}" ] || continue
        hn="$(awk -v RS=',' -F'"' '$2=="host"{print $4; exit}'      "$CJ" || true)"
        src="$(awk -v RS=',' -F'"' '$2=="source"{print $4; exit}'    "$CJ" || true)"
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
          user = m.smbUser;          // ✅ real smb_user, not install_id
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
      function normSource(src: string) {
        const noLead = String(src || '').replace(/^\/+/, '');
        return noLead.endsWith('/') ? noLead : noLead + '/';
      }

      const abs: string[] = [];
      const rel: string[] = [];

      for (const m of metas) {
        const tail = `${m.uuid}/${m.host}/${normSource(m.source)}`;
        rel.push(tail);
        abs.push(ensureSlash(`${shareRoot.value}${tail}`));
      }

      // de-dupe and assign
      absDirs.value = Array.from(new Set(abs));
      relDirs.value = Array.from(new Set(rel));
      uuids.value = Array.from(new Set(metas.map(m => m.uuid)));

      // // 🔁 Fallback (older client.json without "source"): previous behavior
      // if (!shareRoot.value || !smbUser.value) {
      //   uuids.value = []; absDirs.value = []; relDirs.value = [];
      //   return;
      // }

    } catch (e: any) {
      error.value = errorString(e) || String(e);
      shareRoot.value = ''; smbUser.value = ''; uuids.value = []; absDirs.value = []; relDirs.value = [];
    } finally {
      loading.value = false;
    }
  }

  watch(installIdRef, () => { void refresh(); }, { immediate: true });

  return { shareRoot, smbUser, uuids, absDirs, relDirs, loading, error, refresh, underRoot };
}

