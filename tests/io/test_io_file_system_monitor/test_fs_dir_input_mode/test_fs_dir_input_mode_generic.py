# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

# Aim is to run, in sections, as many of the input methods as possible
# Including running a full bot with logging triggers and actions.
# However, individual components also have to be isolated for testing purposes.

"""
Tests the dir input - monitors a directory for changes - on any system.
"""

from typing import Any

import asyncio
import logging
import os
import shutil
import sys
import tempfile
import uuid

import pytest

from mewbot.io.file_system_monitor.fs_events import (
    DirCreatedAtWatchLocationFSInputEvent,
    DirCreatedWithinWatchedDirFSInputEvent,
    DirDeletedFromWatchedDirFSInputEvent,
    DirDeletedFromWatchLocationFSInputEvent,
    DirMovedWithinWatchedDirFSInputEvent,
    DirUpdatedAtWatchLocationFSInputEvent,
    DirUpdatedWithinWatchedDirFSInputEvent,
    FileCreatedWithinWatchedDirFSInputEvent,
    FileDeletedWithinWatchedDirFSInputEvent,
    FileMovedWithinWatchedDirFSInputEvent,
    FileUpdatedWithinWatchedDirFSInputEvent,
)
from tests.io.test_io_file_system_monitor.fs_test_utils import (
    FileSystemTestUtilsDirEvents,
    FileSystemTestUtilsFileEvents,
)

# pylint: disable=invalid-name
# for clarity, test functions should be named after the things they test
# which means CamelCase in function names

# pylint: disable=duplicate-code
# Due to testing for the subtle differences between how the monitors respond in windows and
# linux, code has - inevitably - ended up very similar.
# As such, this inspection has had to be disabled.

# pylint: disable=protected-access
# Need to access the internals of the classes to put them into pathological states.


class TestDirTypeFSInputGenericTests(
    FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents
):
    """
    Tests which should respond the same on any operating system.

    (Ideally, eventually, this will be _all_ of them - but we need some diagnostics as the
    underlying apis do behave differently on different systems).
    """

    sleep_delay: int = 1

    # DIRS IN DIRS

    @pytest.mark.asyncio
    async def test_DirTypeFSInput_existing_dir_create_dir(self, caplog) -> None:
        """
        Check for the expected created signal from a dir which is created in a monitored dir.
        """

        caplog.set_level(logging.INFO)

        with tempfile.TemporaryDirectory() as tmp_dir_path:

            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # Give the class a chance to do init
            await asyncio.sleep(self.sleep_delay)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            os.mkdir(new_dir_path)

            await asyncio.sleep(self.sleep_delay)

            assert output_queue.qsize() > 0, f"Queue has not events - \n{caplog.text}\n"

            # We expect a directory creation event to be registered inside the watched dir
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            await self.cancel_task(run_task)