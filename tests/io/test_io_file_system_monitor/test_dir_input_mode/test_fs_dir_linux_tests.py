# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

# Aim is to run, in sections, as many of the input methods as possible
# Including running a full bot with logging triggers and actions.
# However, individual components also have to be isolated for testing purposes.

"""
Tests the dir input - monitors a directory for changes.
"""


import asyncio
import os
import sys
import tempfile

import pytest

from mewbot.io.file_system_monitor.fs_events import (
    DirCreatedAtWatchLocationFSInputEvent,
    DirMovedWithinWatchedDirFSInputEvent,
    DirUpdatedAtWatchLocationFSInputEvent,
    FileCreatedWithinWatchedDirFSInputEvent,
    FileDeletedWithinWatchedDirFSInputEvent,
    FileUpdatedWithinWatchedDirFSInputEvent,
)

from ..fs_test_utils import FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents

# pylint: disable=invalid-name
# for clarity, test functions should be named after the things they test
# which means CamelCase in function names

# pylint: disable=duplicate-code
# Due to testing for the subtle differences between how the monitors respond in windows and
# linux, code has - inevitably - ended up very similar.
# As such, this inspection has had to be disabled.


class TestDirTypeFSInputLinuxLikeTests(
    FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents
):
    """
    Tests for diagnosis of divergent behavior on linux like systems.
    """

    # Need to make sure there are windows equivalents for all these tests
    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def test_DirTypeFSInput_existing_dir_cre_upd_del_file_loop_linux(self) -> None:
        """
        Create, update and delete a file in a loop - to check for ghost events.

        Check for expected created signal from a file which is created in a monitored dir.
        Followed by an attempt to update the file.
        Then an attempt to delete the file.
        This is done in a loop - to check for any problems with stale events
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            for i in range(8):
                # - Using blocking methods - this should still work
                new_file_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

                with open(new_file_path, "w", encoding="utf-16") as output_file:
                    output_file.write("Here we go")

                # This is just ... utterly weird
                if i == 0:
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=new_file_path,
                        event_type=FileCreatedWithinWatchedDirFSInputEvent,
                    )
                else:
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=tmp_dir_path,
                        event_type=DirUpdatedAtWatchLocationFSInputEvent,
                    )
                    await self.process_file_event_queue_response(
                        output_queue=output_queue,
                        file_path=new_file_path,
                        event_type=FileCreatedWithinWatchedDirFSInputEvent,
                    )

                with open(new_file_path, "a", encoding="utf-16") as output_file:
                    output_file.write(f"Here we go again - {i}")

                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=tmp_dir_path,
                    event_type=DirUpdatedAtWatchLocationFSInputEvent,
                )
                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    file_path=new_file_path,
                    event_type=FileUpdatedWithinWatchedDirFSInputEvent,
                )

                os.unlink(new_file_path)
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=tmp_dir_path,
                    event_type=DirUpdatedAtWatchLocationFSInputEvent,
                )

                # Probably do not want
                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    file_path=new_file_path,
                    event_type=FileUpdatedWithinWatchedDirFSInputEvent,
                )

                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=tmp_dir_path,
                    event_type=DirUpdatedAtWatchLocationFSInputEvent,
                )
                await self.process_file_event_queue_response(
                    output_queue=output_queue,
                    file_path=new_file_path,
                    event_type=FileDeletedWithinWatchedDirFSInputEvent,
                )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def testDirTypeFSInput_existing_dir_create_update_move_file_linux(self) -> None:
        """
        Create, update and then move a file.

        Check for the expected created signal from a file which is created in a monitored dir.
        Followed by an attempt to update the file, then move it.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_file_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            with open(new_file_path, "w", encoding="utf-16") as output_file:
                output_file.write("Here we go")

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=new_file_path,
                event_type=FileCreatedWithinWatchedDirFSInputEvent,
            )

            with open(new_file_path, "a", encoding="utf-16") as output_file:
                output_file.write("Here we go again")

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirUpdatedAtWatchLocationFSInputEvent,
            )

            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=new_file_path,
                event_type=FileUpdatedWithinWatchedDirFSInputEvent,
            )

            # Move a file to a different location
            post_move_file_path = os.path.join(tmp_dir_path, "moved_text_file_delete_me.txt")
            os.rename(src=new_file_path, dst=post_move_file_path)

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirUpdatedAtWatchLocationFSInputEvent,
            )
            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=new_file_path,
                event_type=FileUpdatedWithinWatchedDirFSInputEvent,
            )

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirUpdatedAtWatchLocationFSInputEvent,
            )

            await self.process_file_move_queue_response(
                output_queue,
                file_src_parth=new_file_path,
                file_dst_path=post_move_file_path,
            )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def test_DirTypeFSInput_existing_dir_cre_ud_move_file_loop_linux(
        self,
    ) -> None:
        """
        Check for the expected created signal from a file which is created in a monitored dir.

        Followed by an attempt to update the file.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            for i in range(10):
                # - Using blocking methods - this should still work
                new_file_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

                with open(new_file_path, "w", encoding="utf-16") as output_file:
                    output_file.write("Here we go")

                await asyncio.sleep(0.5)
                output_queue_list = self.dump_queue_to_list(output_queue)

                self.check_queue_for_file_creation_input_event(
                    output_queue=output_queue_list,
                    file_path=new_file_path,
                    message=f"in loop {i}",
                )

                with open(new_file_path, "a", encoding="utf-16") as output_file:
                    output_file.write("Here we go again")

                await asyncio.sleep(0.1)

                output_queue_list = self.dump_queue_to_list(output_queue)

                self.check_queue_for_dir_update_input_event(
                    output_queue=output_queue_list,
                    dir_path=tmp_dir_path,
                    message=f"in loop {i}",
                )
                self.check_queue_for_file_update_input_event(
                    output_queue=output_queue_list,
                    file_path=new_file_path,
                    message=f"in loop {i}",
                )

                # Move a file to a different location
                post_move_file_path = os.path.join(
                    tmp_dir_path, "moved_text_file_delete_me.txt"
                )
                os.rename(src=new_file_path, dst=post_move_file_path)
                await asyncio.sleep(0.5)

                output_queue_list = self.dump_queue_to_list(output_queue)

                self.check_queue_for_dir_update_input_event(
                    output_queue=output_queue_list,
                    dir_path=tmp_dir_path,
                    message=f"in loop {i}",
                )
                self.check_queue_for_file_move_input_event(
                    output_queue=output_queue_list,
                    file_src_parth=new_file_path,
                    file_dst_path=post_move_file_path,
                    message=f"in loop {i}",
                )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def testDirTypeFSInput_existing_dir_create_move_dir_linux(self) -> None:
        """
        Create a dir in a monitored dir - then move it around - checking the output.
        """

        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedAtWatchLocationFSInputEvent,
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
            await self.process_file_move_queue_response(
                output_queue, file_src_parth=new_dir_path, file_dst_path=post_move_dir_path
            )

            await self.cancel_task(run_task)
