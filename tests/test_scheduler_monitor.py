import importlib.util

import pytest

from conftest import SCRIPTS_DIR

UNIT = "houston_scheduler_CustomTask_demo.service"


@pytest.fixture
def monitor(monkeypatch):
    spec = importlib.util.spec_from_file_location("scheduler_monitor", SCRIPTS_DIR / "scheduler-monitor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.sent = []
    module.props = {}
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(module, "get_service_result", lambda _u: dict(module.props))
    monkeypatch.setattr(module, "send_final_notification",
                        lambda unit, retry_count=0: module.sent.append((unit, retry_count)))
    return module


def _emit(monitor, message):
    monitor.handle_journal_entry({"UNIT": UNIT, "MESSAGE": message})


def test_no_retry_exit_sends_final_failure(monitor):
    monitor.props = {"Result": "exit-code", "ExecMainStatus": "90"}
    _emit(monitor, "houston_scheduler_CustomTask_demo.service: Failed with result 'exit-code'.")

    assert monitor.sent == [(UNIT, 0)]
    assert UNIT not in monitor._pending_failures


def test_retried_run_reports_retry_count_on_final_attempt(monitor):
    monitor.props = {"Result": "exit-code", "ExecMainStatus": "1"}
    _emit(monitor, "Failed with result 'exit-code'.")
    _emit(monitor, "Scheduled restart job, restart counter is at 1.")
    _emit(monitor, "Failed with result 'exit-code'.")
    _emit(monitor, "Scheduled restart job, restart counter is at 2.")
    assert monitor.sent == []

    monitor.props = {"Result": "exit-code", "ExecMainStatus": "90"}
    _emit(monitor, "Failed with result 'exit-code'.")

    assert monitor.sent == [(UNIT, 2)]


def test_start_limit_hit_still_finalizes_via_failed_to_start(monitor):
    monitor.props = {"Result": "start-limit-hit", "ExecMainStatus": "90"}
    _emit(monitor, "Failed with result 'start-limit-hit'.")
    assert monitor.sent == []

    _emit(monitor, "Failed to start Service for demo.")
    _emit(monitor, "Failed to start Service for demo.")

    assert monitor.sent == [(UNIT, 0)]
