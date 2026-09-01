import pytest

import task_retry
from replication import retry


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("HOUSTON_SCHEDULER_UNIT", raising=False)
    monkeypatch.delenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("taskName", raising=False)
    monkeypatch.setattr(task_retry, "SCHEDULER_CONF_PATH", "/nonexistent/scheduler.conf")


def _fake_nrestarts(monkeypatch, value, returncode=0):
    class _Proc:
        def __init__(self):
            self.returncode = returncode
            self.stdout = f"{value}\n"
            self.stderr = ""

    monkeypatch.setattr(task_retry.subprocess, "run", lambda *a, **k: _Proc())


def test_unit_name_falls_back_to_task_name(monkeypatch):
    monkeypatch.setenv("taskName", "rep_demo")
    assert retry._unit_name() == "houston_scheduler_ZfsReplicationTask_rep_demo.service"


def test_max_attempts_uses_env_then_default(monkeypatch):
    assert retry.max_attempts() == retry.DEFAULT_MAX_ATTEMPTS
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "5")
    assert retry.max_attempts() == 5
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "0")
    assert retry.max_attempts() == retry.DEFAULT_MAX_ATTEMPTS


def test_current_attempt_is_nrestarts_plus_one(monkeypatch):
    monkeypatch.setenv("HOUSTON_SCHEDULER_UNIT", "houston_scheduler_x.service")
    _fake_nrestarts(monkeypatch, 2)
    assert retry.current_attempt() == 3


def test_current_attempt_defaults_to_one_when_systemctl_unavailable(monkeypatch):
    monkeypatch.setenv("HOUSTON_SCHEDULER_UNIT", "houston_scheduler_x.service")

    def _boom(*a, **k):
        raise OSError("no systemctl")

    monkeypatch.setattr(task_retry.subprocess, "run", _boom)
    assert retry.current_attempt() == 1


def test_retries_until_attempt_budget_is_spent(monkeypatch):
    monkeypatch.setenv("HOUSTON_SCHEDULER_UNIT", "houston_scheduler_x.service")
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "3")

    _fake_nrestarts(monkeypatch, 0)
    assert retry.resolve_exit_code(1) == 1
    _fake_nrestarts(monkeypatch, 1)
    assert retry.resolve_exit_code(1) == 1
    _fake_nrestarts(monkeypatch, 2)
    assert retry.resolve_exit_code(1) == retry.NO_RETRY_EXIT_CODE
    _fake_nrestarts(monkeypatch, 61)
    assert retry.resolve_exit_code(1) == retry.NO_RETRY_EXIT_CODE


def test_permanent_failures_are_never_retried(monkeypatch):
    monkeypatch.setenv("HOUSTON_SCHEDULER_UNIT", "houston_scheduler_x.service")
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "10")
    _fake_nrestarts(monkeypatch, 0)
    assert retry.resolve_exit_code(retry.PERMANENT_FAILURE_EXIT_CODE) == retry.NO_RETRY_EXIT_CODE


def test_success_codes_pass_through(monkeypatch):
    assert retry.resolve_exit_code(0) == 0
    assert retry.resolve_exit_code(None) is None
    assert retry.resolve_exit_code(retry.NO_RETRY_EXIT_CODE) == retry.NO_RETRY_EXIT_CODE


def test_burst_of_one_never_retries(monkeypatch):
    monkeypatch.setenv("HOUSTON_SCHEDULER_UNIT", "houston_scheduler_x.service")
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "1")
    _fake_nrestarts(monkeypatch, 0)
    assert retry.resolve_exit_code(1) == retry.NO_RETRY_EXIT_CODE
