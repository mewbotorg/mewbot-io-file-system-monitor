# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

# Aim is to run, in sections, as many of the input methods as possible
# Including running a full bot with logging triggers and actions.
# However, individual components also have to be isolated for testing purposes.

"""
Tests the dir input - monitors a directory for changes - on any system.
"""


import asyncio
import os
import shutil
import sys
import tempfile

import pytest

from mewbot.io.file_system_monitor.fs_events import (
    DirCreatedWithinWatchedDirFSInputEvent,
    DirDeletedFromWatchedDirFSInputEvent,
    DirMovedWithinWatchedDirFSInputEvent,
    DirUpdatedAtWatchLocationFSInputEvent,
    DirUpdatedWithinWatchedDirFSInputEvent,
    FileCreatedWithinWatchedDirFSInputEvent,
    FileDeletedWithinWatchedDirFSInputEvent,
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


class TestDirTypeFSInputWindowsTests(
    FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents
):
    """
    Tests which should respond the same on any operating system.

    (Ideally, eventually, this will be _all_ of them - but we need some diagnostics as the
    underlying apis do behave differently on different systems).
    """

    sleep_delay: int = 1

    @pytest.mark.asyncio
    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only test")
    async def test_DirTypeFSInput_existing_dir_cre_ud_file_del_file(self) -> None:
        """
        Start in an existing dir - then create and update a file.

        Check for the expected created signal from a file which is created in a monitored dir.
        Followed by an attempt to update the file.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_file_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            with open(new_file_path, "w", encoding="utf-16") as output_file:
                output_file.write("Here we go")

            await asyncio.sleep(self.sleep_delay)

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=new_file_path,
                event_type=FileCreatedWithinWatchedDirFSInputEvent,
                allowed_queue_size=[0, 1, 2, 3, 4],
            )

            with open(new_file_path, "a", encoding="utf-16") as output_file:
                output_file.write("Here we go again")

            await asyncio.sleep(self.sleep_delay)

            # The directory we're watching itself has been updated with the file change
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                allowed_queue_size=[0, 1, 2, 3, 4, 5],
                event_type=DirUpdatedAtWatchLocationFSInputEvent,
            )

            queue_list = self.dump_queue_to_list(output_queue)

            # Need to do some detailed analysis of the queue - multiple outcomes are fine
            if len(queue_list) == 1:
                self.validate_dir_update_input_event_within_watched_dir(
                    input_event=queue_list[0], dir_path=tmp_dir_path
                )

            queue_list = self.dump_queue_to_list(output_queue)

            assert len(queue_list) == 0

            # Now delete the file
            os.unlink(new_file_path)

            await asyncio.sleep(self.sleep_delay)

            pre_dump_queue_size = output_queue.qsize()

            queue_list = self.dump_queue_to_list(output_queue)
            assert pre_dump_queue_size == len(queue_list)

            self.validate_dir_input_event(
                queue_list[0],
                dir_path=tmp_dir_path,
                event_type=DirUpdatedWithinWatchedDirFSInputEvent,
            )

            self.validate_file_input_event(
                queue_list[1],
                file_path=new_file_path,
                event_type=FileDeletedWithinWatchedDirFSInputEvent,
            )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only test")
    async def testDirTypeFSInput_existing_dir_create_dir_del_dir_windows(self) -> None:
        """
        Check for the expected created signal from a dir which is created in a monitored dir.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            # Create the dir - check for the response
            os.mkdir(new_dir_path)

            await asyncio.sleep(self.sleep_delay)

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            # Delete the dir - check for the response
            shutil.rmtree(new_dir_path)

            await asyncio.sleep(self.sleep_delay)

            # - we should see an update to the monitored directory
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirUpdatedWithinWatchedDirFSInputEvent,
            )

            await asyncio.sleep(self.sleep_delay)

            # - we should then see a deletion event within the monitored dir
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirDeletedFromWatchedDirFSInputEvent,
            )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="windows only test")
    async def testDirTypeFSInput_existing_dir_create_dir_del_dir_starting_non_exist_dir_winodws(
        self,
    ) -> None:
        """
        Start without a directory at the path - then create one and run the test.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            # Create the dir - check for the response
            os.mkdir(new_dir_path)

            await asyncio.sleep(self.sleep_delay)

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            # Delete the dir - check for the response
            shutil.rmtree(new_dir_path)

            await asyncio.sleep(self.sleep_delay)

            # - we should see an update to the monitored directory
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirUpdatedWithinWatchedDirFSInputEvent,
            )

            # - we should then see a deletion event within the monitored dir
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirDeletedFromWatchedDirFSInputEvent,
            )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="windows only test")
    async def testDirTypeFSInput_existing_dir_create_move_dir_move_by_rename_windows(
        self,
    ) -> None:
        """
        Create a dir in a monitored dir - then move it around via a rename.
        """

        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            await asyncio.sleep(0.1)

            # Move a file to a different location
            post_move_dir_path = os.path.join(tmp_dir_path, "moved_text_file_delete_me.txt")

            os.rename(src=new_dir_path, dst=post_move_dir_path)

            # This is an asymmetry between how files and folders handle delete
            # left in while I try and think how to deal sanely with it
            # await self.process_dir_deletion_response(output_queue, dir_path=new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirMovedWithinWatchedDirFSInputEvent,
            )

            # Now create a new folder inside the

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="windows only test")
    async def testDirTypeFSInput_existing_dir_create_move_dir_move_by_shutil_move_windows(
        self,
    ) -> None:
        """
        Create a directory inside the monitored dir - then move it using shutil.
        """

        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            os.mkdir(new_dir_path)

            await asyncio.sleep(self.sleep_delay)

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            await asyncio.sleep(self.sleep_delay)

            # Move a file to a different location
            post_move_dir_path = os.path.join(tmp_dir_path, "moved_text_file_delete_me.txt")
            shutil.move(src=new_dir_path, dst=post_move_dir_path)

            await asyncio.sleep(self.sleep_delay)

            # This is an asymmetry between how files and folders handle delete
            # left in while I try and think how to deal sanely with it
            # await self.process_dir_deletion_response(output_queue, dir_path=new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirMovedWithinWatchedDirFSInputEvent,
            )

            # Now create a new folder inside the

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only test")
    async def testDirTypeFSInput_existing_dir_modify_file(self) -> None:
        """
        Create a file in a monitored dir, then modify it.

        Checking for the right signals.
        This may not be working - windows modification events are weird.
        """
        import ctypes  # pylint: disable = import-outside-toplevel

        with tempfile.TemporaryDirectory() as tmp_dir_path:
            _, _, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            file_attribute_hidden = 0x02

            ctypes.windll.kernel32.SetFileAttributesW(tmp_dir_path, file_attribute_hidden)

            await asyncio.sleep(5)

            new_path = os.path.join(tmp_dir_path, "test_dir")
            os.mkdir(new_path)

            ctypes.windll.kernel32.SetFileAttributesW(new_path, file_attribute_hidden)
