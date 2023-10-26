# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Stores the base class for all monitor operations.
"""

from typing import AsyncGenerator, Optional, Set, Tuple

import asyncio
import dataclasses
import logging

import aiopath  # type: ignore
import watchfiles


@dataclasses.dataclass
class InputState:
    """
    Stores a path to the object we're watching and some basic information about it.
    """

    input_path: Optional[str] = None
    input_path_exists: bool = False
    _input_path_type: Optional[str] = None

    @property
    def input_path_type(self) -> Optional[str]:
        """
        Allows some access control on the input_path_type.

        :return:
        """
        return self._input_path_type

    @input_path_type.setter
    def input_path_type(self, value: Optional[str]) -> None:
        """
        Preforms validation and sets the input path type.

        :param value:
        :return:
        """
        if value not in (None, "dir", "file"):
            raise AttributeError(f"Cannot set input_path_type to {value} - not valid")
        self._input_path_type = value


class BaseMonitor:
    """
    Contains base methods which are common to most monitor.
    """

    _logger: logging.Logger

    _polling_interval: float

    _input_path_state: InputState = InputState()

    watcher: Optional[AsyncGenerator[Set[Tuple[watchfiles.Change, str]], None]]

    async def monitor_input_path_generic(self, obj_type: str) -> bool:
        """
        Generic function which aims to combine the file and dir monitoring logic.

        DRYing out the code base.
        :param obj_type:
        :return:
        """
        assert obj_type in ["dir", "file"]

        if (
            self._input_path_state.input_path_exists
            and self._input_path_state.input_path_type == obj_type
        ):
            return True
        return False

    async def monitor_input_path_file(self) -> None:
        """
        Preforms a check on the monitored location - updating the properties of the class.

        Several properties are cached.
        """
        if await self.monitor_input_path_generic(obj_type="file"):
            return

        self._logger.info(
            "The provided input path will be monitored until a file appears - %s",
            str(self._input_path_state),
        )

        while True:
            if self._input_path_state.input_path is None:
                await asyncio.sleep(
                    self._polling_interval
                )  # Give the rest of the loop a chance to do something
                continue

            target_async_path: aiopath.AsyncPath = aiopath.AsyncPath(
                self._input_path_state.input_path
            )
            target_exists: bool = await target_async_path.exists()
            is_target_dir: bool = await target_async_path.is_dir()
            if not target_exists:
                await asyncio.sleep(
                    self._polling_interval
                )  # Give the rest of the loop a chance to do something
                continue

            if target_exists and is_target_dir:
                await asyncio.sleep(
                    self._polling_interval
                )  # Give the rest of the loop a chance to do something
                continue

            # Something has come into existence since the last loop
            self._logger.info(
                "Something has appeared at the input_path - %s",
                self._input_path_state.input_path,
            )

            # All the logic which needs to be run when a file is created at the target location
            # Aim is to get the event on the wire as fast as possible, so as to start the watcher
            # To minimize the chance of missing events
            asyncio.get_running_loop().create_task(
                self.input_path_file_created_task(target_async_path)
            )

            self.watcher = watchfiles.awatch(self._input_path_state.input_path)
            self._input_path_state.input_path_exists = True
            return

    async def input_path_file_created_task(
        self, target_async_path: aiopath.AsyncPath
    ) -> None:
        """
        Called when _monitor_file detects that there's now something at the input_path location.

        Spun off into a separate method because want to get into starting the watch as fast as
        possible.
        """

    async def _input_path_dir_created_task(
        self, target_async_path: aiopath.AsyncPath
    ) -> None:
        """
        Called when _monitor_file detects that there's now something at the input_path location.

        Spun off into a separate method because want to get into starting the watch as fast as
        possible.
        """

    async def monitor_input_path_dir(self) -> None:
        """
        Preforms a check on the file - updating if needed.
        """
        if await self.monitor_input_path_generic(obj_type="dir"):
            return

        self._logger.info(
            "The provided input path will be monitored until a dir appears - %s - %s",
            self._input_path_state.input_path,
            self._input_path_state.input_path_type,
        )

        while True:
            if self._input_path_state.input_path is None:
                await asyncio.sleep(
                    self._polling_interval
                )  # Give the rest of the loop a chance to do something
                continue

            target_async_path: aiopath.AsyncPath = aiopath.AsyncPath(
                self._input_path_state.input_path
            )

            target_exists: bool = await target_async_path.exists()
            if not target_exists:
                await asyncio.sleep(
                    self._polling_interval
                )  # Give the rest of the loop a chance to do something
                continue

            is_target_file: bool = await target_async_path.is_file()
            if target_exists and is_target_file:
                await asyncio.sleep(
                    self._polling_interval
                )  # Give the rest of the loop a chance to do something
                continue

            # Something has come into existence since the last loop
            self._logger.info(
                "Something has appeared at the input_path - %s",
                self._input_path_state.input_path,
            )

            asyncio.get_running_loop().create_task(
                self._input_path_dir_created_task(target_async_path)
            )

            self._input_path_state.input_path_exists = True
            return
