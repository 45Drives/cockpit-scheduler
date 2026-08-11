"""Process-wide service integration objects."""

from .logging_utils import configure_standard_streams
from notify import get_notifier

configure_standard_streams()
notifier = get_notifier()
