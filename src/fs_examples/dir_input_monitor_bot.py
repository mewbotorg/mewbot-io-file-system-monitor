#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

# pylint: disable=duplicate-code
# this is an example - duplication for emphasis is desirable

"""
Tools to support example which demonstrate watcing a directory in particular.
"""

from __future__ import annotations

from typing import Any, Coroutine, Dict, Set, Type

import logging

from mewbot.api.v1 import Action, Trigger
from mewbot.core import InputEvent, OutputEvent, OutputQueue

from mewbot.io.file_system_monitor import (
    DirCreatedAtWatchLocationFSInputEvent,
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
)


class DirSystemAllCommandTrigger(Trigger):
    """
    Nothing fancy - just fires whenever there is a dir related FSInputEvent.
    """

    @staticmethod
    def consumes_inputs() -> Set[Type[InputEvent]]:
        """
        Triggers on any change within the monitored directory.

        :return:
        """
        return {
            DirCreatedAtWatchLocationFSInputEvent,
            DirUpdatedAtWatchLocationFSInputEvent,
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

    def matches(self, event: InputEvent) -> bool:
        """
        Matches to any output corresponding to a change in the directory.

        :param event:
        :return:
        """
        print("-------\n", "event seen by matches - ", event, "\n-------")

        if not isinstance(
            event,
            (
                DirCreatedAtWatchLocationFSInputEvent,
                DirUpdatedAtWatchLocationFSInputEvent,
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
            ),
        ):
            return False

        return True


class DirSystemInputPrintResponse(Action):
    """
    Print every DirSystem Dir related InputEvent.
    """

    _logger: logging.Logger
    _queue: OutputQueue

    def __init__(self) -> None:
        """
        Startup - with logging.
        """
        super().__init__()
        self._logger = logging.getLogger(__name__ + type(self).__name__)

    @staticmethod
    def consumes_inputs() -> Set[Type[InputEvent]]:
        """
        Any input related to changes inside a monitored directory is of interest.

        :return:
        """
        return {
            DirCreatedAtWatchLocationFSInputEvent,
            DirUpdatedAtWatchLocationFSInputEvent,
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

    @staticmethod
    def produces_outputs() -> Set[Type[OutputEvent]]:
        """
        No output is produce - all this does is print.

        :return:
        """
        return set()

    async def act(  # type: ignore
        self, event: InputEvent, state: Dict[str, Any]
    ) -> Coroutine[Any, Any, None]:
        """
        Construct a DiscordOutputEvent with the result of performing the calculation.
        """
        if not isinstance(event, InputEvent):
            self._logger.warning("Received wrong event type %s", type(event))
            yield None

        print("-------\n", "event seen by action - ", event, "\n-------")
