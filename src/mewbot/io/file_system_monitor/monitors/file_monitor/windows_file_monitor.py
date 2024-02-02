# !/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Stores the file monitor components for the file system monitor.
"""

from __future__ import annotations

from typing import AsyncGenerator, Optional, Set, Tuple

import asyncio

import watchfiles

from mewbot.io.file_system_monitor.fs_events import (
    FileDeletedFromWatchLocationFSInputEvent,
    FileUpdatedAtWatchLocationFSInputEvent,
)
from mewbot.io.file_system_monitor.monitors.file_monitor.base_file_monitor import (
    BaseFileMonitor,
)


class WindowsFileMonitorMixin(BaseFileMonitor):
    """
    Provides tools to watch a file for changes to it.
    """

    watcher: Optional[AsyncGenerator[Set[Tuple[watchfiles.Change, str]], None]]

    async def monitor_file_watcher(self) -> None:
        """
        Actually do the job of monitoring and responding to the watcher.

        If the file is detected as deleted, then the shutdown the watcher.
        """
        # Ideally this would be done with some kind of run-don't run lock
        # Waiting on better testing before attempting that.
        if self.watcher is None:
            self._logger.info("Unexpected case - self.watcher is None in _monitor_watcher")
            await asyncio.sleep(
                self._polling_interval
            )  # Give the rest of the loop a chance to act
            return

        async for changes in self.watcher:
            file_deleted = await self.process_changes(changes)

            if file_deleted:
                # File is detected as deleted
                # - shutdown the watcher
                # - indicate we need to start monitoring for a new file
                # (or folder - in which case this will do nothing more)
                # - (Putting an event to indicate this on the wire should have happened elsewhere)
                self.watcher = None
                self._input_path_state.input_path_exists = False

                return

    async def process_changes(self, changes: set[tuple[watchfiles.Change, str]]) -> bool:
        """
        Turn the product of a watchfile watcher into events to put on the wire.

        :param changes:
        :return:
        """
        # Changes are sets of chance objects
        # tuples with
        #  - the first entry being a watchfiles.Change object
        #  - the second element being a str path to the changed item

        for change in changes:
            change_type, change_path = change

            if change_type == watchfiles.Change.added:
                self._logger.warning(
                    "With how we are using watchfiles this point should never be reached "
                    "- %s - '%s'",
                    change_type,
                    change_path,
                )

            elif change_type == watchfiles.Change.modified:
                await self.do_update_event(change_path, change)

            elif change_type == watchfiles.Change.deleted:
                await self.do_delete_event(change_path, change)
                return True

            else:
                self._logger.warning(
                    "Unexpected case when trying to parse file change - %s", change_type
                )

        return False

    async def do_update_event(
        self, change_path: str, raw_change: tuple[watchfiles.Change, str]
    ) -> None:
        """
        Called when the monitored file is updated.
        """
        await self.send(
            FileUpdatedAtWatchLocationFSInputEvent(
                path=change_path,
                base_event=raw_change,
            )
        )

    async def do_delete_event(
        self, change_path: str, raw_change: tuple[watchfiles.Change, str]
    ) -> None:
        """
        Called when the monitored file is deleted.
        """
        await self.send(
            FileDeletedFromWatchLocationFSInputEvent(
                path=change_path,
                base_event=raw_change,
            )
        )
