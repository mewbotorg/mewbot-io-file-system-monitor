#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

# pylint: disable=duplicate-code
# this is an example - duplication for emphasis is desirable

"""
Tooling to support the file_input_monitor_bot.

This bot notifies you of any changes to a file at the given location.
"""

from __future__ import annotations

from typing import Any, AsyncIterable, Dict, Set, Type

import logging

from mewbot.api.v1 import Action, Trigger
from mewbot.core import InputEvent, OutputEvent, OutputQueue

from mewbot.io.file_system_monitor import (
    FileCreatedAtWatchLocationFSInputEvent,
    FileDeletedFromWatchLocationFSInputEvent,
    FileUpdatedAtWatchLocationFSInputEvent,
    FSInputEvent,
)


class FileSystemAllCommandTrigger(Trigger):
    """
    Nothing fancy - just fires whenever there is a file related FSInputEvent.
    """

    @staticmethod
    def consumes_inputs() -> Set[Type[InputEvent]]:
        """
        Consumes all input file manipulation events.

        :return:
        """
        return {
            FileCreatedAtWatchLocationFSInputEvent,
            FileUpdatedAtWatchLocationFSInputEvent,
            FileDeletedFromWatchLocationFSInputEvent,
        }

    def matches(self, event: InputEvent) -> bool:
        """
        Matches on all inout file created events.

        :param event:
        :return:
        """

        if not isinstance(
            event,
            (
                FileCreatedAtWatchLocationFSInputEvent,
                FileUpdatedAtWatchLocationFSInputEvent,
                FileDeletedFromWatchLocationFSInputEvent,
            ),
        ):
            return False

        return True


class FileSystemInputPrintResponse(Action):
    """
    Print every FileSystem File related InputEvent.
    """

    _logger: logging.Logger
    _queue: OutputQueue

    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger(__name__ + type(self).__name__)

    @staticmethod
    def consumes_inputs() -> Set[Type[InputEvent]]:
        """
        All inout file events are of interest to this bot.

        :return:
        """
        return {
            FileCreatedAtWatchLocationFSInputEvent,
            FileUpdatedAtWatchLocationFSInputEvent,
            FileDeletedFromWatchLocationFSInputEvent,
        }

    @staticmethod
    def produces_outputs() -> Set[Type[OutputEvent]]:
        """
        This bot does not produce outputs - it just prints what it sees.

        :return:
        """
        return set()

    async def act(
        self, event: InputEvent, state: Dict[str, Any]
    ) -> AsyncIterable[OutputEvent]:
        """
        Construct a DiscordOutputEvent with the result of performing the calculation.
        """
        if not isinstance(event, FSInputEvent):
            self._logger.warning("Received wrong event type %s", type(event))
            raise StopAsyncIteration

        print(event)
        yield OutputEvent()
