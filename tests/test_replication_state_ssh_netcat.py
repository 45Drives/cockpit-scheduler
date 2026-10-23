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


NCAT_HELP = "/usr/bin/ncat\nNcat 7.92 ( https://nmap.org/ncat )\n      --send-only           Only send data, ignoring received; quit on EOF\n"
OPENBSD_HELP = (
    "/usr/bin/nc.openbsd\nOpenBSD netcat (Debian patchlevel 1.218-4ubuntu1)\n"
    "usage: nc [-46CDdFhklNnrStUuvZz]\n"
    "\t-N\t\tShutdown the network socket after EOF on stdin\n"
    "\t-q secs\t\tquit after EOF on stdin and delay of secs\n"
)
OPENBSD_NO_N_HELP = "OpenBSD netcat\n\t-q secs\t\tquit after EOF on stdin and delay of secs\n"
TRADITIONAL_HELP = "/bin/nc.traditional\n[v1.10-47]\n\t-q secs\t\t\tquit after EOF on stdin and delay of secs\n"
UNSUPPORTED_HELP = "usage: nc [-l] host port\n\t-l\t\tlisten mode\n"


@pytest.mark.parametrize(
    "probe,expected",
    [
        (NCAT_HELP, ("ncat", ["--send-only"])),
        (OPENBSD_HELP, ("openbsd", ["-N"])),
        (OPENBSD_NO_N_HELP, ("openbsd", ["-q", "0"])),
        (TRADITIONAL_HELP, ("traditional", ["-q", "0"])),
        (UNSUPPORTED_HELP, ("unknown", [])),
        ("", ("unknown", [])),
    ],
)
def test_netcat_classifies_flavour_and_sender_eof_args(probe, expected):
    assert netcat._classify_nc(probe) == expected


def test_netcat_probe_does_not_depend_on_which(monkeypatch):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return result(stdout="/usr/bin/nc.openbsd\n", stderr=OPENBSD_HELP)

    monkeypatch.setattr(netcat.subprocess, "run", fake_run)
    monkeypatch.setattr(netcat, "ssh_base_args", lambda *args: ["ssh", "root@host"])
    assert netcat._detect_nc("root", "host") == ("openbsd", ["-N"])
    assert len(seen) == 1
    assert "which" not in seen[0][-1]
    assert "command -v nc" in seen[0][-1]


def test_netcat_detection_failure_warns_and_uses_plain_nc(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("ssh", 10)

    monkeypatch.setattr(netcat.subprocess, "run", fail)
    assert netcat._detect_nc() == ("unknown", [])
    assert "no close-on-EOF option" in capsys.readouterr().out


@pytest.mark.parametrize(
    "detected,bind,send_only,expected",
    [
        (("ncat", ["--send-only"]), None, False, "nc -l --recv-only 31337"),
        (("ncat", ["--send-only"]), "10.0.0.1", True, "nc -l --send-only -s 10.0.0.1 31337"),
        (("openbsd", ["-N"]), None, True, "nc -l -N 31337"),
        (("openbsd", ["-N"]), None, False, "nc -l 31337"),
        (("traditional", ["-q", "0"]), "10.0.0.1", True, "nc -l -q 0 -s 10.0.0.1 31337"),
        (("unknown", []), "10.0.0.1", True, "nc -l -s 10.0.0.1 31337"),
    ],
)
def test_netcat_listener_command_variants(monkeypatch, detected, bind, send_only, expected):
    monkeypatch.setattr(netcat, "_detect_nc", lambda *args, **kwargs: detected)
    assert netcat.build_nc_listen_cmd("31337", bind_address=bind, send_only=send_only) == expected


@pytest.mark.parametrize(
    "detected,receive,send",
    [
        (("ncat", ["--send-only"]), ["nc", "--recv-only", "host", "31337"], ["nc", "--send-only", "host", "31337"]),
        (("openbsd", ["-N"]), ["nc", "host", "31337"], ["nc", "-N", "host", "31337"]),
        (("traditional", ["-q", "0"]), ["nc", "host", "31337"], ["nc", "-q", "0", "host", "31337"]),
        (("unknown", []), ["nc", "host", "31337"], ["nc", "host", "31337"]),
    ],
)
def test_netcat_connect_direction_flags(monkeypatch, detected, receive, send):
    monkeypatch.setattr(netcat, "_detect_nc", lambda *args, **kwargs: detected)
    assert netcat._build_nc_connect_cmd("host", "31337", recv_only=True) == receive
    assert netcat._build_nc_connect_cmd("host", "31337", recv_only=False) == send


@pytest.mark.parametrize(
    "recv_err,sender_rc,sender_err,expected",
    [
        (b"cannot receive: out of space\n", 0, "", "ERROR: local recv error: cannot receive: out of space"),
        (
            "cannot receive: incomplete stream",
            1,
            b"zfs send failed: I/O error\n",
            "ERROR: local recv error: cannot receive: incomplete stream\n"
            "[Remote Side] Error during send: zfs send failed: I/O error",
        ),
        (None, 255, None, "ERROR: local recv error: "),
    ],
)
def test_recv_failure_message_reports_recv_first(recv_err, sender_rc, sender_err, expected):
    from replication.transfers.common import _recv_failure_message

    assert _recv_failure_message(recv_err, sender_rc, sender_err) == expected

