# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Monitoring a directory for changes and monitoring a file for changes are very different processes.

As such, different classes are used for each of them.
"""

from __future__ import annotations

from typing import Optional, Set, Union

import asyncio
import logging
import os
import pathlib

import aiopath  # type: ignore
import watchdog
from mewbot.core import InputEvent

from mewbot.io.file_system_monitor.fs_events import (
    DirCreatedWithinWatchedDirFSInputEvent,
    DirDeletedFromWatchedDirFSInputEvent,
    DirDeletedFromWatchLocationFSInputEvent,
    DirMovedOutOfWatchedDirFSInputEvent,
    DirMovedWithinWatchedDirFSInputEvent,
    DirUpdatedAtWatchLocationFSInputEvent,
    DirUpdatedWithinWatchedDirFSInputEvent,
    FileCreatedWithinWatchedDirFSInputEvent,
    FileDeletedWithinWatchedDirFSInputEvent,
    FileMovedOutsideWatchedDirFSInputEvent,
    FileMovedWithinWatchedDirFSInputEvent,
    FileUpdatedWithinWatchedDirFSInputEvent,
    FSInputEvent,
)
from mewbot.io.file_system_monitor.monitors.dir_monitor.event_handler import (
    MewbotEventHandler,
)
from mewbot.io.file_system_monitor.monitors.external_apis import (
    WatchdogBaseObserver,
    WatchdogFileSystemEvent,
)


class LinuxFileSystemObserver:
    """
    Base class for all observers defined on the system.

    Basic program flow goes as follows
     - Observer is provided with a location in a local file system
     - Observer checks to see if there's something at that location
     - if there is
       - and it's a dir - start a dir observer
       - and it's a file - start a file observer
     - if there isn't, wait for there to be and start the appropriate observer
    """

    _output_queue: Optional[asyncio.Queue[InputEvent]]
    _input_path: Optional[str] = None

    _logger: logging.Logger

    _watchdog_observer: WatchdogBaseObserver = watchdog.observers.Observer()

    _internal_queue: asyncio.Queue[WatchdogFileSystemEvent]

    def __init__(
        self, output_queue: Optional[asyncio.Queue[InputEvent]], input_path: str
    ) -> None:
        """
        Holds the queues which will store the events prodced by the watcher.

        :param output_queue:
        :param input_path:
        """
        self._output_queue = output_queue
        self._input_path = input_path

        self._logger = logging.getLogger(__name__ + ":" + type(self).__name__)

        self._internal_queue = asyncio.Queue()

    def event_process_preflight(self) -> None:
        """
        Checks we are in a state where we can process events.

        :return None: Will error if we can't proceed
        """
        # mypy hack
        assert self._input_path is not None, "_input_path unexpectedly None"

    async def _process_queue(self) -> bool:
        """
        Take event off the internal queue, process them, and then put them on the wire.
        """
        target_async_path: aiopath.AsyncPath = aiopath.AsyncPath(self._input_path)

        while True:
            new_event = await self._internal_queue.get()

            # The events produced when the dir is deleted are not helpful
            # Currently not sure that watchdog elegantly indicates that it's had its target dir
            # deleted
            # So need this horrible hack. Will get the rest of it working, then optimize

            # No helpful info is provided by the watcher if the target dir itself is deleted
            # So need to check before each event

            target_exists: bool = await target_async_path.exists()

            if not target_exists:
                self._logger.info("Delete event detected - %s is gone", self._input_path)
                return True

            await self._process_event_from_watched_dir(new_event)

    async def monitor_dir_watcher(self) -> bool:
        """
        Monitor a watcher which has been assigned to watch a location which contains a dir.

        :return:
        """

        if self._input_path is not None:
            self.start_watchdog_on_dir()
        else:
            self._logger.warning("self._input_path is None in run - this should not happen")
            raise NotImplementedError(
                "self._input_path is None in run - this should not happen"
            )

        dir_deleted = await self._process_queue()
        if dir_deleted:
            self._logger.info(
                "%s has been deleted - returning to wait mode", self._input_path
            )
            await self.send(
                DirDeletedFromWatchLocationFSInputEvent(
                    path=self._input_path,
                    base_event=None,
                )
            )
            return False
        return True

    async def send(self, event: FSInputEvent) -> None:
        """
        Responsible for putting events on the wire.

        :param event: A FSInputEvent to send.
        :return:
        """
        if self._output_queue is None:
            return

        await self._output_queue.put(event)

    async def _process_event_from_watched_dir(self, event: WatchdogFileSystemEvent) -> None:
        """
        Take an event and process it before putting it on the wire.
        """
        # Filter null events
        if event is None:
            return

        if isinstance(
            event,
            (
                watchdog.events.FileCreatedEvent,
                watchdog.events.FileModifiedEvent,
                watchdog.events.FileMovedEvent,
                watchdog.events.FileSystemMovedEvent,
                watchdog.events.FileDeletedEvent,
            ),
        ):
            await self._process_file_event_from_within_dir(event)

        elif isinstance(
            event,
            (
                watchdog.events.DirCreatedEvent,
                watchdog.events.DirModifiedEvent,
                watchdog.events.DirMovedEvent,
                watchdog.events.DirDeletedEvent,
            ),
        ):
            await self._process_dir_event_from_within_dir(event)
        else:
            self._logger.info("Unhandled event in _process_event - %s", event)

    def start_watchdog_on_dir(self) -> None:
        """
        Use watchdog in a separate thread to watch a dir for changes.
        """
        handler = MewbotEventHandler(
            queue=self._internal_queue, loop=asyncio.get_event_loop()
        )

        self._watchdog_observer = watchdog.observers.Observer()
        self._watchdog_observer.schedule(  # type: ignore
            event_handler=handler, path=self._input_path, recursive=True
        )
        self._watchdog_observer.start()  # type: ignore

        self._logger.info("Started _watchdog_observer")

        self._watchdog_observer.join(10)

        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                self._internal_queue.put_nowait, None
            )
        except RuntimeError:  # Can happen when the shutdown is not clean
            return

    async def _process_file_event_from_within_dir(
        self, event: WatchdogFileSystemEvent
    ) -> None:
        """
        Take a file event and process it before putting it on the wire.
        """

        if isinstance(event, watchdog.events.FileCreatedEvent):
            await self._process_file_creation_event(event)

        elif isinstance(event, watchdog.events.FileModifiedEvent):
            await self._process_file_modified_event(event)

        elif isinstance(
            event, (watchdog.events.FileMovedEvent, watchdog.events.FileSystemMovedEvent)
        ):
            await self._process_file_move_event(event)

        elif isinstance(event, watchdog.events.FileDeletedEvent):
            await self._process_file_delete_event(event)

        else:
            self._logger.warning("Unexpected case in _process_file_event - %s", event)

    async def _process_file_creation_event(
        self, event: watchdog.events.FileCreatedEvent
    ) -> None:
        """
        A file has been created within a watched dir.

        :param event:
        :return:
        """
        await self.send(
            FileCreatedWithinWatchedDirFSInputEvent(
                path=event.src_path,
                base_event=event,
            )
        )

    async def _process_file_modified_event(
        self, event: watchdog.events.FileModifiedEvent
    ) -> None:
        """
        A file has been modified.

        :param event:
        :return:
        """
        await self.send(
            FileUpdatedWithinWatchedDirFSInputEvent(
                path=event.src_path,
                base_event=event,
            )
        )

    async def _process_file_move_event(
        self,
        event: Union[
            watchdog.events.FileSystemMovedEvent, watchdog.events.FileSystemMovedEvent
        ],
    ) -> None:
        """
        A file movement has been detected in the monitored folder.

        :param event:
        :return:
        """
        if self._input_path is None:
            raise NotImplementedError("self._input_path unexpectedly None.")

        monitored_dir_path = pathlib.Path(self._input_path)
        dir_dst_path = pathlib.Path(event.dest_path)
        if dir_dst_path.absolute().is_relative_to(monitored_dir_path):
            await self.send(
                FileMovedWithinWatchedDirFSInputEvent(
                    path=event.dest_path,
                    file_src=event.src_path,
                    file_dst=event.dest_path,
                    base_event=event,
                )
            )
        else:
            await self.send(
                FileMovedOutsideWatchedDirFSInputEvent(
                    path=event.dest_path,
                    file_src=event.src_path,
                    base_event=event,
                )
            )

    async def _process_file_delete_event(
        self, event: watchdog.events.FileDeletedEvent
    ) -> None:
        """
        A file has been deleted from inside the monitored dirs.

        :param event:
        :return:
        """
        await self.send(
            FileDeletedWithinWatchedDirFSInputEvent(
                path=event.src_path,
                base_event=event,
            )
        )

    async def _process_dir_in_watched_dir_creation_event(
        self, event: watchdog.events.DirCreatedEvent
    ) -> None:
        """
        Process a dir creation event.

        This will - always - correspond to an event inside a directory we are watching.
        If the event involves the directory itself, that will break the watcher in a way which is
        caught later.
        :param event:
        :return:
        """
        await self.send(
            DirCreatedWithinWatchedDirFSInputEvent(
                path=event.src_path,
                base_event=event,
            )
        )

    async def _process_dir_update_event(
        self, event: watchdog.events.DirModifiedEvent
    ) -> None:
        """
        Process a dir modified event.

        Produces a DirUpdatedAtWatchLocationFSInputEvent - if the dir being watched itself is
        changed.
        Otherwise, produces a DirUpdatedWithinWatchedDirFSInputEvent - if the dir being modified
        is inside the watched dir.
        :param event:
        :return:
        """
        assert self._input_path is not None, "mypy hack"
        if pathlib.Path(event.src_path).samefile(pathlib.Path(self._input_path).resolve()):
            await self.send(
                DirUpdatedAtWatchLocationFSInputEvent(
                    path=event.src_path,
                    base_event=event,
                )
            )
        else:
            await self.send(
                DirUpdatedWithinWatchedDirFSInputEvent(
                    path=event.src_path,
                    base_event=event,
                )
            )

    async def _process_dir_move_event(self, event: watchdog.events.DirMovedEvent) -> None:
        """
        Aa directory has been moved - process the resulting event.

        :param event:
        :return:
        """
        assert self._input_path is not None, "mypy hack"

        # Check to see of the directory has been moved within or out of the dir
        monitored_dir_path = pathlib.Path(self._input_path)
        dir_dst_path = pathlib.Path(event.dest_path)
        if dir_dst_path.resolve().is_relative_to(monitored_dir_path):
            await self.send(
                DirMovedWithinWatchedDirFSInputEvent(
                    path=event.src_path,
                    dir_src_path=event.src_path,
                    dir_dst_path=event.dest_path,
                    base_event=event,
                )
            )

        else:
            await self.send(
                DirMovedOutOfWatchedDirFSInputEvent(
                    path=event.src_path,
                    dir_src_path=event.src_path,
                    dir_dst_path=event.dest_path,
                    base_event=event,
                )
            )

    async def _process_dir_delete_event(self, event: watchdog.events.DirDeletedEvent) -> None:
        """
        Aa dir delete event has occurred.

        :param event:
        :return:
        """
        await self.send(
            DirDeletedFromWatchedDirFSInputEvent(
                path=event.src_path,
                base_event=event,
            )
        )

    async def _process_dir_event_from_within_dir(
        self, event: WatchdogFileSystemEvent
    ) -> None:
        """
        Take an event and process it before putting it on the wire.

        Event has been generated from within a directory being watched with watchdog.
        """

        # DIRS
        if isinstance(event, watchdog.events.DirCreatedEvent):
            return await self._process_dir_in_watched_dir_creation_event(event)

        if isinstance(event, watchdog.events.DirModifiedEvent):
            # If the path is the same as the monitored path, then the folder we're watching itself
            # has been modified
            return await self._process_dir_update_event(event)

        if isinstance(event, watchdog.events.DirMovedEvent):
            return await self._process_dir_move_event(event)

        if isinstance(event, watchdog.events.DirDeletedEvent):
            return await self._process_dir_delete_event(event)

        raise NotImplementedError(f"{event} had unexpected form.")
