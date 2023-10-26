# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Monitoring a directory for changes and monitoring a file for changes are very different processes.

As such, different classes are used for each of them.
"""

from __future__ import annotations

from typing import Any, Optional, Set, Union

import asyncio
import logging
import os
import pathlib

import aiopath  # type: ignore
import watchdog
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

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

    _watchdog_observer: Observer = Observer()

    _internal_queue: asyncio.Queue[FileSystemEvent]

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

    async def _process_event_from_watched_dir(self, event: FileSystemEvent) -> None:
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
        handler = _EventHandler(queue=self._internal_queue, loop=asyncio.get_event_loop())

        self._watchdog_observer = Observer()
        self._watchdog_observer.schedule(
            event_handler=handler, path=self._input_path, recursive=True
        )
        self._watchdog_observer.start()

        self._logger.info("Started _watchdog_observer")

        self._watchdog_observer.join(10)

        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                self._internal_queue.put_nowait, None
            )
        except RuntimeError:  # Can happen when the shutdown is not clean
            return

    async def _process_file_event_from_within_dir(self, event: FileSystemEvent) -> None:
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

    async def _process_dir_event_from_within_dir(self, event: FileSystemEvent) -> None:
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


class WindowsFileSystemObserver(LinuxFileSystemObserver):
    """
    Does the job of actually observing the file system.

    Isolated here because the observer subsystem for windows is particularly problematic, and it
    should be swapped out wholesale where possible.
    """

    # workaround for a problem with file monitors on Windows
    # when a file is deleted you receive several modification events before the delete event.
    # These are meaningless - the file is, in truth, already gone
    # This cache contains file paths which the user has been told have been deleted.
    # And python believes to be gone
    # Removed from the cache when an actual delete event comes in, or a creation/move to event
    _python_registers_deleted_cache: Set[str] = set()
    _python_registers_created_cache: Set[str] = set()

    _dir_cache: Set[str]

    def __init__(
        self, output_queue: Optional[asyncio.Queue[InputEvent]], input_path: str
    ) -> None:
        """
        Prepare to monitor a directory.

        :param output_queue:
        :param input_path:
        """
        super().__init__(output_queue, input_path)

        self._dir_cache = set()
        self.build_dir_cache()

    def build_dir_cache(self) -> None:
        """
        On Windows DIR deletion events are being reported as FILE del events.

        There is no good way to check the status of an object after it's gone,
        thus need to cache all the dirs first.
        """
        if self._input_path is None:
            return

        self._logger.info("Building dir cache for %s", self._input_path)
        for root, dirs, _ in os.walk(top=self._input_path):
            self._dir_cache.update(set(os.path.join(root, dn) for dn in dirs))
        self._logger.info(
            "dir cache built for %s - %i dirs found", self._input_path, len(self._dir_cache)
        )

    async def _process_file_creation_event(
        self, event: watchdog.events.FileCreatedEvent
    ) -> None:
        """
        A file creation event has been registered by watchdog.

        This might, or might not, be a zombie event.
        Windows seems to produce several such events when a file is created.
        :param event:
        :return None:
        """
        file_async_path = aiopath.AsyncPath(event.src_path)

        if not await file_async_path.exists():
            # zombie event - appeal to reality says the file does not exist
            return

        if event.src_path in self._python_registers_created_cache:
            # User has already been notified - no reason to tell them again
            return

        # After one of these there very much should be something at the target loc
        self._python_registers_deleted_cache.discard(event.src_path)
        self._python_registers_created_cache.add(event.src_path)

        await super()._process_file_creation_event(event)

    async def _process_file_modified_event(
        self, event: watchdog.events.FileModifiedEvent
    ) -> None:
        """
        A file modification event has been produced by watchdog.

        This event could, in fact, be rendered into several events.
        Because file modification events can occur _before_ a file creation event.
        (This usually seems to happen when the file has been recently deleted and recreated.
        However it cannot be guaranteed it doesn't happen under different circumstances).
        :param event:
        :return:
        """
        file_async_path = aiopath.AsyncPath(event.src_path)

        if await file_async_path.exists():
            # This might be a legit event

            if event.src_path in self._python_registers_deleted_cache:
                # We're getting modification events - and the file exists
                # where once it was registered as deleted
                # So tell the user the file exists again
                self._python_registers_deleted_cache.discard(event.src_path)
                self._python_registers_created_cache.add(event.src_path)

                await self.send(
                    FileCreatedWithinWatchedDirFSInputEvent(
                        path=event.src_path,
                        base_event=event,
                    )
                )

                return

            # Inotify on linux also notifies you of a change to the folder in this case

            dir_path = os.path.split(event.src_path)[0]

            await self.send(
                DirUpdatedAtWatchLocationFSInputEvent(
                    path=dir_path,
                    base_event=None,
                )
            )

            await super()._process_file_modified_event(event)

        else:
            if event.src_path in self._python_registers_deleted_cache:
                # User has already been informed - no need to do anything
                # Any modification events we get here are stale
                return

            # User might think the file still exists - tell them it does not

            # Note that the user has been informed the file is gone
            self._python_registers_deleted_cache.add(event.src_path)
            # The user can be informed again that the file exists
            self._python_registers_created_cache.remove(event.src_path)

            dir_path = os.path.split(event.src_path)[0]

            await self.send(
                DirUpdatedWithinWatchedDirFSInputEvent(
                    path=dir_path,
                    base_event=None,
                )
            )

            await self.send(
                FileDeletedWithinWatchedDirFSInputEvent(
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
        A file move has been detected by watchdog - process it.

        :param event:
        :return:
        """
        if isinstance(event, watchdog.events.FileSystemMovedEvent):
            self._logger.info("System moved a file %s", str(event))

        # Unfortunately, we're getting these events when a file is moved as well
        if event.src_path in self._dir_cache:
            self._dir_cache.discard(event.src_path)
            self._dir_cache.add(event.dest_path)
            await self.send(
                DirMovedWithinWatchedDirFSInputEvent(
                    path=os.path.split(event.src_path)[0],
                    dir_src_path=event.src_path,
                    dir_dst_path=event.dest_path,
                    base_event=event,
                )
            )
            return

        # Hopefully, from this point on, any modified and deleted events are legit.
        # The user has been effectively told that the src_path no longer exists
        self._python_registers_deleted_cache.add(event.src_path)
        self._python_registers_deleted_cache.discard(event.dest_path)

        # A file hs been moved into position
        # so the user does not need to be informed that one has been created
        # The user has been (effectively) informed that an object has been created here
        self._python_registers_created_cache.add(event.dest_path)
        self._python_registers_created_cache.discard(event.src_path)

        await super()._process_file_move_event(event)

    async def _process_file_delete_event(
        self, event: watchdog.events.FileDeletedEvent
    ) -> None:
        """
        A file deletion event has been detected.

        Windows can produce multiple deletion events off a single file deletion.
        Some filtering is needed to produce useful results.
        :param event:
        :return:
        """
        file_async_path = aiopath.AsyncPath(event.src_path)

        # Only put a deletion event on the wire if
        # - we haven't done so already
        # - There has been no other events which could be sanely followed by a
        #   delete event (such as a create event)
        # - The file does not, in fact, still exist

        if event.src_path in self._python_registers_deleted_cache:
            self._python_registers_deleted_cache.discard(event.src_path)
            return

        if await file_async_path.exists():
            return

        # For some reason the watcher is emitting file delete events when a dir is deleted
        if event.src_path in self._dir_cache:
            self.event_process_preflight()

            # Inotify on linux also notifies you of a change to the folder in this case
            assert self._input_path is not None, "mypy hack"
            await self.send(
                DirUpdatedWithinWatchedDirFSInputEvent(
                    path=self._input_path,
                    base_event=None,
                )
            )

            await self.send(
                DirDeletedFromWatchedDirFSInputEvent(
                    path=event.src_path,
                    base_event=event,
                )
            )
            return

        dir_path = os.path.split(event.src_path)[0]

        # Inotify on linux also notifies you of a change to the folder in this case
        await self.send(
            DirUpdatedWithinWatchedDirFSInputEvent(
                path=dir_path,
                base_event=None,
            )
        )

        return await super()._process_file_delete_event(event)

    async def _process_dir_event_from_within_dir(self, event: FileSystemEvent) -> None:
        """
        Take an event and process it before putting it on the wire.
        """
        self.event_process_preflight()

        # DIRS
        if isinstance(event, watchdog.events.DirCreatedEvent):
            # A new directory has been created - record it
            self._dir_cache.add(event.src_path)
            return await self._process_dir_in_watched_dir_creation_event(event)

        if isinstance(event, watchdog.events.DirModifiedEvent):
            return await self._process_dir_update_event(event)

        if isinstance(event, watchdog.events.DirMovedEvent):
            # If a dir experiences a move event, the original dir effectively ceases to exist
            # And a new one appears - update the _dir_cache accordingly
            self._dir_cache.discard(event.src_path)
            self._dir_cache.add(event.dest_path)

            return await self._process_dir_move_event(event)

        if isinstance(event, watchdog.events.DirDeletedEvent):
            # Not that I think you'll ever actually see one of these events
            # Because Windows registers a dir delete event as a file delete for some reason
            self._dir_cache.discard(event.src_path)

            return await self._process_dir_delete_event(event)

        raise NotImplementedError(f"{event} had unexpected form.")


class _EventHandler(FileSystemEventHandler):  # type: ignore
    """
    Produces events when file system changes are detected.
    """

    _loop: asyncio.AbstractEventLoop
    _queue: asyncio.Queue[FileSystemEvent]

    def __init__(
        self,
        queue: asyncio.Queue[FileSystemEvent],
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

    def on_any_event(self, event: FileSystemEvent) -> None:
        """
        All events are of interest - filtering can happen at the Behavior level.

        :param event:
        :return:
        """
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            return
