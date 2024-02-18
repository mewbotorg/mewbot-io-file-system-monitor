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
import logging
import sys
import tempfile
import uuid

import pytest
from mewbot.api.v1 import InputEvent

from mewbot.io.file_system_monitor import FileTypeFSInput
from mewbot.io.file_system_monitor.fs_events import (
    FileUpdatedAtWatchLocationFSInputEvent, FileCreatedAtWatchLocationFSInputEvent, FileDeletedFromWatchLocationFSInputEvent
)
from tests.io.test_io_file_system_monitor.fs_test_utils import (
    FileSystemTestUtilsDirEvents,
    FileSystemTestUtilsFileEvents,
)

# pylint: disable=invalid-name
# for clarity, test functions should be named after the things they test
# which means CamelCase in function names


class TestFileTypeFSInputLinux(FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents):
    """
    Tests that the expected file type events are produced from a monitored file.
    """

    sleep_duration: float = 4.0

    async def create_overwrite_update_unlink_file(
        self, input_path: str, output_queue: asyncio.Queue[InputEvent], i: str = "Not in loop"
    ) -> None:
        """
        Create a file - then update, modify and finally delete it.

        :param input_path:
        :param output_queue:
        :param i:
        :return:
        """

        with open(input_path, "w", encoding="utf-8") as test_outfile:
            test_outfile.write(
                f"\nThe testing will continue until moral improves - probably!- time {i}"
            )

        await asyncio.sleep(self.sleep_duration)

        await self.process_file_event_queue_response(
            output_queue=output_queue,
            file_path=input_path,
            event_type=FileCreatedAtWatchLocationFSInputEvent,
        )

        await asyncio.sleep(self.sleep_duration)

        with open(input_path, "w", encoding="utf-8") as test_outfile:
            test_outfile.write(
                f"\nThe testing will continue until moral improves - again! - time {i}"
            )

        await asyncio.sleep(self.sleep_duration)

        await self.process_file_event_queue_response(
            output_queue=output_queue,
            event_type=FileUpdatedAtWatchLocationFSInputEvent,
            file_path=input_path,
            message=f"Failing on the first write of loop {i}"
        )

        with open(input_path, "a", encoding="utf-8") as test_outfile:
            test_outfile.write(
                f"\nThe testing will continue until moral improves - really! - time {i}"
            )

        await asyncio.sleep(self.sleep_duration)

        await self.process_file_event_queue_response(
            output_queue=output_queue,
            event_type=FileUpdatedAtWatchLocationFSInputEvent,
            file_path=input_path,
        )

        os.unlink(input_path)

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def test_FileTypeFSInput_create_update_delete_target_file_loop_linux(self) -> None:
        """
        Linux version of running the create-update-delete loop.

        (diagnostic check - that this fails on linux or not).
        1 - Start without a file at all.
        2 - Starting the input
        3 - Create a file - check for the file creation event
        3 - Append to that file - check this produces the expected event
        4 - Delete the file - looking for the event
        4 - Do it a few times - check the results continue to be produced
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            input_path = os.path.join(tmp_dir_path, "test_file_delete_me.txt")

            run_task, output_queue = await self.get_FileTypeFSInput(input_path)

            for loop_num in range(10):

                await self.create_overwrite_update_unlink_file(input_path, output_queue, i=str(loop_num))

                await asyncio.sleep(self.sleep_duration)

                queue_length = output_queue.qsize()

                if queue_length == 2:
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        event_type=FileUpdatedAtWatchLocationFSInputEvent,
                        file_path=input_path,
                        allowed_queue_size=1,
                    )
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        event_type=FileDeletedFromWatchLocationFSInputEvent,
                        file_path=input_path,
                    )
                elif queue_length == 1:
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        event_type=FileDeletedFromWatchLocationFSInputEvent,
                        file_path=input_path,
                    )
                else:
                    raise NotImplementedError(f"unexpected queue length - {queue_length}")

            await self.cancel_task(run_task)

    async def update_delete_file_loop(
        self, tmp_file_path: str, output_queue: asyncio.Queue[InputEvent]
    ) -> None:
        """
        Update a file, delete it, then recreate it in a loop.

        Five iterations.
        Intended to catch transitory file events when a file is repeatedly deleted and recreated.
        :param tmp_file_path:
        :param output_queue:
        :return:
        """

        for i in range(5):
            # Generate some events which should end up in the queue
            # - Using blocking methods - this should still work
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write(
                    f"\nThe testing will continue until moral improves! "
                    f"But my moral is already so high - time {i}"
                )
            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=tmp_file_path,
                event_type=FileUpdatedAtWatchLocationFSInputEvent,
            )

            # Delete the file - then recreate it
            os.unlink(tmp_file_path)

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=tmp_file_path,
                event_type=FileDeletedFromWatchLocationFSInputEvent,
            )

            # Generate some events which should end up in the queue
            # - Using blocking methods - this should still work
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write(
                    "\nThe testing will continue until moral improves! Please... no...."
                )

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=tmp_file_path,
                event_type=FileCreatedAtWatchLocationFSInputEvent,
            )

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def test_FileTypeFSInput_existing_file_io_in_non_existing_file_linux(self, caplog) -> None:
        """
        Start without  file, create it, append to it and loop - looking for ghost events.

        1 - Start without a file at all.
        2 - Starting the input
        3 - Create a file - check for the file creation event
        3 - Append to that file - check this produces the expected event
        4 - Delete the file - looking for the event
        4 - Do it a few times - check the results continue to be produced
        """
        caplog.set_level(logging.INFO)

        with tempfile.TemporaryDirectory() as tmp_dir_path:

            # io will be done on this file
            tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")
            # tmp_file_path = "/home/ajcameron/test_file.txt"

            test_fs_input = FileTypeFSInput(input_path=tmp_file_path)
            assert isinstance(test_fs_input, FileTypeFSInput)

            output_queue: asyncio.Queue[InputEvent] = asyncio.Queue()
            test_fs_input.queue = output_queue

            # We need to retain control of the thread to delay shutdown
            # And to probe the results
            run_task = asyncio.get_running_loop().create_task(test_fs_input.run())

            task_exception = None
            try:
                task_exception = run_task.exception()
            except asyncio.exceptions.InvalidStateError:
                pass
            assert task_exception is None, task_exception

            # Give the class a chance to actually do init
            await asyncio.sleep(self.sleep_duration)

            # Check the task is still running
            task_exception = None
            try:
                task_exception = run_task.exception()
            except asyncio.exceptions.InvalidStateError:
                pass
            assert task_exception is None, task_exception

            # Modify the file - which should generate an event
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write("We are testing mewbot!")

            await asyncio.sleep(self.sleep_duration)

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=tmp_file_path,
                event_type=FileCreatedAtWatchLocationFSInputEvent,
            )

            # Modify the file again - check for changes - again
            #  - Check the task is still running
            task_exception = None
            try:
                task_exception = run_task.exception()
            except asyncio.exceptions.InvalidStateError:
                pass
            assert task_exception is None, task_exception

            # Modify the file - which should generate an event
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write("We are (still) testing mewbot!")

            await asyncio.sleep(self.sleep_duration)

            # - Check this has produce an event which is visible in the queue
            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=tmp_file_path,
                event_type=FileUpdatedAtWatchLocationFSInputEvent,
            )

            # Generate some events which should end up in the queue
            # - Using blocking methods - this should still work
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write(
                    f"Testing string for mewbot - {str(uuid.uuid4())}"
                )
                test_outfile.flush()

            await asyncio.sleep(self.sleep_duration)

            # Check the task is still running
            task_exception = None
            try:
                task_exception = run_task.exception()
            except asyncio.exceptions.InvalidStateError:
                pass
            assert task_exception is None, task_exception

            # assert True is False, caplog.text

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=tmp_file_path,
                event_type=FileUpdatedAtWatchLocationFSInputEvent,
            )

            await asyncio.sleep(self.sleep_duration)

            for i in range(5):

                # Check the input task is still running
                task_exception = None
                try:
                    task_exception = run_task.exception()
                except asyncio.exceptions.InvalidStateError:
                    pass
                assert task_exception is None, task_exception

                await asyncio.sleep(self.sleep_duration)

                # Generate some events which should end up in the queue
                # - Using blocking methods - this should still work
                with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                    test_outfile.write(
                        f"\nThe testing will continue until moral improves! "
                        f"{str(uuid.uuid4())}- time {i}"
                    )

                # Check the task is still running
                task_exception = None
                try:
                    task_exception = run_task.exception()
                except asyncio.exceptions.InvalidStateError:
                    pass
                assert task_exception is None, task_exception

                # Give the task a chance to generate
                await asyncio.sleep(self.sleep_duration)

                assert output_queue.qsize() > 0, f"No event made it to the queue - \n{caplog.text}"

                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    file_path=tmp_file_path,
                    event_type=FileUpdatedAtWatchLocationFSInputEvent,
                    message=f"In loop {i}"
                )

                # Delete the file - then recreate it
                os.unlink(tmp_file_path)

                await asyncio.sleep(self.sleep_duration)

                queue_length = output_queue.qsize()

                if queue_length == 2:
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=tmp_file_path,
                        allowed_queue_size=1,
                        event_type=FileUpdatedAtWatchLocationFSInputEvent,
                    )

                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=tmp_file_path,
                        event_type=FileDeletedFromWatchLocationFSInputEvent,
                    )

                elif queue_length == 1:
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=tmp_file_path,
                        event_type=FileDeletedFromWatchLocationFSInputEvent,
                    )

                else:
                    raise NotImplementedError(f"Unexpected queue length - {queue_length}")

                # Generate some events which should end up in the queue
                # - Using blocking methods - this should still work
                with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                    test_outfile.write(
                        "\nThe testing will continue until moral improves!"
                        " If this does not improve your moral ... that's fair, tbh."
                    )

                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    event_type=FileCreatedAtWatchLocationFSInputEvent,
                    file_path=tmp_file_path,
                )

            # Otherwise the queue seems to be blocking pytest from a clean exit.
            await self.cancel_task(run_task)

            # Tests are NOW making a clean exist after this test
            # This seems to have been a problem with the presence of a queue

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def test_FileTypeFSInput_existing_dir_deleted_and_replaced_with_file_linux(
        self,
    ) -> None:
        """
        Create and delete a file at a location in a loop.

        1 - Start without a file at all.
        2 - Starting the input
        3 - create a dir at the monitored location - this should do nothing
        4 - delete that dir
        5 - Create a file - check for the file creation event
        6 - Append to that file - check this produces the expected event
        7 - Delete the file - looking for the event
        8 - Do it a few times - check the results continue to be produced
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            # io will be done on this file
            tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")

            run_task, output_queue = await self.get_FileTypeFSInput(tmp_file_path)

            # Give the class a chance to actually do init
            await asyncio.sleep(0.5)

            # Make a dir - the class should not respond
            os.mkdir(tmp_file_path)

            await asyncio.sleep(0.5)

            await self.verify_queue_size(output_queue, task_done=False)

            # Delete the file - the class should also not respond
            os.rmdir(tmp_file_path)

            await asyncio.sleep(0.5)

            await self.verify_queue_size(output_queue, task_done=False)

            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write("We are testing mewbot!")

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                event_type=FileCreatedAtWatchLocationFSInputEvent,
                file_path=tmp_file_path,
            )

            await asyncio.sleep(self.sleep_duration)

            # Generate some events which should end up in the queue
            # - Using blocking methods - this should still work
            with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                test_outfile.write("\nThe testing will continue until moral improves!")

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                event_type=FileUpdatedAtWatchLocationFSInputEvent,
                file_path=tmp_file_path,
            )

            await asyncio.sleep(self.sleep_duration)

            for i in range(5):

                # Generate some events which should end up in the queue
                # - Using blocking methods - this should still work
                with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                    test_outfile.write(
                        f"\nThe testing will continue until moral improves! - time {i}"
                    )

                await asyncio.sleep(self.sleep_duration)

                assert output_queue.qsize() > 0, f"Failing in loop {i}"

                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    event_type=FileUpdatedAtWatchLocationFSInputEvent,
                    file_path=tmp_file_path,
                )

                # Delete the file - then recreate it
                os.unlink(tmp_file_path)

                await asyncio.sleep(0.5)

                queue_length = output_queue.qsize()

                if queue_length == 2:
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=tmp_file_path,
                        allowed_queue_size=1,
                        event_type=FileUpdatedAtWatchLocationFSInputEvent,
                    )

                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=tmp_file_path,
                        event_type=FileDeletedFromWatchLocationFSInputEvent,
                    )

                elif queue_length == 1:
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=tmp_file_path,
                        event_type=FileDeletedFromWatchLocationFSInputEvent,
                    )

                else:
                    raise NotImplementedError(f"Unexpected queue_length - {queue_length}")

                # Generate some events which should end up in the queue
                # - Using blocking methods - this should still work
                with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
                    test_outfile.write("\nThe testing will continue until moral improves!")

                await asyncio.sleep(self.sleep_duration)

                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    event_type=FileCreatedAtWatchLocationFSInputEvent,
                )

                await asyncio.sleep(self.sleep_duration)


            # Otherwise the queue seems to be blocking pytest from a clean exit.
            await self.cancel_task(run_task)

            # Tests are NOW making a clean exist after this test
            # This seems to have been a problem with the presence of a queue
