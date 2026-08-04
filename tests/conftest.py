import io
import sys
from pathlib import Path


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "system_files"
    / "opt"
    / "45drives"
    / "houston"
    / "scheduler"
    / "scripts"
)

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


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

