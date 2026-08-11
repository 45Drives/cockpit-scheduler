from conftest import FakeProcess, RecordingNotifier
from replication.transfers import pull, push, resume


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


def test_resume_push_rejects_unknown_transfer_method(monkeypatch):
    monkeypatch.setattr(resume.subprocess, "Popen", lambda cmd, **kwargs: FakeProcess(cmd, with_stdin=False))
    monkeypatch.setattr(resume, "estimate_send_size", lambda cmd: None)
    ok, error = resume.resume_receive_push("1-token", "backup/target", recvHost="host", transferMethod="carrier-pigeon")
    assert ok is False
    assert "only supported for local, ssh, or netcat" in error
