import threading
import time

import pytest

import task_concurrency


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("HOUSTON_MAX_CONCURRENT_PER_HOST", raising=False)
    monkeypatch.setattr(task_concurrency, "SCHEDULER_CONF_PATH", "/nonexistent/scheduler.conf")
    monkeypatch.setattr(task_concurrency, "SLOT_DIR_ROOT", str(tmp_path / "task-slots"))
    monkeypatch.setattr(task_concurrency, "POLL_INTERVAL_SEC", 0.05)
    monkeypatch.setattr(task_concurrency, "NOTIFY_REPEAT_SEC", 0.05)


def test_max_concurrent_per_host_uses_env_then_default(monkeypatch):
    assert task_concurrency.max_concurrent_per_host() == task_concurrency.DEFAULT_MAX_CONCURRENT_PER_HOST
    monkeypatch.setenv("HOUSTON_MAX_CONCURRENT_PER_HOST", "7")
    assert task_concurrency.max_concurrent_per_host() == 7


def test_gating_skipped_when_host_empty():
    entered = False
    with task_concurrency.acquire_host_slot("") as slot_info:
        entered = True
        assert slot_info == {"waited_seconds": 0.0}
    assert entered


def test_gating_skipped_when_limit_zero(monkeypatch):
    monkeypatch.setenv("HOUSTON_MAX_CONCURRENT_PER_HOST", "0")
    entered = False
    with task_concurrency.acquire_host_slot("backup.example.com"):
        entered = True
    assert entered


def test_second_run_waits_for_a_free_slot(monkeypatch):
    monkeypatch.setenv("HOUSTON_MAX_CONCURRENT_PER_HOST", "1")
    release_first = threading.Event()
    second_acquired = threading.Event()
    notifications = []

    def hold_first():
        with task_concurrency.acquire_host_slot("backup.example.com"):
            release_first.wait(timeout=5)

    def acquire_second():
        with task_concurrency.acquire_host_slot("backup.example.com", notify=notifications.append):
            second_acquired.set()

    t1 = threading.Thread(target=hold_first)
    t1.start()
    time.sleep(0.1)  # let t1 grab the only slot first

    t2 = threading.Thread(target=acquire_second)
    t2.start()

    time.sleep(0.2)
    assert not second_acquired.is_set()
    assert any("Waiting for a free task slot" in n for n in notifications)

    release_first.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert second_acquired.is_set()


def test_second_run_reports_time_spent_waiting(monkeypatch):
    monkeypatch.setenv("HOUSTON_MAX_CONCURRENT_PER_HOST", "1")
    release_first = threading.Event()
    results = {}

    def hold_first():
        with task_concurrency.acquire_host_slot("backup.example.com"):
            release_first.wait(timeout=5)

    def acquire_second():
        with task_concurrency.acquire_host_slot("backup.example.com") as slot_info:
            results["waited_seconds"] = slot_info["waited_seconds"]

    t1 = threading.Thread(target=hold_first)
    t1.start()
    time.sleep(0.1)

    t2 = threading.Thread(target=acquire_second)
    t2.start()
    time.sleep(0.3)
    release_first.set()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert results["waited_seconds"] >= 0.2


def test_different_hosts_do_not_contend(monkeypatch):
    monkeypatch.setenv("HOUSTON_MAX_CONCURRENT_PER_HOST", "1")
    both_entered = threading.Event()
    entered = {"a": False, "b": False}

    def run(host, key):
        with task_concurrency.acquire_host_slot(host):
            entered[key] = True
            if all(entered.values()):
                both_entered.set()
            time.sleep(0.2)

    t1 = threading.Thread(target=run, args=("host-a", "a"))
    t2 = threading.Thread(target=run, args=("host-b", "b"))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert both_entered.is_set()


def test_replication_and_rsync_share_the_same_slot_pool(monkeypatch):
    """The pool is keyed only by host, so different task types targeting the
    same host correctly contend for the same limited set of slots."""
    monkeypatch.setenv("HOUSTON_MAX_CONCURRENT_PER_HOST", "1")
    second_acquired = threading.Event()
    release_first = threading.Event()

    def hold_as_replication():
        with task_concurrency.acquire_host_slot("shared-host"):
            release_first.wait(timeout=5)

    def acquire_as_rsync():
        with task_concurrency.acquire_host_slot("shared-host"):
            second_acquired.set()

    t1 = threading.Thread(target=hold_as_replication)
    t1.start()
    time.sleep(0.1)

    t2 = threading.Thread(target=acquire_as_rsync)
    t2.start()
    time.sleep(0.2)
    assert not second_acquired.is_set()

    release_first.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert second_acquired.is_set()
