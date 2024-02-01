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

    # DIRS IN DIRS

    @pytest.mark.asyncio
    async def test_DirTypeFSInput_existing_dir_create_dir(self) -> None:
        """
        Check for the expected created signal from a dir which is created in a monitored dir.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            os.mkdir(new_dir_path)
            # We expect a directory creation event to be registered inside the watched dir
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            await self.cancel_task(run_task)

    # FILES IN DIRS

    @pytest.mark.asyncio
    async def test_DirTypeFSInput_existing_dir_crefile(self) -> None:
        """
        Start in an existing dir - then create a file in it.

        Check for the expected created signal from a file which is created in a monitored dir.
        Followed by an attempt to update the file.
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

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
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
            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=new_file_path,
                event_type=FileCreatedWithinWatchedDirFSInputEvent,
            )

            with open(new_file_path, "a", encoding="utf-16") as output_file:
                output_file.write("Here we go again")

            # The directory we're watching itself has been updated with the file change
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                allowed_queue_size=1,
                event_type=DirUpdatedAtWatchLocationFSInputEvent,
            )

            # The file has also been updated
            await self.process_file_event_queue_response(
                output_queue=output_queue,
                file_path=new_file_path,
                event_type=FileUpdatedWithinWatchedDirFSInputEvent,
            )

            # Now delete the file
            os.unlink(new_file_path)

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                allowed_queue_size=1,
                event_type=DirUpdatedWithinWatchedDirFSInputEvent,
            )

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_file_path,
                allowed_queue_size=1,
                event_type=FileDeletedWithinWatchedDirFSInputEvent,
            )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    async def testDirTypeFSInput_existing_dir_create_dir_del_dir(self) -> None:
        """
        Check for the expected created signal from a dir which is created in a monitored dir.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            # Create the dir - check for the response
            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            # Delete the dir - check for the response
            shutil.rmtree(new_dir_path)

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
    async def testDirTypeFSInput_existing_dir_create_dir_del_dir_starting_non_exist_dir(
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
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            # Delete the dir - check for the response
            shutil.rmtree(new_dir_path)

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
    async def testDirTypeFSInput_non_existing_dir_create_dir_del_dir(self) -> None:
        """
        Check for the expected created signal from a dir which is created in a monitored dir.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            run_task, output_queue, _ = await self.get_DirTypeFSInput(new_dir_path)

            # Create the dir - check for the response
            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedAtWatchLocationFSInputEvent,
            )

            # Delete the dir - check for the response
            shutil.rmtree(new_dir_path)

            # - we should see an update to the monitored directory
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirDeletedFromWatchLocationFSInputEvent,
            )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    async def testDirTypeFSInput_non_existing_dir_create_dir_del_dir_set_watch_None(
        self,
    ) -> None:
        """
        Unexpectedly set the input path to be None, and then monitor dir watcher.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            run_task, output_queue, test_fs_input = await self.get_DirTypeFSInput(
                new_dir_path
            )

            # Create the dir - check for the response
            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedAtWatchLocationFSInputEvent,
            )

            # Delete the dir - check for the response
            shutil.rmtree(new_dir_path)

            # - we should see an update to the monitored directory
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirDeletedFromWatchLocationFSInputEvent,
            )

            # Try and break things
            test_fs_input.input_path = None
            run_task_2 = asyncio.get_running_loop().create_task(test_fs_input.run())

            await self.cancel_task(run_task)
            await self.cancel_task(run_task_2)

    @pytest.mark.asyncio
    async def testDirTypeFSInput_non_existing_dir_create_dir_del_dir_set_ip_None(
        self,
    ) -> None:
        """
        Unexpectedly set the input path to be None, and then monitor dir watcher.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            run_task, output_queue, test_fs_input = await self.get_DirTypeFSInput(
                new_dir_path
            )

            # Create the dir - check for the response
            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedAtWatchLocationFSInputEvent,
            )

            # Delete the dir - check for the response
            shutil.rmtree(new_dir_path)

            # - we should see an update to the monitored directory
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirDeletedFromWatchLocationFSInputEvent,
            )

            # Try and break things
            test_fs_input._input_path_state.input_path = None
            run_task_2 = asyncio.get_running_loop().create_task(
                test_fs_input.monitor_input_path_dir()
            )

            run_task_3 = asyncio.get_running_loop().create_task(
                test_fs_input.file_system_observer.monitor_dir_watcher()
            )
            assert await self.cancel_task(run_task_3) is None  # type: ignore

            # Try and interfere with the observer directly
            test_fs_input.file_system_observer._input_path = None

            run_task_4 = asyncio.get_running_loop().create_task(
                test_fs_input.file_system_observer.monitor_dir_watcher()
            )

            run_task_5 = asyncio.get_running_loop().create_task(
                test_fs_input.file_system_observer._process_event_from_watched_dir(
                    "nonsense"  # type: ignore
                )
            )

            # Write a bad event onto the wire - to trigger an exception which should be handled
            test_fs_input.file_system_observer._input_path = None
            run_task_6 = asyncio.get_running_loop().create_task(
                test_fs_input.file_system_observer._process_file_move_event(
                    "nonsense"  # type: ignore
                )
            )

            await self.cancel_task(run_task)
            await self.cancel_task(run_task_2)
            # The observer has been sabotaged. This should fail.
            try:
                await self.cancel_task(run_task_4)  # type: ignore
            except NotImplementedError:
                pass
            await self.cancel_task(run_task_5)
            try:
                await self.cancel_task(run_task_6)
            except (NotImplementedError, AttributeError):
                pass

    @pytest.mark.asyncio
    async def testDirTypeFSInput_monitor_dir_watcher_normal_operation(
        self,
    ) -> None:
        """
        Unexpectedly set the input path to be None, and then monitor dir watcher.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            run_task, output_queue, test_fs_input = await self.get_DirTypeFSInput(
                new_dir_path
            )

            # There's no path, so there is currently no observer
            assert not hasattr(test_fs_input, "file_system_observer")

            # Create the dir - check for the response
            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedAtWatchLocationFSInputEvent,
            )

            run_task = asyncio.get_running_loop().create_task(
                test_fs_input.file_system_observer.monitor_dir_watcher()  # type: ignore
            )

            shutil.rmtree(new_dir_path)

            assert await self.cancel_task(run_task) is None  # type: ignore

    @pytest.mark.asyncio
    async def testDirTypeFSInput_monitor_dir_watcher_file_created(
        self,
    ) -> None:
        """
        Set up a dir watcher - then create a file where it expects a dr.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            run_task, output_queue, test_fs_input = await self.get_DirTypeFSInput(
                new_dir_path
            )

            # There's no path, so there is currently no observer
            assert not hasattr(test_fs_input, "file_system_observer")

            # Create the dir - check for the response - there should be none
            with open(new_dir_path, "w", encoding="utf-8") as test_out_file:
                test_out_file.write(str(uuid.uuid4()))

            try:
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=new_dir_path,
                    event_type=DirCreatedAtWatchLocationFSInputEvent,
                )
            except asyncio.exceptions.TimeoutError:
                pass

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    async def testDirTypeFSInput_monitor_dir_unexpectdaly_nullify_queue(
        self,
    ) -> None:
        """
        Unexpectedly set the input path to be None, and then monitor dir watcher.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            run_task, output_queue, test_fs_input = await self.get_DirTypeFSInput(
                new_dir_path
            )

            # There's no path, so there is currently no observer
            assert not hasattr(test_fs_input, "file_system_observer")

            # Create the dir - check for the response
            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedAtWatchLocationFSInputEvent,
            )

            test_fs_input.file_system_observer._output_queue = None

            os.mkdir(os.path.join(new_dir_path, "bad_output_dir"))

            try:
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=new_dir_path,
                    event_type=DirCreatedAtWatchLocationFSInputEvent,
                )
            except asyncio.exceptions.TimeoutError:
                pass

            try:
                await self.cancel_task(run_task)
            except NotImplementedError:
                pass

    @pytest.mark.asyncio
    async def test_DirTypeFSInput_bad_event_in_output_queue(
        self,
    ) -> None:
        """
        Unexpectedly set the input path to be None, and then monitor dir watcher.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")

            run_task, output_queue, test_fs_input = await self.get_DirTypeFSInput(
                new_dir_path
            )

            # There's no path, so there is currently no observer
            assert not hasattr(test_fs_input, "file_system_observer")

            # Create the dir - check for the response
            os.mkdir(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedAtWatchLocationFSInputEvent,
            )

            await test_fs_input.file_system_observer._internal_queue.put(None)  # type: ignore

            run_task = asyncio.get_running_loop().create_task(
                test_fs_input.file_system_observer._process_event_from_watched_dir(
                    event=None  # type: ignore
                )
            )

            try:
                await self.cancel_task(run_task)
            except NotImplementedError:
                pass

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
    async def testDirTypeFSInput_existing_dir_cre_del_dir_windows(self) -> None:
        """
        Check that we get the expected created signal from a dir created in a monitorbd dir.

        Followed by an attempt to update the file.
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

            shutil.rmtree(new_dir_path)
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=tmp_dir_path,
                event_type=DirUpdatedAtWatchLocationFSInputEvent,
            )
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirDeletedFromWatchLocationFSInputEvent,
            )

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    async def testDirTypeFSInput_existing_dir_create_move_dir_move_by_rename(self) -> None:
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
    async def testDirTypeFSInput_existing_dir_create_move_dir_move_by_shutil_move(
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
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )

            await asyncio.sleep(0.1)

            # Move a file to a different location
            post_move_dir_path = os.path.join(tmp_dir_path, "moved_text_file_delete_me.txt")
            shutil.move(src=new_dir_path, dst=post_move_dir_path)

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
    async def testDirTypeFSInput_existing_dir_create_move_file(self) -> None:
        """
        Create a file in the monitored dir - then move it.
        """

        with tempfile.TemporaryDirectory() as tmp_dir_path:
            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            # - Using blocking methods - this should still work
            new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")
            with open(new_dir_path, "w", encoding="utf-8") as out_file:
                out_file.write("test stuff")

            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=FileCreatedWithinWatchedDirFSInputEvent,
            )

            await asyncio.sleep(1)

            # Move a file to a different location
            post_move_dir_path = os.path.join(tmp_dir_path, "moved_text_file_delete_me.txt")
            shutil.move(src=new_dir_path, dst=post_move_dir_path)

            await asyncio.sleep(5)

            # We may be getting a transitory file updated event
            if output_queue.qsize() == 3:
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=tmp_dir_path,
                    event_type=DirUpdatedAtWatchLocationFSInputEvent,
                    allowed_queue_size=2,
                )

                # This is an asymmetry between how files and folders handle delete
                # left in while I try and think how to deal sanely with it
                # await self.process_dir_deletion_response(output_queue, dir_path=new_dir_path)
                # DirUpdatedAtWatchLocationFSInputEvent
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=new_dir_path,
                    event_type=FileUpdatedWithinWatchedDirFSInputEvent,
                    allowed_queue_size=1,
                )
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=post_move_dir_path,
                    event_type=FileMovedWithinWatchedDirFSInputEvent,
                    allowed_queue_size=0,
                )

            elif output_queue.qsize() == 2:
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=tmp_dir_path,
                    event_type=DirUpdatedAtWatchLocationFSInputEvent,
                    allowed_queue_size=2,
                )

                # This is an asymmetry between how files and folders handle delete
                # left in while I try and think how to deal sanely with it
                # await self.process_dir_deletion_response(output_queue, dir_path=new_dir_path)
                # DirUpdatedAtWatchLocationFSInputEvent
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=tmp_dir_path,
                    event_type=DirUpdatedAtWatchLocationFSInputEvent,
                    allowed_queue_size=1,
                )
                await self.process_dir_event_queue_response(
                    output_queue=output_queue,
                    dir_path=tmp_dir_path,
                    event_type=FileMovedWithinWatchedDirFSInputEvent,
                    allowed_queue_size=0,
                )

            else:
                raise NotImplementedError(f"{output_queue.qsize() = } not expected.")

            await self.cancel_task(run_task)

    @pytest.mark.asyncio
    async def testDirTypeFSInput_existing_dir_create_move_dir_loop(self) -> None:
        """
        Create a directory in a monitored dir, then move it in a loop.

        The loop behavior - especially a rapid loop - seems to confuse windows.
        """
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            new_subfolder_path = os.path.join(tmp_dir_path, "subfolder_1", "subfolder_2")
            os.makedirs(new_subfolder_path)

            run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)

            for i in range(10):
                # - Using blocking methods - this should still work
                new_dir_path = os.path.join(new_subfolder_path, "text_file_delete_me.txt")

                await self.make_dir_at_path(new_dir_path, output_queue, new_subfolder_path)

                # Move a dir to a different location
                post_move_dir_path = os.path.join(
                    new_subfolder_path, "moved_text_file_delete_me.txt"
                )
                os.rename(src=new_dir_path, dst=post_move_dir_path)
                await asyncio.sleep(2.0)

                # I think this is a Windows problem - probably.
                if output_queue.qsize() == 1 and i == 0:
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirUpdatedWithinWatchedDirFSInputEvent,
                    )
                elif output_queue.qsize() == 1:
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirMovedWithinWatchedDirFSInputEvent,
                    )
                elif output_queue.qsize() == 2:
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirMovedWithinWatchedDirFSInputEvent,
                    )

                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirUpdatedWithinWatchedDirFSInputEvent,
                    )

                elif output_queue.qsize() == 3:
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirUpdatedWithinWatchedDirFSInputEvent,
                        allowed_queue_size=2,
                    )

                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirMovedWithinWatchedDirFSInputEvent,
                    )

                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirUpdatedWithinWatchedDirFSInputEvent,
                    )

                else:
                    raise NotImplementedError(f"{output_queue.qsize() = } was not expected.")

                # Delete the moved file

                shutil.rmtree(post_move_dir_path)
                await asyncio.sleep(1.0)

                if output_queue.qsize() == 2:
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=tmp_dir_path,
                        event_type=DirUpdatedWithinWatchedDirFSInputEvent,
                    )
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=post_move_dir_path,
                        event_type=DirDeletedFromWatchedDirFSInputEvent,
                    )

                elif output_queue.qsize() == 3:
                    # Sometimes the target file sees an update before delete
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=post_move_dir_path,
                        event_type=DirUpdatedWithinWatchedDirFSInputEvent,
                    )
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=post_move_dir_path,
                        event_type=DirDeletedFromWatchedDirFSInputEvent,
                    )
                    await self.process_dir_event_queue_response(
                        output_queue=output_queue,
                        dir_path=new_subfolder_path,
                        event_type=DirUpdatedWithinWatchedDirFSInputEvent,
                    )

                else:
                    raise NotImplementedError(
                        f"{output_queue.qsize() = } was not expected here."
                    )

            await self.cancel_task(run_task)

    async def make_dir_at_path(
        self, new_dir_path: str, output_queue: Any, new_subfolder_path: Any
    ) -> None:
        """
        Construct and validate the resulting events of a dir at the given path.

        :param new_dir_path:
        :return:
        """
        os.mkdir(new_dir_path)
        await asyncio.sleep(0.1)

        if output_queue.qsize() == 1:
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )
        else:
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_dir_path,
                event_type=DirCreatedWithinWatchedDirFSInputEvent,
            )
            await self.process_dir_event_queue_response(
                output_queue=output_queue,
                dir_path=new_subfolder_path,
                event_type=DirUpdatedWithinWatchedDirFSInputEvent,
            )

    # async def move_file_to_new_loc
