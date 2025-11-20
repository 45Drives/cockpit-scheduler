#!/usr/bin/env python3
# ensure_passwordless_ssh.py
import argparse, json, os, shutil, subprocess, sys

def log(msg, quiet=False):
    if not quiet:
        sys.stderr.write(str(msg) + "\n")
        sys.stderr.flush()

def run(cmd, check=False, quiet=False, env=None):
    if not quiet:
        log(f"$ {' '.join(cmd)}", quiet)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,)

def have_cmd(name:str) -> bool:
    return shutil.which(name) is not None

def test_passwordless(user, host, port, quiet=False) -> bool:
    cp = run([
        "ssh", "-p", str(port),
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "NumberOfPasswordPrompts=0",
        f"{user}@{host}", "true"
    ], quiet=True)
    return cp.returncode == 0

def ensure_keypair(kind: str, key_dir: str, quiet=False) -> str:
    os.makedirs(key_dir, exist_ok=True)
    if kind == "ed25519":
        pk = os.path.join(key_dir, "id_ed25519")
        pub = pk + ".pub"
        if os.path.isfile(pk) and os.path.isfile(pub): return pk
        log(f"Generating ed25519 keypair at {pk}", quiet)
        run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", pk, "-C", "auto"], check=True, quiet=True)
        return pk
    elif kind == "rsa":
        pk = os.path.join(key_dir, "id_rsa")
        pub = pk + ".pub"
        if os.path.isfile(pk) and os.path.isfile(pub): return pk
        log(f"Generating rsa-4096 keypair at {pk}", quiet)
        run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", pk, "-C", "auto"], check=True, quiet=True)
        return pk
    raise ValueError("unknown key type")

def ensure_sshpass(quiet=False) -> bool:
    if have_cmd("sshpass"): return True
    log("sshpass not found; attempting to install…", quiet)
    pm = None
    for cand in ("apt-get","dnf","yum","zypper","pacman","apk"):
        if have_cmd(cand):
            pm = cand
            break
    if pm is None:
        log("Could not auto-install sshpass. Please install it manually and re-run.", quiet)
        return False

    def maybe_sudo(cmd):
        sudo = ["sudo"]
        # Attempt non-interactive test; if it fails we still try sudo (may prompt)
        run(["sudo","-n","true"], quiet=True)
        return sudo + cmd

    try:
        if pm == "apt-get":
            env = os.environ.copy()
            env["DEBIAN_FRONTEND"] = "noninteractive"
            run(maybe_sudo(["apt-get","update","-y"]), quiet=quiet)
            run(maybe_sudo(["apt-get","install","-y","sshpass"]), check=True, quiet=quiet, env=env)
        elif pm == "dnf":
            run(maybe_sudo(["dnf","-y","install","epel-release"]), quiet=True)
            run(maybe_sudo(["dnf","-y","install","sshpass"]), check=True, quiet=quiet)
        elif pm == "yum":
            run(maybe_sudo(["yum","-y","install","epel-release"]), quiet=True)
            run(maybe_sudo(["yum","-y","install","sshpass"]), check=True, quiet=quiet)
        elif pm == "zypper":
            run(maybe_sudo(["zypper","-n","install","sshpass"]), check=True, quiet=quiet)
        elif pm == "pacman":
            run(maybe_sudo(["pacman","-Sy","--noconfirm","sshpass"]), check=True, quiet=quiet)
        elif pm == "apk":
            run(maybe_sudo(["apk","add","--no-cache","sshpass"]), check=True, quiet=quiet)
    except subprocess.CalledProcessError as e:
        log(f"Failed to install sshpass: {e}", quiet)
        return False

    return have_cmd("sshpass")

def push_pubkey_with_password(user, host, port, password, pubkey_text, quiet=False) -> bool:
    if not have_cmd("sshpass"):
        log("sshpass is required locally to automate the password step. Install it and retry.", quiet)
        return False
    # Escape for remote double-quoted context
    esc = pubkey_text.replace("\\", "\\\\").replace('"', '\\"')
    env = os.environ.copy()
    env["SSHPASS"] = password
    cmd = [
        "sshpass","-e","ssh","-p",str(port),
        "-o","StrictHostKeyChecking=accept-new",
        "-o","PubkeyAuthentication=no",
        f"{user}@{host}",
        f'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; '
        f'grep -qxF "{esc}" ~/.ssh/authorized_keys || echo "{esc}" >> ~/.ssh/authorized_keys; '
        f'chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
    ]
    cp = run(cmd, quiet=True, env=env)
    return cp.returncode == 0

def try_key_then_install(user, host, port, password, privkey_path, quiet=False) -> bool:
    pub = privkey_path + ".pub"
    if not os.path.isfile(pub):
        log(f"Missing {pub}", quiet)
        return False

    if test_passwordless(user, host, port, quiet=True):
        return True

    if not password:
        return False

    if not ensure_sshpass(quiet=quiet):
        return False

    with open(pub, "r", encoding="utf-8") as f:
        pubkey_text = f.read().strip()

    log("Passwordless not ready; attempting one-time key install via password…", quiet)
    if not push_pubkey_with_password(user, host, port, password, pubkey_text, quiet):
        return False

    return test_passwordless(user, host, port, quiet=True)

def main():
    parser = argparse.ArgumentParser(description="Ensure passwordless SSH by installing a public key remotely if needed.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--port", default="22")
    parser.add_argument("--password", default="")
    parser.add_argument("--key-type", default="auto", choices=["auto","ed25519","rsa","both"])
    parser.add_argument("--key-dir", default=os.path.expanduser("~/.ssh"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    host = args.host.strip()
    user = args.user.strip() or "root"
    try:
        port = int(str(args.port).strip() or "22")
    except ValueError:
        port = 22
    password = args.password
    key_mode = args.key_type
    key_dir = args.key_dir
    quiet = args.quiet

    # Quick success if already passwordless
    if test_passwordless(user, host, port, quiet=True):
        msg = f"Passwordless SSH already works for {user}@{host}"
        log(msg, quiet)
        print(json.dumps({"success": True, "message": msg, "user": user, "host": host, "port": port}))
        sys.exit(0)

    ed_pk = rsa_pk = None
    if key_mode in ("ed25519","both","auto"):
        ed_pk = ensure_keypair("ed25519", key_dir, quiet=quiet)
    if key_mode in ("rsa","both"):
        rsa_pk = ensure_keypair("rsa", key_dir, quiet=quiet)

    # Try ed25519 first for auto
    if ed_pk:
        if try_key_then_install(user, host, port, password, ed_pk, quiet=quiet):
            msg = "Passwordless SSH ready (ed25519)."
            log(msg, quiet)
            print(json.dumps({"success": True, "message": msg, "user": user, "host": host, "port": port, "key_type": "ed25519"}))
            sys.exit(0)
        log("ed25519 attempt failed.", quiet)

    # Fallback to RSA if requested/auto/both
    if key_mode in ("auto","both") or rsa_pk:
        if not rsa_pk:
            rsa_pk = ensure_keypair("rsa", key_dir, quiet=quiet)
        if try_key_then_install(user, host, port, password, rsa_pk, quiet=quiet):
            msg = "Passwordless SSH ready (rsa)."
            log(msg, quiet)
            print(json.dumps({"success": True, "message": msg, "user": user, "host": host, "port": port, "key_type": "rsa"}))
            sys.exit(0)

    msg = f"Failed to establish passwordless SSH for {user}@{host}"
    log(msg, quiet)
    print(json.dumps({"success": False, "message": msg, "user": user, "host": host, "port": port}))
    sys.exit(1)

if __name__ == "__main__":
    main()
