from conftest import FakeProcess, RecordingNotifier
from replication.transfers import common, pull, push, resume


def test_local_push_constructs_force_receive_and_completes(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd[:2] == ["zfs", "recv"]))

    recorder = RecordingNotifier()
    monkeypatch.setattr(push.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(push, "estimate_send_size", lambda cmd: 100)
    monkeypatch.setattr(push, "stream_with_progress_stall", lambda *args, **kwargs: (100, False))
    monkeypatch.setattr(push, "_wait_with_finalize_heartbeat", lambda *args, **kwargs: 0)
    monkeypatch.setattr(push, "_communicate_with_finalize_heartbeat", lambda *args, **kwargs: (b"", b""))
    monkeypatch.setattr(push, "notifier", recorder)
    push.send_snapshot_push("tank/source@s1", "backup/target", transferMethod="local", forceOverwrite=True)
    assert commands[0] == ["zfs", "send", "tank/source@s1"]
    assert commands[1] == ["zfs", "recv", "-s", "-F", "backup/target"]
    assert recorder.messages[-1] == "STATUS=Local receive completed."


def test_ssh_pull_standard_pipeline_constructs_both_ends(monkeypatch):
    local_commands = []
    remote_commands = []

    def fake_popen(cmd, **kwargs):
        local_commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "mbuffer"))

    def fake_ssh(*args, **kwargs):
        remote_commands.append(args[3])
        return FakeProcess(args[3], with_stdin=False)

    recorder = RecordingNotifier()
    monkeypatch.setattr(pull.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(pull, "ssh_popen_args", fake_ssh)
    monkeypatch.setattr(pull, "estimate_send_size_remote", lambda *args: 100)
    monkeypatch.setattr(pull, "stream_with_progress_stall", lambda *args, **kwargs: (100, False))
    monkeypatch.setattr(pull, "DIRECT_PIPE_ENABLED", False)
    monkeypatch.setattr(pull, "notifier", recorder)
    pull.send_snapshot_pull(
        "tank/source@s2", "backup/target", remoteBaseSnapName="tank/source@s1",
        remoteHost="host", remoteSshPort="2222", remoteUser="root", forceOverwrite=True,
    )
    assert remote_commands == [["zfs", "send", "-i", "tank/source@s1", "tank/source@s2"]]
    assert ["zfs", "recv", "-s", "-F", "backup/target"] in local_commands
    assert recorder.messages[-1] == "STATUS=Pull receive completed."


def test_local_resume_push_uses_token_and_force_receive(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd[:2] == ["zfs", "recv"]))

    recorder = RecordingNotifier()
    monkeypatch.setattr(resume.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(resume, "estimate_send_size", lambda cmd: 2048)
    monkeypatch.setattr(resume, "stream_with_progress_stall", lambda *args, **kwargs: (2048, False))
    monkeypatch.setattr(resume, "notifier", recorder)
    ok, error = resume.resume_receive_push("1-token", "backup/target", transferMethod="local", forceOverwrite=True)
    assert (ok, error) == (True, "")
    assert commands == [
        ["zfs", "send", "-t", "1-token"],
        ["zfs", "recv", "-s", "-F", "backup/target"],
    ]
    assert recorder.messages[-1] == "STATUS=Local resume receive completed."


def test_ssh_resume_pull_uses_remote_token_stream(monkeypatch):
    local_commands = []
    remote_commands = []

    def fake_popen(cmd, **kwargs):
        local_commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "mbuffer"))

    def fake_ssh(*args, **kwargs):
        remote_commands.append(args[3])
        return FakeProcess(args[3], with_stdin=False)

    recorder = RecordingNotifier()
    monkeypatch.setattr(resume.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(resume, "ssh_popen_args", fake_ssh)
    monkeypatch.setattr(resume, "estimate_send_size_remote", lambda *args: 2048)
    monkeypatch.setattr(resume, "stream_with_progress_stall", lambda *args, **kwargs: (2048, False))
    monkeypatch.setattr(resume, "notifier", recorder)
    ok, error = resume.resume_receive_pull(
        "1-token", "backup/target", remoteHost="host", remoteSshPort="2222", remoteUser="root", forceOverwrite=True
    )
    assert (ok, error) == (True, "")
    assert remote_commands == [["zfs", "send", "-t", "1-token"]]
    assert ["zfs", "recv", "-s", "-F", "backup/target"] in local_commands
    assert recorder.messages[-1] == "STATUS=Pull resume receive completed."


def test_mbuffer_push_constructs_listener_and_network_sender(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "mbuffer"))

    recorder = RecordingNotifier()
    monkeypatch.setattr(push.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(push, "estimate_send_size", lambda cmd: 1024)
    monkeypatch.setattr(push, "stream_with_progress_stall", lambda *args, **kwargs: (1024, False))
    monkeypatch.setattr(push, "_wait_with_finalize_heartbeat", lambda *args, **kwargs: 0)
    monkeypatch.setattr(push, "_wait_for_port_remote", lambda *args, **kwargs: True)
    monkeypatch.setattr(push, "ssh_run_args", lambda *args, **kwargs: type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})())
    monkeypatch.setattr(push, "notifier", recorder)

    push.send_snapshot_push(
        "tank/source@s1",
        "backup/target",
        recvHost="192.0.2.10",
        recvSshPort="2222",
        recvHostUser="root",
        mBufferSize="1",
        mBufferUnit="G",
        transferMethod="mbuffer",
        recvDataPort="31337",
    )

    assert commands[0] == ["zfs", "send", "tank/source@s1"]
    assert commands[1][0] == "ssh"
    assert commands[2][:4] == ["mbuffer", "-s", "256k", "-m"]
    assert commands[2][-2:] == ["-O", "192.0.2.10:31337"]
    assert recorder.messages[-1] == "STATUS=mBuffer send/receive completed."


def test_mbuffer_resume_push_constructs_listener_and_network_sender(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "mbuffer"))

    recorder = RecordingNotifier()
    monkeypatch.setattr(resume.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(resume, "estimate_send_size", lambda cmd: 2048)
    monkeypatch.setattr(resume, "stream_with_progress_stall", lambda *args, **kwargs: (2048, False))
    monkeypatch.setattr(resume, "_wait_for_port_remote", lambda *args, **kwargs: True)
    monkeypatch.setattr(resume, "notifier", recorder)

    ok, error = resume.resume_receive_push(
        "1-token",
        "backup/target",
        recvHost="192.0.2.10",
        recvSshPort="2222",
        recvHostUser="root",
        transferMethod="mbuffer",
        recvDataPort="31337",
    )

    assert (ok, error) == (True, "")
    assert commands[0] == ["zfs", "send", "-t", "1-token"]
    assert commands[1][0] == "ssh"
    assert commands[2][:4] == ["mbuffer", "-s", "256k", "-m"]
    assert commands[2][-2:] == ["-O", "192.0.2.10:31337"]
    assert recorder.messages[-1] == "STATUS=mBuffer resume send/receive completed."


def test_mbuffer_pull_constructs_listener_and_remote_network_sender(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "zfs" and "recv" in cmd))

    recorder = RecordingNotifier()
    monkeypatch.setattr(pull.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(pull, "estimate_send_size_remote", lambda *args: 1024)
    monkeypatch.setattr(pull, "stream_with_progress_stall", lambda *args, **kwargs: (1024, False))
    monkeypatch.setattr(pull, "_wait_with_finalize_heartbeat", lambda *args, **kwargs: 0)
    monkeypatch.setattr(pull, "_communicate_with_finalize_heartbeat", lambda *args, **kwargs: (b"", b""))
    monkeypatch.setattr(pull, "resolve_mbuffer_callback_target_for_remote", lambda *args, **kwargs: ("203.0.113.7", "203.0.113.7", "203.0.113.7:31337"))
    monkeypatch.setattr(pull, "preflight_remote_callback_connectivity", lambda *args, **kwargs: (True, "", True))
    monkeypatch.setattr(pull, "notifier", recorder)

    pull.send_snapshot_pull(
        "tank/source@s2",
        "backup/target",
        remoteBaseSnapName="tank/source@s1",
        remoteHost="192.0.2.20",
        remoteSshPort="2222",
        remoteUser="root",
        forceOverwrite=True,
        transferMethod="mbuffer",
        recvDataPort="31337",
    )

    assert commands[0][:4] == ["mbuffer", "-s", "256k", "-m"]
    assert commands[0][-2:] == ["-I", "31337"]
    assert commands[1] == ["zfs", "recv", "-s", "-F", "backup/target"]
    assert commands[2][0] == "ssh"
    assert recorder.messages[-1] == "STATUS=mBuffer pull receive completed."


def test_mbuffer_resume_pull_constructs_listener_and_remote_network_sender(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "zfs" and "recv" in cmd))

    recorder = RecordingNotifier()
    monkeypatch.setattr(resume.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(resume, "estimate_send_size_remote", lambda *args: 2048)
    monkeypatch.setattr(resume, "stream_with_progress_stall", lambda *args, **kwargs: (2048, False))
    monkeypatch.setattr(resume, "resolve_mbuffer_callback_target_for_remote", lambda *args, **kwargs: ("203.0.113.7", "203.0.113.7", "203.0.113.7:31337"))
    monkeypatch.setattr(resume, "preflight_remote_callback_connectivity", lambda *args, **kwargs: (True, "", True))
    monkeypatch.setattr(resume, "notifier", recorder)

    ok, error = resume.resume_receive_pull(
        "1-token",
        "backup/target",
        remoteHost="192.0.2.20",
        remoteSshPort="2222",
        remoteUser="root",
        forceOverwrite=True,
        transferMethod="mbuffer",
        recvDataPort="31337",
    )

    assert (ok, error) == (True, "")
    assert commands[0][:4] == ["mbuffer", "-s", "256k", "-m"]
    assert commands[0][-2:] == ["-I", "31337"]
    assert commands[1] == ["zfs", "recv", "-s", "-F", "backup/target"]
    assert commands[2][0] == "ssh"
    assert recorder.messages[-1] == "STATUS=mBuffer pull resume receive completed."


def test_mbuffer_pull_uses_explicit_callback_host_when_set(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "zfs" and "recv" in cmd))

    recorder = RecordingNotifier()
    monkeypatch.setattr(pull.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(pull, "estimate_send_size_remote", lambda *args: 512)
    monkeypatch.setattr(pull, "stream_with_progress_stall", lambda *args, **kwargs: (512, False))
    monkeypatch.setattr(pull, "_wait_with_finalize_heartbeat", lambda *args, **kwargs: 0)
    monkeypatch.setattr(pull, "_communicate_with_finalize_heartbeat", lambda *args, **kwargs: (b"", b""))
    monkeypatch.setattr(pull, "resolve_mbuffer_callback_target_for_remote", lambda *args, **kwargs: ("10.0.0.15", "10.0.0.15", "10.0.0.15:31337"))
    monkeypatch.setattr(pull, "preflight_remote_callback_connectivity", lambda *args, **kwargs: (True, "", True))
    monkeypatch.setattr(pull, "notifier", recorder)

    pull.send_snapshot_pull(
        "tank/source@s2",
        "backup/target",
        remoteHost="192.0.2.20",
        remoteSshPort="2222",
        remoteUser="root",
        transferMethod="mbuffer",
        recvDataPort="31337",
        mbufferCallbackHost="10.0.0.15",
    )

    assert commands[2][0] == "ssh"
    remote_cmd = commands[2][-1]
    assert "-O 10.0.0.15:31337" in remote_cmd


def test_mbuffer_resume_pull_uses_explicit_callback_host_when_set(monkeypatch):
    commands = []

    def fake_popen(cmd, **kwargs):
        commands.append(cmd)
        return FakeProcess(cmd, with_stdin=(cmd and cmd[0] == "zfs" and "recv" in cmd))

    recorder = RecordingNotifier()
    monkeypatch.setattr(resume.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(resume, "estimate_send_size_remote", lambda *args: 1024)
    monkeypatch.setattr(resume, "stream_with_progress_stall", lambda *args, **kwargs: (1024, False))
    monkeypatch.setattr(resume, "resolve_mbuffer_callback_target_for_remote", lambda *args, **kwargs: ("10.0.0.15", "10.0.0.15", "10.0.0.15:31337"))
    monkeypatch.setattr(resume, "preflight_remote_callback_connectivity", lambda *args, **kwargs: (True, "", True))
    monkeypatch.setattr(resume, "notifier", recorder)

    ok, error = resume.resume_receive_pull(
        "1-token",
        "backup/target",
        remoteHost="192.0.2.20",
        remoteSshPort="2222",
        remoteUser="root",
        forceOverwrite=True,
        transferMethod="mbuffer",
        recvDataPort="31337",
        mbufferCallbackHost="10.0.0.15",
    )

    assert (ok, error) == (True, "")
    assert commands[2][0] == "ssh"
    remote_cmd = commands[2][-1]
    assert "-O 10.0.0.15:31337" in remote_cmd


def test_resume_push_rejects_unknown_transfer_method(monkeypatch):
    monkeypatch.setattr(resume.subprocess, "Popen", lambda cmd, **kwargs: FakeProcess(cmd, with_stdin=False))
    monkeypatch.setattr(resume, "estimate_send_size", lambda cmd: None)
    ok, error = resume.resume_receive_push("1-token", "backup/target", recvHost="host", transferMethod="carrier-pigeon")
    assert ok is False
    assert "only supported for local, ssh, netcat, or mbuffer" in error


def test_resolve_mbuffer_callback_target_auto_mode_uses_literal_and_port():
    expr, display, cli = common.resolve_mbuffer_callback_target("", "31337")
    assert expr == "${SSH_CLIENT%% *}"
    assert display == "<ssh-client-source-ip>"
    assert cli == "${SSH_CLIENT%% *}:31337"
