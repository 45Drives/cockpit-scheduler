#!/usr/bin/env python3
import os
import socket

try:
    # Optional dependency
    from sdnotify import SystemdNotifier  # type: ignore
    _sdnotify_available = True
except Exception:
    _sdnotify_available = False


class Notifier:
    def __init__(self):
        if _sdnotify_available:
            self._impl = SystemdNotifier()
        else:
            self._impl = None
            self._sock = None
            self._socket_path = os.getenv("NOTIFY_SOCKET")

            if self._socket_path:
                # Handle abstract namespace sockets (start with '@')
                if self._socket_path.startswith('@'):
                    self._socket_path = '\0' + self._socket_path[1:]

                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    def notify(self, message: str):
        # Prefer real sdnotify
        if self._impl:
            try:
                self._impl.notify(message)
                return
            except Exception:
                pass

        # Fallback to direct UNIX datagram
        if self._sock and self._socket_path:
            try:
                self._sock.sendto(message.encode('utf-8'), self._socket_path)
            except Exception:
                pass


def get_notifier():
    return Notifier()
