#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Contains the various input classes which are actually used to parse events from the file system.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Optional, Set, Tuple, Type, Union

import logging
import os.path
import sys

import aiopath  # type: ignore
import watchfiles
from mewbot.api.v1 import Input, InputEvent

from mewbot.io.file_system_monitor.fs_events import (
    DirCreatedAtWatchLocationFSInputEvent,
    DirCreatedWithinWatchedDirFSInputEvent,
    DirDeletedFromWatchedDirFSInputEvent,
    DirDeletedFromWatchLocationFSInputEvent,
    DirMovedFromWatchLocationFSInputEvent,
    DirMovedOutOfWatchedDirFSInputEvent,
    DirMovedToWatchLocationFSInputEvent,
    DirMovedWithinWatchedDirFSInputEvent,
    DirUpdatedAtWatchLocationFSInputEvent,
    DirUpdatedWithinWatchedDirFSInputEvent,
    FileCreatedAtWatchLocationFSInputEvent,
    FileCreatedWithinWatchedDirFSInputEvent,
    FileDeletedFromWatchLocationFSInputEvent,
    FileDeletedWithinWatchedDirFSInputEvent,
    FileMovedOutsideWatchedDirFSInputEvent,
    FileMovedWithinWatchedDirFSInputEvent,
    FileUpdatedAtWatchLocationFSInputEvent,
    FileUpdatedWithinWatchedDirFSInputEvent,
    FSInputEvent,
)
from mewbot.io.file_system_monitor.monitors.base_monitor import BaseMonitor, InputState
from mewbot.io.file_system_monitor.monitors.dir_monitor import (
    LinuxFileSystemObserver,
    WindowsFileSystemObserver,
)
from mewbot.io.file_system_monitor.monitors.file_monitor import BaseFileMonitorMixin


class FileTypeFSInput(Input, BaseFileMonitorMixin):
    """
    Using watchfiles as a backend to watch for events from a single file.

    Augmented by checks so that the system responds properly if the file does not initially exist.
    Or is deleted during the monitoring process.
    If the watcher is started on a folder, it will wait for the folder to go away before starting.
    If the file is deleted and replaced with a folder, it will wait for the folder to be replaced
    with a file before monitoring.
    """

    _input_path_state: InputState

    _logger: logging.Logger

    _polling_interval: float = 0.5

    watcher: Optional[AsyncGenerator[Set[Tuple[watchfiles.Change, str]], None]]

    def __init__(self, input_path: Optional[str] = None) -> None:
        """
        Start up the monitor - watching a file.

        :param input_path:
        """
        super(Input, self).__init__()  # pylint: disable=bad-super-call

        self._input_path_state = InputState()

        self._input_path_state.input_path = input_path

        self._logger = logging.getLogger(__name__ + ":" + type(self).__name__)

        self._logger.info("Using file monitor mixin %s", BaseFileMonitorMixin)

        if input_path is None or not os.path.exists(input_path):
            self.set_watcher(input_path)
            self._input_path_state.input_path_exists = False
            self._input_path_state.input_path_type = None

        # The only case where the watcher can actually start
        elif self._input_path_state.input_path is not None:  # needed to fool pylint
            self.set_watcher(input_path)
            self._input_path_state.input_path_exists = True

            if os.path.isdir(self._input_path_state.input_path):
                self._input_path_state.input_path_type = "dir"
            else:
                self._input_path_state.input_path_type = "file"

        else:
            raise NotImplementedError

    def set_watcher(self,  input_path: Optional[str] = None) -> None:
        """
        Set up the watcher.

        :return:
        """
        if input_path is None or not os.path.exists(input_path):
            self.watcher = None

        # The only case where the watcher can actually start
        elif self._input_path_state.input_path is not None:  # needed to fool pylint
            self.watcher = watchfiles.awatch(self._input_path_state.input_path)

        else:
            raise NotImplementedError


    @staticmethod
    def produces_inputs() -> Set[Type[InputEvent]]:
        """
        Defines the set of input events this Input class can produce.

        This type of InputClass monitors a single file.
        So a number of the file type inputs make no sense for it.
        """
        return {
            FileCreatedAtWatchLocationFSInputEvent,  # A file is created at the monitored point
            FileUpdatedAtWatchLocationFSInputEvent,  # The monitored file is updated
            FileDeletedFromWatchLocationFSInputEvent,  # The monitored file is deleted
        }

    async def run(self) -> None:
        """
        Run the right type of monitor for the input path.
        """
        # Restart if the input path changes ... might be a good idea
        if (
            self._input_path_state.input_path_exists
            and self._input_path_state.input_path_type == "file"
        ):
            self._logger.info(
                'Starting FileTypeFSInput - monitoring existing file "%s"',
                self._input_path_state.input_path,
            )

        elif (
            self._input_path_state.input_path_exists
            and self._input_path_state.input_path_type == "dir"
        ):
            self._logger.warning(
                "Starting FileTypeFSInput - monitoring file is a dir '%s'",
                self._input_path_state.input_path,
            )

        else:
            self._logger.info(
                'Waiting to start FileSystemInput - provided input path did not exist "%s"',
                self._input_path_state.input_path,
            )

        while True:
            await self.monitor_input_path_file()
            await self.monitor_file_watcher()

    async def send(self, event: FSInputEvent) -> None:
        """
        Put an event generated by one of the monitors on the file.

        :param event:
        :return:
        """
        if self.queue is None:
            return

        await self.queue.put(event)


class DirTypeFSInput(Input, BaseMonitor):
    """
    File system input which watches for changes to directory like objects.
    """

    _logger: logging.Logger

    _input_path_state: InputState

    _polling_interval: float = 0.5

    file_system_observer: Union[WindowsFileSystemObserver, LinuxFileSystemObserver]

    def __init__(self, input_path: Optional[str] = None) -> None:
        """
        Construct the input - which we already know is a dir.

        :param input_path:
        """
        super(Input, self).__init__()  # pylint: disable=bad-super-call

        self._input_path_state = InputState()

        self._input_path_state.input_path = input_path

        self._logger = logging.getLogger(__name__ + ":" + type(self).__name__)

        if input_path is None or not os.path.exists(input_path):
            self._input_path_state.input_path_exists = False
            self._input_path_state.input_path_type = None

        elif not os.path.exists(input_path):
            self._input_path_state.input_path_exists = False
            self._input_path_state.input_path_type = None

        # The only case where the watcher can actually start
        elif self._input_path_state.input_path is not None:  # needed to fool pylint
            self._input_path_state.input_path_exists = True

            if os.path.isdir(self._input_path_state.input_path):
                self._input_path_state.input_path_type = "dir"
            else:
                self._input_path_state.input_path_type = "file"

        else:
            raise NotImplementedError

        # Because of backend issues the observer is OS dependant
        self._platform_str = sys.platform
        # Not using an f-string because we want lazy evaluation if possible
        self._logger.info("We are detected as running on %s", self._platform_str)

    @staticmethod
    def produces_inputs() -> Set[Type[InputEvent]]:
        """
        Defines the set of input events this Input class can produce.

        This is intended to be run on a dir - so will produce events for all the things
        in the dir as well.
        Additionally, the dir being monitored itself can be deleted.
        See the final event type.
        """
        return {
            DirCreatedAtWatchLocationFSInputEvent,
            DirUpdatedAtWatchLocationFSInputEvent,
            DirMovedToWatchLocationFSInputEvent,
            DirMovedFromWatchLocationFSInputEvent,
            DirDeletedFromWatchLocationFSInputEvent,
            FileCreatedWithinWatchedDirFSInputEvent,
            FileUpdatedWithinWatchedDirFSInputEvent,
            FileMovedWithinWatchedDirFSInputEvent,
            FileMovedOutsideWatchedDirFSInputEvent,
            FileDeletedWithinWatchedDirFSInputEvent,
            DirCreatedWithinWatchedDirFSInputEvent,
            DirUpdatedWithinWatchedDirFSInputEvent,
            DirMovedWithinWatchedDirFSInputEvent,
            DirMovedOutOfWatchedDirFSInputEvent,
            DirDeletedFromWatchedDirFSInputEvent,
        }

    @property
    def input_path(self) -> Optional[str]:
        """
        Path where the directory which is being monitored is located.

        :return:
        """
        return self._input_path_state.input_path

    @input_path.setter
    def input_path(self, new_input_path: Optional[str]) -> None:
        """
        Set the path for monitoring.

        :param new_input_path:
        :return:
        """
        self._input_path_state.input_path = new_input_path

    @property
    def input_path_exists(self) -> bool:
        """
        Cached property - does the input path exist.

        :return:
        """
        return self._input_path_state.input_path_exists

    @input_path_exists.setter
    def input_path_exists(self, value: Any) -> None:
        """
        Input path is determined internally using some variant of os.path.
        """
        raise AttributeError("input_path_exists cannot be externally set")

    async def run(self) -> None:
        """
        Monitor the directory.
        """
        # Restart if the input path changes ... might be a good idea
        if (
            self._input_path_state.input_path_exists
            and self._input_path_state.input_path_type == "dir"
        ):
            self._logger.info(
                'Starting DirTypeFSInput - monitoring existing dir "%s"',
                self._input_path_state.input_path,
            )

        else:
            self._logger.info(
                'Waiting to start DirTypeFSInput - provided input path did not exist "%s"',
                self._input_path_state.input_path,
            )

        while True:
            # We're waiting for the thing we're monitoring to exist
            await self.monitor_input_path_dir()

            assert self.input_path is not None

            # There's something at the location - it should be a dir - activate the watcher
            self.file_system_observer: Union[
                WindowsFileSystemObserver, LinuxFileSystemObserver
            ]
            if self._platform_str == "win32":
                self.file_system_observer = WindowsFileSystemObserver(
                    output_queue=self.queue, input_path=self.input_path
                )

                self._input_path_state.input_path_exists = (
                    await self.file_system_observer.monitor_dir_watcher()
                )
            else:
                self.file_system_observer = LinuxFileSystemObserver(
                    output_queue=self.queue, input_path=self.input_path
                )

                self._input_path_state.input_path_exists = (
                    await self.file_system_observer.monitor_dir_watcher()
                )

    async def _input_path_dir_created_task(
        self, target_async_path: aiopath.AsyncPath
    ) -> None:
        """
        Called when _monitor_file detects that there's now something at the input_path location.

        Spun off into a separate method because want to get into starting the watch as fast as
        possible.
        """
        if self._input_path_state.input_path is None:
            self._logger.warning(
                "Unexpected call to _input_path_file_created_task - _input_path is None!"
            )
            return
        if (
            self._input_path_state.input_path is not None
            and self._input_path_state.input_path_type == "file"
        ):
            self._logger.warning(
                "Unexpected call to _input_path_file_created_task - "
                "_input_path is not None but _input_path_type is file"
            )

        str_path: str = self._input_path_state.input_path

        if await target_async_path.is_file():  # Not sure this case should ever be reached
            self._logger.info(
                'New asset at "%s" detected as file', self._input_path_state.input_path
            )

        elif await target_async_path.is_dir():
            self._logger.info(
                'New asset at "%s" detected as dir', self._input_path_state.input_path
            )

            await self.send(
                DirCreatedAtWatchLocationFSInputEvent(path=str_path, base_event=None)
            )

        else:
            self._logger.warning(
                "Unexpected case in _input_path_created_task - %s", target_async_path
            )

    async def send(self, event: FSInputEvent) -> None:
        """
        Put events on the wire.

        :param event:
        :return:
        """
        if self.queue is None:
            return

        await self.queue.put(event)
