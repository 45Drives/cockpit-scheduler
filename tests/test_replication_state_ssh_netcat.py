import subprocess
from types import SimpleNamespace

import pytest

from replication import ssh, state
from replication.transfers import netcat


def result(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_local_and_remote_resume_token_normalization(monkeypatch):
    monkeypatch.setattr(state.subprocess, "run", lambda *args, **kwargs: result(stdout="-\n"))
    assert state.get_receive_resume_token("tank/data") == ""
    monkeypatch.setattr(state, "ssh_run_args", lambda *args, **kwargs: result(stdout="1-deadbeef\n"))
    assert state.get_receive_resume_token("tank/data", "root", "host") == "1-deadbeef"


def test_clear_resume_token_returns_error_text(monkeypatch):
    monkeypatch.setattr(state.subprocess, "run", lambda *args, **kwargs: result(1, stderr="busy"))
    assert state.clear_receive_resume_token("tank/data") == (False, "busy")
    monkeypatch.setattr(state, "ssh_run_args", lambda *args, **kwargs: result())
    assert state.clear_receive_resume_token("tank/data", "root", "host") == (True, "")


def test_pending_full_send_state_round_trip(tmp_path, monkeypatch):
    path = tmp_path / "task.fullsend"
    monkeypatch.setattr(state, "_pending_full_send_path", lambda task: str(path))
    state._write_pending_full_send("job-a", "tank/data@s1", "backup/data", "push", "tank/data")
    loaded = state._read_pending_full_send("job-a")
    assert loaded["snapshot"] == "tank/data@s1"
    assert loaded["destFilesystem"] == "backup/data"
    state._clear_pending_full_send("job-a")
    assert not path.exists()


def test_ssh_command_uses_batch_options_port_and_shell_quoting(monkeypatch):
    seen = []
    monkeypatch.setattr(ssh.subprocess, "run", lambda cmd, **kwargs: seen.append((cmd, kwargs)) or result(stdout=b"ok"))
    response = ssh.ssh_run_args("root", "host", "2222", ["zfs", "get", "name with spaces"])
    command = seen[0][0]
    assert command[0] == "ssh"
    assert ["-p", "2222"] == command[command.index("-p"):command.index("-p") + 2]
    assert "root@host" in command
    assert command[-1] == "zfs get 'name with spaces'"
    assert response.returncode == 0


def test_ssh_check_raises_called_process_error(monkeypatch):
    monkeypatch.setattr(ssh.subprocess, "run", lambda *args, **kwargs: result(7, stderr=b"denied"))
    with pytest.raises(subprocess.CalledProcessError) as exc:
        ssh.ssh_run_args("root", "host", "22", ["true"], check=True)
    assert exc.value.returncode == 7


@pytest.mark.parametrize(
    "flavour,bind,send_only,expected",
    [
        ("ncat", None, False, "nc -l --recv-only 31337"),
        ("ncat", "10.0.0.1", True, "nc -l --send-only -s 10.0.0.1 31337"),
        ("openbsd", None, False, "nc -l 31337"),
        ("unknown", "10.0.0.1", False, "nc -l -s 10.0.0.1 31337"),
    ],
)
def test_netcat_listener_command_variants(monkeypatch, flavour, bind, send_only, expected):
    monkeypatch.setattr(netcat, "_detect_nc_flavour", lambda *args, **kwargs: flavour)
    assert netcat.build_nc_listen_cmd("31337", bind_address=bind, send_only=send_only) == expected


def test_netcat_connect_direction_flags(monkeypatch):
    monkeypatch.setattr(netcat, "_detect_nc_flavour", lambda *args, **kwargs: "ncat")
    assert netcat._build_nc_connect_cmd("host", "31337", recv_only=True) == ["nc", "--recv-only", "host", "31337"]
    assert netcat._build_nc_connect_cmd("host", "31337", recv_only=False) == ["nc", "--send-only", "host", "31337"]

