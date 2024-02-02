# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

# Aim is to run, in sections, as many of the input methods as possible
# Including running a full bot with logging triggers and actions.
# However, individual components also have to be isolated for testing purposes.

"""
Tests for the file input mode for the file_system_monitor IOConfig.
"""

import asyncio
import os
import tempfile
import uuid

import pytest
from mewbot.api.v1 import InputEvent

from mewbot.io.file_system_monitor import FileTypeFSInput
from mewbot.io.file_system_monitor.fs_events import (
    FileUpdatedAtWatchLocationFSInputEvent,
)
from tests.io.test_io_file_system_monitor.fs_test_utils import (
    FileSystemTestUtilsDirEvents,
    FileSystemTestUtilsFileEvents,
)

# pylint: disable=invalid-name
# for clarity, test functions should be named after the things they test
# which means CamelCase in function names


class TestFileTypeFSInput(FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents):
    """
    Tests that the expected file type events are produced from a monitored file.
    """

    # - INIT AND ATTRIBUTES

    @pytest.mark.asyncio
    async def test_FileTypeFSInput__init__input_path_None(self) -> None:
        """
        Start a copy of a file type input - with input path set to None.

        Input_path is set to None
        """
        test_fs_input = FileTypeFSInput(input_path=None)
        assert isinstance(test_fs_input, FileTypeFSInput)

    @pytest.mark.asyncio
    async def test_FileTypeFSInput__init__input_path_nonsense(self) -> None:
        """
        Start a copy of a file type input - with input path set to nonsense.
        """
        input_path_str = "\\///blargleblarge_not_a_path"
        test_fs_input = FileTypeFSInput(input_path=input_path_str)
        assert isinstance(test_fs_input, FileTypeFSInput)

        # Test attributes which should have been set
        assert test_fs_input.input_path == input_path_str
        test_fs_input.input_path = "//\\another thing which does not exist"

        assert test_fs_input.input_path_exists is False

        try:
            test_fs_input.input_path_exists = True
        except AttributeError:
            pass

    @pytest.mark.asyncio
    async def test_FileTypeFSInput__init__input_path_existing_dir(self) -> None:
        """
        Tests that we can start an isolated copy of FileTypeFSInput - for testing purposes.

        This basic method will be used for all the functional tests.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            test_fs_input = FileTypeFSInput(input_path=tmp_dir_path)
            assert isinstance(test_fs_input, FileTypeFSInput)

            assert test_fs_input.input_path == tmp_dir_path
            assert test_fs_input.input_path_exists is True

    # - RUN

    @pytest.mark.asyncio
    async def test_FileTypeFSInput_run_without_error_inside_existing_dir(self) -> None:
        """
        Tests that the run method of the input class does not throw an error.

        Testing on a dir which actually exists.
        This will not produce actual events, because it's a FileTypeFSInput
        The object it's pointed at is a dir.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            test_fs_input = FileTypeFSInput(input_path=tmp_dir_path)
            assert isinstance(test_fs_input, FileTypeFSInput)

            # We need to retain control of the thread to preform shutdown
            asyncio.get_running_loop().create_task(test_fs_input.run())

            await asyncio.sleep(0.5)
            # Note - manually stopping the loop seems to lead to a rather nasty cash

    @pytest.mark.asyncio
    async def test_FileTypeFSInput_run_without_error_existing_file(self) -> None:
        """
        Tests that the run method of the input class does not throw an error.

        Testing on a dir which actually exists.
        This will not produce actual events, because it's a FileTypeFSInput
        The object it's pointed at is a dir.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write("We are testing mewbot!")

            test_fs_input = FileTypeFSInput(input_path=tmp_file_path)
            assert isinstance(test_fs_input, FileTypeFSInput)

            # We need to retain control of the thread to preform shutdown
            asyncio.get_running_loop().create_task(test_fs_input.run())

            await asyncio.sleep(0.5)
            # Note - manually stopping the loop seems to lead to a rather nasty cash

            # Tests are making a clean exist after this test

    @pytest.mark.asyncio
    async def test_FileTypeFSInput_existing_file_io_in_existing_file(self) -> None:
        """
        Starting the monitor on a file which already exists.

        1 - Creating a file which actually exists
        2 - Starting the input
        3 - Append to that file - check this produces the expected event
        4 - Do it a few times - check the results continue to be produced
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write("We are testing mewbot!")

            test_fs_input = FileTypeFSInput(input_path=tmp_file_path)
            assert isinstance(test_fs_input, FileTypeFSInput)

            output_queue: asyncio.Queue[InputEvent] = asyncio.Queue()
            test_fs_input.queue = output_queue

            # We need to retain control of the thread to delay shutdown
            # And to probe the results
            run_task = asyncio.get_running_loop().create_task(test_fs_input.run())

            # Give the class a chance to actually do init
            await asyncio.sleep(0.5)

            # Generate some events which should end up in the queue
            # - Using blocking methods - this should still work
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write(str(uuid.uuid4()))

            await self.process_file_event_queue_response(
                output_queue=output_queue, event_type=FileUpdatedAtWatchLocationFSInputEvent
            )

            for i in range(20):
                # Generate some events which should end up in the queue
                # - Using blocking methods - this should still work
                with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                    test_outfile.write(
                        f"\nThe testing will continue until moral improves! - "
                        f"{str(uuid.uuid4())} - time {i}"
                    )

                await asyncio.sleep(0.5)

                if output_queue.qsize() == 0:
                    try:
                        run_task.exception()
                    except asyncio.exceptions.InvalidStateError:
                        pass

                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    file_path=tmp_file_path,
                    event_type=FileUpdatedAtWatchLocationFSInputEvent,
                )

            # Otherwise the queue seems to be blocking pytest from a clean exit.
            await self.cancel_task(run_task)

            # Tests are NOW making a clean exist after this test
            # This seems to have been a problem with the presence of a queue
