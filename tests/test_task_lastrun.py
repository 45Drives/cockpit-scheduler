import pytest

import task_lastrun
import task_retry


@pytest.fixture(autouse=True)
def marker_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(task_lastrun, "SYSTEMD_DIR", str(tmp_path))
    monkeypatch.delenv("HOUSTON_SCHEDULER_UNIT", raising=False)
    monkeypatch.delenv("taskName", raising=False)
    monkeypatch.setattr(task_retry, "SCHEDULER_CONF_PATH", "/nonexistent/scheduler.conf")
    return tmp_path


def _read(marker_dir, unit="houston_scheduler_ScrubTask_demo"):
    return (marker_dir / f"{unit}.lastrun").read_text().strip().split()


def _fake_nrestarts(monkeypatch, value):
    class _Proc:
        returncode = 0
        stdout = f"{value}\n"
        stderr = ""

    monkeypatch.setattr(task_retry.subprocess, "run", lambda *a, **k: _Proc())


@pytest.mark.parametrize(
    "unit,expected",
    [
        ("houston_scheduler_ScrubTask_demo.service", "houston_scheduler_ScrubTask_demo.lastrun"),
        ("houston_scheduler_ScrubTask_demo", "houston_scheduler_ScrubTask_demo.lastrun"),
    ],
)
def test_service_suffix_is_optional(marker_dir, unit, expected):
    assert task_lastrun.marker_path(unit) == str(marker_dir / expected)


@pytest.mark.parametrize("unit", ["", "   ", "../../etc/passwd", "a/b", ".hidden", "bad name"])
def test_unusable_unit_names_are_refused(unit):
    assert task_lastrun.marker_path(unit) == ""


def test_persist_refusing_a_name_writes_nothing(marker_dir):
    task_lastrun.persist("../../etc/passwd")
    assert list(marker_dir.iterdir()) == []


def test_persist_leaves_no_temp_file_behind(marker_dir):
    task_lastrun.persist("houston_scheduler_ScrubTask_demo")
    assert [p.name for p in marker_dir.iterdir()] == ["houston_scheduler_ScrubTask_demo.lastrun"]


def test_marker_is_a_single_line(marker_dir):
    """The bulk reader uses `tail -n 1`, so the record must fit on one line."""
    task_lastrun.persist("houston_scheduler_ScrubTask_demo")
    contents = (marker_dir / "houston_scheduler_ScrubTask_demo.lastrun").read_text()
    assert contents.count("\n") == 1 and contents.endswith("\n")


def test_success_is_recorded(marker_dir, monkeypatch):
    monkeypatch.setenv("taskName", "demo")
    task_retry.run_with_retry_policy(lambda: None, unit_prefix="houston_scheduler_ScrubTask_")
    epoch, outcome = _read(marker_dir)
    assert int(epoch) > 0
    assert outcome == task_lastrun.SUCCESS


def test_explicit_zero_exit_is_recorded_as_success(marker_dir, monkeypatch):
    monkeypatch.setenv("taskName", "demo")
    with pytest.raises(SystemExit):
        task_retry.run_with_retry_policy(
            lambda: (_ for _ in ()).throw(SystemExit(0)),
            unit_prefix="houston_scheduler_ScrubTask_",
        )
    assert _read(marker_dir)[1] == task_lastrun.SUCCESS


def test_failure_is_recorded(marker_dir, monkeypatch):
    monkeypatch.setenv("taskName", "demo")
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "3")
    _fake_nrestarts(monkeypatch, 0)

    def _fail():
        raise SystemExit(1)

    with pytest.raises(SystemExit):
        task_retry.run_with_retry_policy(_fail, unit_prefix="houston_scheduler_ScrubTask_")
    assert _read(marker_dir)[1] == task_lastrun.FAILED


def test_uncaught_exception_is_recorded_as_failure(marker_dir, monkeypatch):
    monkeypatch.setenv("taskName", "demo")

    def _boom():
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError):
        task_retry.run_with_retry_policy(_boom, unit_prefix="houston_scheduler_ScrubTask_")
    assert _read(marker_dir)[1] == task_lastrun.FAILED


def test_failure_overwrites_an_earlier_success(marker_dir, monkeypatch):
    monkeypatch.setenv("taskName", "demo")
    monkeypatch.setenv("HOUSTON_SCHEDULER_MAX_ATTEMPTS", "3")
    task_retry.run_with_retry_policy(lambda: None, unit_prefix="houston_scheduler_ScrubTask_")
    assert _read(marker_dir)[1] == task_lastrun.SUCCESS

    _fake_nrestarts(monkeypatch, 0)
    with pytest.raises(SystemExit):
        task_retry.run_with_retry_policy(
            lambda: (_ for _ in ()).throw(SystemExit(1)),
            unit_prefix="houston_scheduler_ScrubTask_",
        )
    assert _read(marker_dir)[1] == task_lastrun.FAILED


def test_unwritable_marker_does_not_break_the_run(marker_dir, monkeypatch):
    monkeypatch.setenv("taskName", "demo")
    monkeypatch.setattr(task_lastrun, "SYSTEMD_DIR", "/nonexistent/dir")
    task_retry.run_with_retry_policy(lambda: None, unit_prefix="houston_scheduler_ScrubTask_")
