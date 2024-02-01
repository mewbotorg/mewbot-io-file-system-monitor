# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Monitoring a directory for changes and monitoring a file for changes are very different processes.

As such, different classes are used for each of them.
"""

from __future__ import annotations

from typing import Any

import asyncio


from mewbot.io.file_system_monitor.monitors.external_apis import (
    WatchdogFileSystemEvent,
    WatchdogFileSystemEventHandler,
)


class MewbotEventHandler(WatchdogFileSystemEventHandler):
    """
    Produces events when file system changes are detected.
    """

    _loop: asyncio.AbstractEventLoop
    _queue: asyncio.Queue[WatchdogFileSystemEvent]

    def __init__(
        self,
        queue: asyncio.Queue[WatchdogFileSystemEvent],
        loop: asyncio.AbstractEventLoop,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Startup the file watcher handle - needs a queue to put things on.

        :param queue:
        :param loop:
        :param args:
        :param kwargs:
        """
        self._loop = loop
        self._queue = queue
        super().__init__(*args, **kwargs)

    def on_any_event(self, event: WatchdogFileSystemEvent) -> None:
        """
        All events are of interest - filtering can happen at the Behavior level.

        :param event:
        :return:
        """
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            return
