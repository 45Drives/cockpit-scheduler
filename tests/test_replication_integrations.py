import json
from types import SimpleNamespace

import notify

from replication import notifications


def test_systemd_notifier_fallback_supports_abstract_socket(monkeypatch):
    sent = []

    class Socket:
        def sendto(self, payload, path):
            sent.append((payload, path))

    monkeypatch.setattr(notify, "_sdnotify_available", False)
    monkeypatch.setattr(notify.socket, "socket", lambda *args: Socket())
    monkeypatch.setenv("NOTIFY_SOCKET", "@houston-test")
    notifier = notify.Notifier()
    notifier.notify("STATUS=Transferring… 50.0% complete")
    assert sent == [("STATUS=Transferring… 50.0% complete".encode("utf-8"), "\0houston-test")]


def test_houston_notification_serializes_payload(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(notifications, "open", lambda *args, **kwargs: (tmp_path / "notify.log").open("a"), raising=False)
    monkeypatch.setattr(notifications.subprocess, "run", lambda cmd, **kwargs: calls.append((cmd, kwargs)) or SimpleNamespace(returncode=0))
    payload = {"event": "zfs_replication_failed", "errors": "boom"}
    notifications.send_houston_notification(payload)
    assert calls[0][0][:2] == ["python3", "/opt/45drives/houston/houston-notify"]
    assert json.loads(calls[0][0][2]) == payload

