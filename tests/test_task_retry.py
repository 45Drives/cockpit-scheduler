import pytest

import task_retry


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("HOUSTON_SCHEDULER_UNIT", raising=False)
    monkeypatch.delenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("taskName", raising=False)
    monkeypatch.setattr(task_retry, "SCHEDULER_CONF_PATH", "/nonexistent/scheduler.conf")


def _fake_nrestarts(monkeypatch, value):
    class _Proc:
        returncode = 0
        stdout = f"{value}\n"
        stderr = ""

    monkeypatch.setattr(task_retry.subprocess, "run", lambda *a, **k: _Proc())


def _run(main_func, **kwargs):
    with pytest.raises(SystemExit) as excinfo:
        task_retry.run_with_retry_policy(main_func, **kwargs)
    return excinfo.value.code


def test_unit_name_without_prefix_is_empty(monkeypatch):
    monkeypatch.setenv("taskName", "demo")
    assert task_retry.unit_name() == ""
    assert task_retry.unit_name("houston_scheduler_ScrubTask_") == "houston_scheduler_ScrubTask_demo.service"


def test_successful_main_does_not_raise():
    task_retry.run_with_retry_policy(lambda: None)


def test_explicit_success_exit_passes_through():
    assert _run(lambda: (_ for _ in ()).throw(SystemExit(0))) == 0


def test_failure_retries_then_stops(monkeypatch):
    monkeypatch.setenv("HOUSTON_SCHEDULER_UNIT", "houston_scheduler_x.service")
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "3")

    def _fail():
        raise SystemExit(1)

    _fake_nrestarts(monkeypatch, 0)
    assert _run(_fail) == 1
    _fake_nrestarts(monkeypatch, 2)
    assert _run(_fail) == task_retry.NO_RETRY_EXIT_CODE


def test_permanent_exit_codes_are_opt_in(monkeypatch):
    monkeypatch.setenv("HOUSTON_SCHEDULER_UNIT", "houston_scheduler_x.service")
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "3")
    _fake_nrestarts(monkeypatch, 0)

    def _fail():
        raise SystemExit(2)

    assert _run(_fail) == 1
    assert _run(_fail, permanent_exit_codes=(2,)) == task_retry.NO_RETRY_EXIT_CODE


def test_string_exit_is_left_alone():
    assert _run(lambda: (_ for _ in ()).throw(SystemExit("boom"))) == "boom"
