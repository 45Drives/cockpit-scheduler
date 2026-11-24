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
    # The unit's live state is the final attempt's, whatever entry is being processed.
    monkeypatch.setattr(module, "get_service_result",
                        lambda _u: {"Result": "exit-code", "ExecMainStatus": "90"})
    monkeypatch.setattr(module, "send_final_notification",
                        lambda unit, retry_count=0: module.sent.append((unit, retry_count)))
    return module


def _emit(monitor, message):
    monitor.handle_journal_entry({"UNIT": UNIT, "MESSAGE": message})


def _attempt_failed(monitor, status, result="exit-code"):
    _emit(monitor, f"{UNIT}: Main process exited, code=exited, status={status}/FAILURE")
    _emit(monitor, f"{UNIT}: Failed with result '{result}'.")


def test_no_retry_exit_sends_final_failure(monitor):
    _attempt_failed(monitor, 90)

    assert monitor.sent == [(UNIT, 0)]
    assert UNIT not in monitor._pending_failures


def test_retried_run_reports_retry_count_on_final_attempt(monitor):
    _attempt_failed(monitor, 1)
    _emit(monitor, "Scheduled restart job, restart counter is at 1.")
    _attempt_failed(monitor, 1)
    _emit(monitor, "Scheduled restart job, restart counter is at 2.")
    assert monitor.sent == []

    _attempt_failed(monitor, 90)

    assert monitor.sent == [(UNIT, 2)]


def test_earlier_attempt_is_not_finalized_by_the_units_later_exit_status(monitor):
    # Journal entries delivered late: the unit has already exited 90 (see fixture),
    # but the first attempt's entries, which say status 1, are processed first.
    _attempt_failed(monitor, 1)

    assert monitor.sent == []
    assert UNIT in monitor._pending_failures


def test_start_limit_hit_still_finalizes_via_failed_to_start(monitor):
    _attempt_failed(monitor, 90, result="start-limit-hit")
    assert monitor.sent == []

    _emit(monitor, "Failed to start Service for demo.")
    _emit(monitor, "Failed to start Service for demo.")

    assert monitor.sent == [(UNIT, 0)]
