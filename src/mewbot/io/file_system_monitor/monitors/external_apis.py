"""
Experiencing a clash between mypy and flake8 - hopefully this will resolve it.

Watchdog seems to be doing something odd with imports.
Hopefully working around that here.
"""

from watchdog.events import FileSystemEvent as WatchdogFileSystemEvent
from watchdog.events import FileSystemEventHandler as WatchdogFileSystemEventHandler
from watchdog.observers.api import BaseObserver as WatchdogBaseObserver

__all__ = [
    "WatchdogBaseObserver",
    "WatchdogFileSystemEvent",
    "WatchdogFileSystemEventHandler",
]
