import importlib
import io
import subprocess
from pathlib import Path

import pytest

from replication import ssh as ssh_module


CIPHER_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scheduler"
    / "src"
    / "scripts"
    / "list-ssh-ciphers.py"
)

# The probe script is bundled into the frontend, so it is absent on an installed appliance.
requires_cipher_script = pytest.mark.skipif(
    not CIPHER_SCRIPT.is_file(),
    reason="list-ssh-ciphers.py is only present in a source checkout",
)


def load_cipher_script():
    spec = importlib.util.spec_from_file_location("list_ssh_ciphers", CIPHER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def reload_ssh(monkeypatch):
    """Reload replication.ssh so module-level cipher wiring re-reads the environment."""
    def _reload(**env):
        for key in ("zfsRepConfig_sendOptions_sshCipher", "ZFS_REP_SSH_CIPHER"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(ssh_module)

    yield _reload
    importlib.reload(ssh_module)


def cipher_opt(module):
    opts = module.SSH_BASE_OPTS
    for index, value in enumerate(opts):
        if value.startswith("Ciphers="):
            return value.split("=", 1)[1]
    return None


def test_no_cipher_option_when_unset(reload_ssh):
    module = reload_ssh()
    assert cipher_opt(module) is None


def test_task_scoped_cipher_is_applied(reload_ssh):
    module = reload_ssh(zfsRepConfig_sendOptions_sshCipher="aes128-gcm@openssh.com")
    assert cipher_opt(module) == "aes128-gcm@openssh.com"


def test_host_wide_cipher_still_honoured(reload_ssh):
    module = reload_ssh(ZFS_REP_SSH_CIPHER="aes256-ctr")
    assert cipher_opt(module) == "aes256-ctr"


def test_task_scoped_cipher_wins_over_host_wide(reload_ssh):
    module = reload_ssh(
        zfsRepConfig_sendOptions_sshCipher="aes128-gcm@openssh.com",
        ZFS_REP_SSH_CIPHER="aes256-ctr",
    )
    assert cipher_opt(module) == "aes128-gcm@openssh.com"


def test_blank_task_cipher_falls_back_to_host_wide(reload_ssh):
    module = reload_ssh(
        zfsRepConfig_sendOptions_sshCipher="   ",
        ZFS_REP_SSH_CIPHER="aes256-gcm@openssh.com",
    )
    assert cipher_opt(module) == "aes256-gcm@openssh.com"


def test_cipher_reaches_remote_estimate_argv(reload_ssh, monkeypatch):
    module = reload_ssh(zfsRepConfig_sendOptions_sshCipher="aes128-gcm@openssh.com")
    seen = []

    class FakeProc:
        def __init__(self, args, **kwargs):
            seen.append(args)
            self.stdout = io.BytesIO(b"size\t1024\n")
            self.stderr = io.BytesIO()
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(module.subprocess, "Popen", FakeProc)
    module.estimate_send_size_remote("root", "host", 22, ["zfs", "send", "tank/a@s1"])

    argv = seen[0]
    assert "Ciphers=aes128-gcm@openssh.com" in argv


def test_remote_estimate_rejects_wrapped_negative(reload_ssh, monkeypatch):
    module = reload_ssh()

    class FakeProc:
        def __init__(self, args, **kwargs):
            self.stdout = io.BytesIO(b"size\t18446744072580570568\n")
            self.stderr = io.BytesIO()
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(module.subprocess, "Popen", FakeProc)
    result = module.estimate_send_size_remote("root", "host", 22, ["zfs", "send", "tank/a@s1"])
    assert result is None


# ---------------------------------------------------------------------------
# list-ssh-ciphers.py
# ---------------------------------------------------------------------------

PEER_STDERR = """debug2: local client KEXINIT proposal
debug2: ciphers stoc: chacha20-poly1305@openssh.com,aes128-ctr
debug2: peer server KEXINIT proposal
debug2: KEX algorithms: curve25519-sha256
debug2: ciphers ctos: aes128-ctr,aes128-gcm@openssh.com
debug2: ciphers stoc: aes128-ctr,aes256-ctr,aes128-gcm@openssh.com
debug2: MACs stoc: hmac-sha2-256
"""


class CompletedStub:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


@requires_cipher_script
def test_local_ciphers_parses_ssh_q_output(monkeypatch):
    module = load_cipher_script()
    monkeypatch.setattr(
        module.subprocess, "run",
        lambda *a, **k: CompletedStub(stdout="aes128-ctr\n\naes256-gcm@openssh.com\n"),
    )
    assert module.local_ciphers() == ["aes128-ctr", "aes256-gcm@openssh.com"]


@requires_cipher_script
def test_local_ciphers_empty_when_ssh_missing(monkeypatch):
    module = load_cipher_script()

    def boom(*a, **k):
        raise OSError("no ssh")

    monkeypatch.setattr(module.subprocess, "run", boom)
    assert module.local_ciphers() == []


# The client prints its own proposal first, so anchoring on the peer marker matters.
@requires_cipher_script
def test_remote_ciphers_reads_peer_proposal_not_local(monkeypatch):
    module = load_cipher_script()
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **k: CompletedStub(stderr=PEER_STDERR, returncode=255)
    )
    ciphers, error = module.remote_ciphers("root", "host", 22)
    assert ciphers == ["aes128-ctr", "aes256-ctr", "aes128-gcm@openssh.com"]
    assert error == ""


@requires_cipher_script
def test_remote_ciphers_reports_missing_proposal(monkeypatch):
    module = load_cipher_script()
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **k: CompletedStub(stderr="ssh: connect: refused\n", returncode=255)
    )
    ciphers, error = module.remote_ciphers("root", "host", 22)
    assert ciphers == []
    assert "host" in error


@requires_cipher_script
def test_remote_ciphers_reports_timeout(monkeypatch):
    module = load_cipher_script()

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=30)

    monkeypatch.setattr(module.subprocess, "run", boom)
    ciphers, error = module.remote_ciphers("root", "host", 22)
    assert ciphers == []
    assert "Timed out" in error


@requires_cipher_script
def test_remote_probe_uses_requested_port(monkeypatch):
    module = load_cipher_script()
    seen = []
    monkeypatch.setattr(
        module.subprocess, "run",
        lambda cmd, **k: (seen.append(cmd), CompletedStub(stderr=PEER_STDERR))[1],
    )
    module.remote_ciphers("backup", "host", 2222)
    assert "2222" in seen[0]
    assert "backup@host" in seen[0]
