#!/usr/bin/env python3
# ensure_passwordless_ssh.py
import argparse, getpass, json, os, shutil, subprocess, sys, tempfile

STEPS = []
LOG_LINES = []

SSH_BASE = [
    "-o", "ConnectTimeout=8",
    "-o", "StrictHostKeyChecking=accept-new",
]

def log(msg, quiet=False):
    text = str(msg)
    LOG_LINES.append(text)
    if not quiet:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()

def record(step, ok, detail=""):
    STEPS.append({"step": step, "ok": bool(ok), "detail": (detail or "")[-2000:]})

def run(cmd, env=None):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        env=env,
    )

def decode(b) -> str:
    return (b or b"").decode("utf-8", "replace")

def have_cmd(name:str) -> bool:
    return shutil.which(name) is not None

def classify(text: str):
    """Map raw ssh output onto a machine-readable reason plus a human explanation."""
    t = (text or "").lower()
    if "remote host identification has changed" in t or "host key verification failed" in t:
        return ("host_key_changed",
                "The target's SSH host key does not match the one already saved on this server. "
                "This happens when the target was reinstalled or its IP was reused by another machine. "
                f"Clear the stale entry on this server with: ssh-keygen -R <host>")
    if "could not resolve hostname" in t or "name or service not known" in t:
        return ("host_unresolved",
                "The server address could not be resolved. Check the hostname or use an IP address.")
    if "connection refused" in t:
        return ("connection_refused",
                "The target refused the connection on this port. Check that sshd is running and the port is correct.")
    if "connection timed out" in t or "operation timed out" in t or "timed out" in t:
        return ("connection_timeout",
                "The target did not answer. Check the network path, VPN tunnel and firewall rules.")
    if "no route to host" in t or "network is unreachable" in t:
        return ("network_unreachable",
                "There is no network route to the target. For an off-site server, confirm the VPN tunnel is up.")
    if "permission denied" in t:
        return ("permission_denied",
                "The target rejected the credentials. Check the username and password.")
    if "too many authentication failures" in t:
        return ("too_many_auth_failures",
                "The target closed the connection after too many key offers. Reduce the keys offered or set IdentitiesOnly=yes.")
    return ("", "")

def parse_auth_methods(verbose_text: str):
    """Pull the last 'Authentications that can continue' list out of ssh -v output."""
    marker = "Authentications that can continue:"
    methods = []
    for line in (verbose_text or "").splitlines():
        if marker in line:
            methods = [m.strip() for m in line.split(marker, 1)[1].strip().split(",") if m.strip()]
    return methods

def test_passwordless(user, host, port, quiet=False):
    cp = run(["ssh", "-p", str(port)] + SSH_BASE + [
        "-o", "BatchMode=yes",
        "-o", "NumberOfPasswordPrompts=0",
        f"{user}@{host}", "true",
    ])
    return cp.returncode == 0, decode(cp.stderr).strip()

def probe(user, host, port):
    """Verbose reachability/auth probe. Never sends a password."""
    cp = run(["ssh", "-v", "-p", str(port)] + SSH_BASE + [
        "-o", "BatchMode=yes",
        "-o", "NumberOfPasswordPrompts=0",
        f"{user}@{host}", "true",
    ])
    err = decode(cp.stderr)
    reason, detail = classify(err)
    return {
        "reachable": reason not in ("host_unresolved", "connection_refused", "connection_timeout", "network_unreachable"),
        "reason": reason,
        "detail": detail,
        "auth_methods": parse_auth_methods(err),
        "stderr": err,
    }

def ensure_keypair(kind: str, key_dir: str, quiet=False):
    os.makedirs(key_dir, mode=0o700, exist_ok=True)
    if kind == "ed25519":
        pk = os.path.join(key_dir, "id_ed25519")
        args = ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", pk, "-C", "cockpit-scheduler"]
    elif kind == "rsa":
        pk = os.path.join(key_dir, "id_rsa")
        args = ["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", pk, "-C", "cockpit-scheduler"]
    else:
        raise ValueError("unknown key type")

    if os.path.isfile(pk) and os.path.isfile(pk + ".pub"):
        record(f"keypair:{kind}", True, f"reused existing key {pk}")
        return pk

    log(f"Generating {kind} keypair at {pk}", quiet)
    cp = run(args)
    if cp.returncode != 0:
        record(f"keypair:{kind}", False, decode(cp.stderr).strip())
        return None
    record(f"keypair:{kind}", True, f"generated {pk}")
    return pk

REMOTE_INSTALL = (
    'umask 077; '
    'mkdir -p ~/.ssh; '
    'touch ~/.ssh/authorized_keys; '
    'grep -qxF "{key}" ~/.ssh/authorized_keys || printf "%s\\n" "{key}" >> ~/.ssh/authorized_keys; '
    'chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; chmod go-w ~ 2>/dev/null; '
    'command -v restorecon >/dev/null 2>&1 && restorecon -R ~/.ssh >/dev/null 2>&1; '
    'exit 0'
)

def _remote_cmd(pubkey_text: str) -> str:
    esc = pubkey_text.replace("\\", "\\\\").replace('"', '\\"')
    return REMOTE_INSTALL.format(key=esc)

def _push_with_sshpass(user, host, port, password, pubkey_text):
    env = os.environ.copy()
    env["SSHPASS"] = password
    cp = run(["sshpass", "-e", "ssh", "-p", str(port)] + SSH_BASE + [
        "-o", "PubkeyAuthentication=no",
        "-o", "PreferredAuthentications=password,keyboard-interactive",
        "-o", "NumberOfPasswordPrompts=1",
        f"{user}@{host}", _remote_cmd(pubkey_text),
    ], env=env)
    return cp.returncode, decode(cp.stdout) + decode(cp.stderr)

def _push_with_askpass(user, host, port, password, pubkey_text):
    """Password auth without sshpass, driven by SSH_ASKPASS. Works on stock OpenSSH."""
    tmpdir = tempfile.mkdtemp(prefix="cockpit-scheduler-askpass-")
    script = os.path.join(tmpdir, "askpass.sh")
    try:
        with open(script, "w", encoding="utf-8") as f:
            f.write('#!/bin/sh\nprintf \'%s\\n\' "$COCKPIT_SSH_PASSWORD"\n')
        os.chmod(script, 0o700)

        env = os.environ.copy()
        env["SSH_ASKPASS"] = script
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["COCKPIT_SSH_PASSWORD"] = password
        env.setdefault("DISPLAY", ":0")

        ssh_cmd = ["ssh", "-p", str(port)] + SSH_BASE + [
            "-o", "PubkeyAuthentication=no",
            "-o", "PreferredAuthentications=password,keyboard-interactive",
            "-o", "NumberOfPasswordPrompts=1",
            f"{user}@{host}", _remote_cmd(pubkey_text),
        ]

        cp = run(ssh_cmd, env=env)
        out = decode(cp.stdout) + decode(cp.stderr)
        if cp.returncode == 0:
            return cp.returncode, out

        # OpenSSH < 8.4 ignores SSH_ASKPASS_REQUIRE and needs no controlling terminal.
        if have_cmd("setsid"):
            cp2 = run(["setsid", "-w"] + ssh_cmd, env=env)
            out2 = decode(cp2.stdout) + decode(cp2.stderr)
            if cp2.returncode == 0:
                return cp2.returncode, out2
            return cp2.returncode, out + out2
        return cp.returncode, out
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def install_pubkey(user, host, port, password, pubkey_text, quiet=False):
    """Returns (ok, reason, detail)."""
    attempts = []
    if have_cmd("sshpass"):
        log("Installing public key using sshpass…", quiet)
        rc, out = _push_with_sshpass(user, host, port, password, pubkey_text)
        record("install:sshpass", rc == 0, out.strip())
        if rc == 0:
            return True, "", ""
        attempts.append(out)

    log("Installing public key using SSH_ASKPASS…", quiet)
    rc, out = _push_with_askpass(user, host, port, password, pubkey_text)
    record("install:askpass", rc == 0, out.strip())
    if rc == 0:
        return True, "", ""
    attempts.append(out)

    reason, detail = classify("\n".join(attempts))
    if not reason:
        reason = "key_install_failed"
        detail = "The one-time key install over password authentication did not complete."
    return False, reason, detail

def main():
    parser = argparse.ArgumentParser(description="Ensure passwordless SSH by installing a public key remotely if needed.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--port", default="22")
    parser.add_argument("--password", default="")
    parser.add_argument("--password-stdin", action="store_true", help="Read the password from stdin instead of argv.")
    parser.add_argument("--key-type", default="auto", choices=["auto","ed25519","rsa","both"])
    parser.add_argument("--key-dir", default="")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    host = args.host.strip()
    user = args.user.strip() or "root"
    try:
        port = int(str(args.port).strip() or "22")
    except ValueError:
        port = 22
    password = sys.stdin.read().rstrip("\n") if args.password_stdin else args.password
    key_mode = args.key_type
    key_dir = args.key_dir or os.path.join(os.path.expanduser("~"), ".ssh")
    quiet = args.quiet

    try:
        local_user = getpass.getuser()
    except Exception:
        local_user = str(os.geteuid())

    base = {
        "user": user,
        "host": host,
        "port": port,
        "local_user": local_user,
        "key_dir": key_dir,
        "sshpass_available": have_cmd("sshpass"),
    }

    def emit(success, message, reason="", detail="", extra=None):
        payload = dict(base)
        payload.update({
            "success": success,
            "message": message,
            "reason": reason,
            "detail": detail,
            "steps": STEPS,
            "log": "\n".join(LOG_LINES)[-4000:],
        })
        if extra:
            payload.update(extra)
        print(json.dumps(payload))
        sys.exit(0 if success else 1)

    ok, err = test_passwordless(user, host, port)
    record("precheck", ok, err)
    if ok:
        msg = f"Passwordless SSH already works for {user}@{host}"
        log(msg, quiet)
        emit(True, msg)

    info = probe(user, host, port)
    record("probe", info["reachable"], (info["reason"] or "reachable") + " | auth: " + ", ".join(info["auth_methods"]))

    if not info["reachable"]:
        emit(False, f"Cannot reach {user}@{host}:{port}.", info["reason"] or "unreachable", info["detail"])

    if info["reason"] == "host_key_changed":
        emit(False, f"Host key mismatch for {host}.", info["reason"], info["detail"])

    if not password:
        emit(False, f"A password for {user}@{host} is required to install the SSH key.",
             "password_required",
             "Enter the account password once so the key can be installed. It is not stored.")

    methods = info["auth_methods"]
    if methods and not any(m in ("password", "keyboard-interactive") for m in methods):
        emit(False, f"{host} does not accept password logins for {user}.",
             "password_auth_disabled",
             "The target's sshd only offers: " + ", ".join(methods) +
             ". Enable PasswordAuthentication on the target (and PermitRootLogin yes when connecting as root), "
             "or add this server's public key to the target's authorized_keys manually.")

    key_types = ["ed25519", "rsa"] if key_mode in ("auto", "both") else [key_mode]

    last_reason, last_detail = "", ""
    for kind in key_types:
        pk = ensure_keypair(kind, key_dir, quiet=quiet)
        if not pk:
            last_reason = "keygen_failed"
            last_detail = f"Could not generate a local {kind} keypair in {key_dir}."
            continue

        with open(pk + ".pub", "r", encoding="utf-8") as f:
            pubkey_text = f.read().strip()

        installed, reason, detail = install_pubkey(user, host, port, password, pubkey_text, quiet=quiet)
        if not installed:
            last_reason, last_detail = reason, detail
            if reason in ("permission_denied", "password_auth_disabled", "host_key_changed"):
                break
            continue

        ok, err = test_passwordless(user, host, port)
        record(f"verify:{kind}", ok, err)
        if ok:
            msg = f"Passwordless SSH ready ({kind})."
            log(msg, quiet)
            emit(True, msg, extra={"key_type": kind, "key_path": pk})

        last_reason = "verify_failed"
        last_detail = (
            "The key was copied to the target but key-based login still failed. On the target, check that sshd "
            "allows public key authentication, that ~/.ssh is 700 and authorized_keys is 600, and on RHEL-family "
            "systems that SELinux contexts are correct (restorecon -R ~/.ssh). ssh reported: " + (err or "no output")
        )

    if last_reason == "permission_denied":
        last_detail = (
            f"{host} rejected the password for {user}. Confirm the password, and when connecting as root confirm "
            "the target allows root password logins (PermitRootLogin yes, PasswordAuthentication yes)."
        )

    emit(False, f"Failed to establish passwordless SSH for {user}@{host}.",
         last_reason or "unknown", last_detail)

if __name__ == "__main__":
    main()
