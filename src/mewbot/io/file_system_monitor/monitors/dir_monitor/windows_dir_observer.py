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
import os

import aiopath  # type: ignore
import watchdog
from mewbot.core import InputEvent

from mewbot.io.file_system_monitor.fs_events import (
    DirDeletedFromWatchedDirFSInputEvent,
    DirMovedWithinWatchedDirFSInputEvent,
    DirUpdatedAtWatchLocationFSInputEvent,
    DirUpdatedWithinWatchedDirFSInputEvent,
    FileCreatedWithinWatchedDirFSInputEvent,
    FileDeletedWithinWatchedDirFSInputEvent,
)
from mewbot.io.file_system_monitor.monitors.dir_monitor.linux_dir_observer import (
    WatchdogLinuxFileSystemObserver,
)
from mewbot.io.file_system_monitor.monitors.external_apis import WatchdogFileSystemEvent


class WindowsFileSystemObserver(WatchdogLinuxFileSystemObserver):
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

    async def _process_dir_event_from_within_dir(
        self, event: WatchdogFileSystemEvent
    ) -> None:
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
