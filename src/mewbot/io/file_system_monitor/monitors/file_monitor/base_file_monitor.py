"""
All file monitors - linux, windows, e.t.c - should inherit from this.
"""

from typing import Any, Optional

import abc
import logging

import aiopath
from mewbot.core import InputQueue

from mewbot.io.file_system_monitor.fs_events import (
    FileCreatedAtWatchLocationFSInputEvent,
    FSInputEvent,
)
from mewbot.io.file_system_monitor.monitors.base_monitor import BaseMonitor, InputState


class BaseFileMonitor(BaseMonitor):
    _logger: logging.Logger

    _input_path_state: InputState = InputState()

    _polling_interval: float = 0.5

    queue: InputQueue | None

    @property
    def input_path(self) -> Optional[str]:
        """
        The path being watched by the file type monitor.

        :return:
        """
        return self._input_path_state.input_path

    @input_path.setter
    def input_path(self, new_input_path: Optional[str]) -> None:
        """
        Set the path to be watched.

        :param new_input_path:
        :return:
        """
        self._input_path_state.input_path = new_input_path

    @property
    def input_path_exists(self) -> bool:
        """
        Checks to see if the input path is registered as exists.

        :return:
        """
        return self._input_path_state.input_path_exists

    @input_path_exists.setter
    def input_path_exists(self, value: Any) -> None:
        """
        Input path is determined internally using some variant of os.path.
        """
        raise AttributeError("input_path_exists cannot be externally set")

    async def send(self, event: FSInputEvent) -> None:
        """
        Put an event generated by one of the monitors on the file.

        :param event:
        :return:
        """
        if self.queue is None:
            return

        await self.queue.put(event)

    async def input_path_file_created_task(
        self, target_async_path: aiopath.AsyncPath
    ) -> None:
        """
        Called when _monitor_file detects that there's now something at the input_path location.

        Spun off into a separate method because want to get into starting the watch as fast as
        possible.
        """
        if self._input_path_state.input_path is None:
            self._logger.error(
                "Unexpected call to _input_path_file_created_task - _input_path is None!"
            )
            return

        if (
            self._input_path_state.input_path is not None
            and self._input_path_state.input_path_type == "dir"
        ):
            self._logger.warning(
                "Unexpected call to _input_path_file_created_task - "
                "_input_path is not None but _input_path_type is dir"
            )

        str_path: str = self._input_path_state.input_path

        if await target_async_path.is_dir():
            self._logger.info(
                'New asset at "%s" detected as dir', self._input_path_state.input_path
            )

        elif await target_async_path.is_file():
            self._logger.info(
                'New asset at "%s" detected as file', self._input_path_state.input_path
            )

            await self.send(
                FileCreatedAtWatchLocationFSInputEvent(path=str_path, base_event=None)
            )

        else:
            self._logger.warning(
                "Unexpected case in _input_path_created_task - %s", target_async_path
            )

    @abc.abstractmethod
    async def monitor_file_watcher(self) -> None:
        """
        Actually do the job of monitoring and responding to the watcher.

        If the file is detected as deleted, then the
        """

    @abc.abstractmethod
    async def process_changes(self, changes: set[tuple[Any, str]]) -> bool:
        """
        Turn the product of a watcher into events to put on the wire.

        :param changes:
        :return:
        """

    @abc.abstractmethod
    async def do_update_event(self, change_path: str, raw_change: tuple[Any, str]) -> None:
        """
        Called when the monitored file is updated.
        """

    @abc.abstractmethod
    async def do_delete_event(self, change_path: str, raw_change: tuple[Any, str]) -> None:
        """
        Called when the monitored file is deleted.
        """