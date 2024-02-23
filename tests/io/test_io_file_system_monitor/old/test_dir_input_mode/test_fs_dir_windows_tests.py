# # SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
# #
# # SPDX-License-Identifier: BSD-2-Clause
#
# # Aim is to run, in sections, as many of the input methods as possible
# # Including running a full bot with logging triggers and actions.
# # However, individual components also have to be isolated for testing purposes.
#
# """
# Tests the dir input - monitors a directory for changes.
# """
#
#
# import asyncio
# import ctypes
# import os
# import sys
# import tempfile
#
# import pytest
#
# from tests.io.test_io_file_system_monitor.fs_test_utils import (
#     FileSystemTestUtilsDirEvents,
#     FileSystemTestUtilsFileEvents,
# )
#
# # pylint: disable=invalid-name
# # for clarity, test functions should be named after the things they test
# # which means CamelCase in function names
#
# # pylint: disable=duplicate-code
# # Due to testing for the subtle differences between how the monitors respond in windows and
# # linux, code has - inevitably - ended up very similar.
# # As such, this inspection has had to be disabled.
#
# # pylint: disable=protected-access
# # Need to access the internals of the classes to put them into pathological states.
#
#
# class TestDirTypeFSInputWindowsTests(
#     FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents
# ):
#     """
#     Tests the DirTypeFSInput input type.
#     """
#
#     # - RUNNING TO DETECT DIR CHANGES
#
#     # @pytest.mark.asyncio
#     # @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
#     # async def testDirTypeFSInput_existing_dir_cre_del_dir_loop_linux(self) -> None:
#     #     """
#     #     Checks we get the expected created signal from a file which is created in a monitored dir
#     #     Followed by an attempt to update the file.
#     #     Then an attempt to delete the file.
#     #     This is done in a loop - to check for any problems with stale events
#     #     """
#     #     with tempfile.TemporaryDirectory() as tmp_dir_path:
#     #         run_task, output_queue = await self.get_DirTypeFSInput(tmp_dir_path)
#     #
#     #         for i in range(10):
#     #             # - Using blocking methods - this should still work
#     #             new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me_txt")
#     #
#     #             os.mkdir(new_dir_path)
#     #             if i == 0:
#     #                 await self.process_dir_event_queue_response(
#     #                     output_queue=output_queue,
#     #                     dir_path=new_dir_path,
#     #                     event_type=CreatedDirFSInputEvent,
#     #                 )
#     #
#     #             else:
#     #                 await self.process_dir_event_queue_response(
#     #                     output_queue=output_queue,
#     #                     dir_path=tmp_dir_path,
#     #                     event_type=UpdatedDirFSInputEvent,
#     #                 )
#     #                 await self.process_dir_event_queue_response(
#     #                     output_queue=output_queue,
#     #                     dir_path=new_dir_path,
#     #                     event_type=CreatedDirFSInputEvent,
#     #                 )
#     #
#     #             shutil.rmtree(new_dir_path)
#     #             await self.process_dir_event_queue_response(
#     #                 output_queue=output_queue,
#     #                 dir_path=tmp_dir_path,
#     #                 event_type=UpdatedDirFSInputEvent,
#     #             )
#     #             await self.process_dir_event_queue_response(
#     #                 output_queue=output_queue,
#     #                 dir_path=new_dir_path,
#     #                 event_type=DeletedDirFSInputEvent,
#     #             )
#     #
#     #         await self.cancel_task(run_task)
