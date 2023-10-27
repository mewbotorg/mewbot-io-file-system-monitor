#!/usr/bin/env python3

"""
Public api for the file monitor IOConfig - which generates events from a file system.
"""

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Optional, Sequence, Union

from mewbot.api.v1 import Input, IOConfig, Output

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
from mewbot.io.file_system_monitor.inputs import DirTypeFSInput, FileTypeFSInput

__version__ = "0.0.1"


__all__ = (
    "FSInputEvent",
    "FileCreatedAtWatchLocationFSInputEvent",
    "FileUpdatedAtWatchLocationFSInputEvent",
    "FileDeletedFromWatchLocationFSInputEvent",
    "DirCreatedAtWatchLocationFSInputEvent",
    "DirUpdatedAtWatchLocationFSInputEvent",
    "DirMovedToWatchLocationFSInputEvent",
    "DirMovedFromWatchLocationFSInputEvent",
    "DirDeletedFromWatchLocationFSInputEvent",
    "FileCreatedWithinWatchedDirFSInputEvent",
    "FileUpdatedWithinWatchedDirFSInputEvent",
    "FileMovedWithinWatchedDirFSInputEvent",
    "FileMovedOutsideWatchedDirFSInputEvent",
    "FileDeletedWithinWatchedDirFSInputEvent",
    "DirCreatedWithinWatchedDirFSInputEvent",
    "DirUpdatedWithinWatchedDirFSInputEvent",
    "DirMovedWithinWatchedDirFSInputEvent",
    "DirMovedOutOfWatchedDirFSInputEvent",
    "DirDeletedFromWatchedDirFSInputEvent",
    "FileSystemMonitorIO",
    "DirTypeFSInput",
    "FileTypeFSInput",
)


class FileSystemMonitorIO(IOConfig):
    """
    Exists to produce events when file system changes are detected.
    """

    _input: Optional[Union[FileTypeFSInput, DirTypeFSInput]] = None

    _input_path: Optional[str] = None
    _input_path_type: str = "not_set"
    _output_path: Optional[str] = None

    @property
    def input_path(self) -> Optional[str]:
        """
        The path to watch.

        :return:
        """
        return self._input_path

    @input_path.setter
    def input_path(self, input_path: str) -> None:
        """
        Set the watched path.

        :param input_path:
        :return:
        """
        self._input_path = input_path

    @property
    def input_path_type(self) -> str:
        """
        When starting this class you need to set the type of resource you are monitoring.

        This is due to limitations of the underlying libraries used to do the actual monitoring.
        A different solution must be used if you're watching a dictionary compared to a file.
        """
        return self._input_path_type

    @input_path_type.setter
    def input_path_type(self, input_path_type: str) -> None:
        """
        Declare the type of the input resource to monitor.

        :param input_path_type:
        :return:
        """
        assert input_path_type in (
            "dir",
            "file",
        ), f"input_path_type couldn't be set as {input_path_type}"
        self._input_path_type = input_path_type

    def get_inputs(self) -> Sequence[Input]:
        """
        Return all the input methods for this IOConfig.

        :return:
        """
        assert self._input_path_type in (
            "dir",
            "file",
        ), (
            f"input_path_type must be properly set before startup - "
            f"{self._input_path_type} is not proper"
        )

        if not self._input:
            if self._input_path_type == "file":
                self._input = FileTypeFSInput(self._input_path)
            elif self._input_path_type == "dir":
                self._input = DirTypeFSInput(self._input_path)
            else:
                raise NotImplementedError(
                    f"{self._input_path_type} not good. Options are 'dir' and 'file'"
                )

        return [self._input]

    def get_outputs(self) -> Sequence[Output]:
        """
        No outputs are currently supported for this IOConfig.

        :return:
        """
        return []
