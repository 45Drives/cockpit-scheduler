import io
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "system_files"
    / "opt"
    / "45drives"
    / "houston"
    / "scheduler"
    / "scripts"
)

if not SCRIPTS_DIR.is_dir():
    # Installed layout: tests/ sits beside scripts/ under /opt/45drives/houston/scheduler.
    SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Opt-in suites: skipped when collecting a directory, run when named on the command line
# (pytest tests/test_zfs_replication_consolidate.py) or with --run-consolidate.
# The consolidation migration script lives in the repo's top-level scripts/ and is not
# installed on appliances, so the test cannot even import there.
OPT_IN_TESTS = {"test_zfs_replication_consolidate.py": "--run-consolidate"}


def pytest_addoption(parser):
    parser.addoption(
        "--run-consolidate", action="store_true", default=False,
        help="also run the zfs-replication-consolidate migration tests",
    )


def _ignore_opt_in(name, config):
    option = OPT_IN_TESTS.get(name)
    if option and not config.getoption(option):
        return True
    return None


# pytest 7 added collection_path and later dropped the py.path `path` argument.
if int(pytest.__version__.split(".")[0]) >= 7:
    def pytest_ignore_collect(collection_path, config):
        return _ignore_opt_in(collection_path.name, config)
else:
    def pytest_ignore_collect(path, config):
        return _ignore_opt_in(path.basename, config)


class RecordingNotifier:
    def __init__(self):
        self.messages = []

    def notify(self, message):
        self.messages.append(message)


class FakeProcess:
    """Reusable mock subprocess.Popen for testing transfer pipelines."""
    _next_pid = 100

    def __init__(self, args, with_stdin=True, communicate_result=(b"", b""), returncode=0):
        self.args = args
        self.pid = FakeProcess._next_pid
        FakeProcess._next_pid += 1
        self.stdin = io.BytesIO() if with_stdin else None
        self.stdout = io.BytesIO(b"payload")
        self.stderr = io.BytesIO()
        self.returncode = returncode
        self._communicate_result = communicate_result
        self.killed = False
        self.terminated = False

    def wait(self, timeout=None):
        return self.returncode

    def communicate(self, timeout=None):
        return self._communicate_result

    def kill(self):
        self.killed = True

    def terminate(self):
        self.terminated = True

