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
# import os
# import sys
# import tempfile
#
# import pytest
#
# from mewbot.io.file_system_monitor import DirTypeFSInput
# from mewbot.io.file_system_monitor.fs_events import (
#     DirUpdatedAtWatchLocationFSInputEvent,
#     FileCreatedWithinWatchedDirFSInputEvent,
#     FileDeletedWithinWatchedDirFSInputEvent,
#     FileUpdatedWithinWatchedDirFSInputEvent,
# )
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
#
# class TestDirTypeFSInputInitAndProperties(
#     FileSystemTestUtilsDirEvents, FileSystemTestUtilsFileEvents
# ):
#     """
#     Tests the DirTypeFSInput input type.
#     """
#
#     # - INIT AND ATTRIBUTES
#
#     @pytest.mark.asyncio
#     async def test_DirTypeFSInput__init__input_path_None(self) -> None:
#         """
#         Tests we can init DirTypeFSInput - input_path is set to None.
#         """
#         test_fs_input = DirTypeFSInput(input_path=None)
#         assert isinstance(test_fs_input, DirTypeFSInput)
#
#     @pytest.mark.asyncio
#     async def test_DirTypeFSInput__init__input_path_nonsense(self) -> None:
#         """
#         Tests that we can start an isolated copy of FileTypeFSInput - for testing purposes.
#         """
#         input_path_str = "\\///blargleblarge_not_a_path"
#         test_fs_input = DirTypeFSInput(input_path=input_path_str)
#
#         assert test_fs_input.input_path_exists is False
#
#         # Test attributes which should have been set
#         assert test_fs_input.input_path == input_path_str
#         test_fs_input.input_path = "//\\another thing which does not exist"
#
#         try:
#             test_fs_input.input_path_exists = True
#         except AttributeError:
#             pass
#
#         assert test_fs_input.input_path_exists is False
#
#     @pytest.mark.asyncio
#     async def test_DirTypeFSInput__init__input_path_existing_dir(self) -> None:
#         """
#         Tests that we can start an isolated copy of FileTypeFSInput - for testing purposes.
#
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             test_fs_input = DirTypeFSInput(input_path=tmp_dir_path)
#
#             assert test_fs_input.input_path == tmp_dir_path
#             assert test_fs_input.input_path_exists is True
#
#             assert isinstance(test_fs_input, DirTypeFSInput)
#
#     # - RUNNING TO DETECT CHANGES TO MONITORED DIR
#
#     @pytest.mark.asyncio
#     async def testDirTypeFSInput_existing_dir_create_file(self) -> None:
#         """
#         Create a file inside an existing dir - check this is properly registered.
#
#         Check for the expected created signal from a file which is created in a monitored dir.
#         File is just being created inside the test dir.
#         Which already exists when the test is run.
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)
#
#             # - Using blocking methods - this should still work
#             new_file_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")
#
#             with open(new_file_path, "w", encoding="utf-16") as output_file:
#                 output_file.write("Here we go")
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=new_file_path,
#                 event_type=FileCreatedWithinWatchedDirFSInputEvent,
#             )
#
#             await self.cancel_task(run_task)
#
#     @pytest.mark.asyncio
#     @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
#     async def test_DirTypeFSInput_existing_dir_cre_upd_del_file_linux(self) -> None:
#         """
#         Create, update, then delete a file.
#
#         Linux only test - to isolate some unhelpful inotify behavior.
#         Check for the expected created signal from a file which is created in a monitored dir.
#         Followed by an attempt to update the file.
#         Followed by deleting that file.
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             run_task, output_queue, _ = await self.get_DirTypeFSInput(tmp_dir_path)
#
#             # - Using blocking methods - this should still work
#             new_dir_path = os.path.join(tmp_dir_path, "text_file_delete_me.txt")
#
#             with open(new_dir_path, "w", encoding="utf-16") as output_file:
#                 output_file.write("Here we go")
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=new_dir_path,
#                 event_type=FileCreatedWithinWatchedDirFSInputEvent,
#             )
#
#             with open(new_dir_path, "a", encoding="utf-16") as output_file:
#                 output_file.write("Here we go again")
#             await self.process_dir_event_queue_response(
#                 output_queue=output_queue,
#                 dir_path=tmp_dir_path,
#                 allowed_queue_size=1,
#                 event_type=DirUpdatedAtWatchLocationFSInputEvent,
#             )
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=new_dir_path,
#                 event_type=FileUpdatedWithinWatchedDirFSInputEvent,
#             )
#
#             os.unlink(new_dir_path)
#             await self.process_dir_event_queue_response(
#                 output_queue=output_queue,
#                 dir_path=tmp_dir_path,
#                 allowed_queue_size=1,
#                 event_type=DirUpdatedAtWatchLocationFSInputEvent,
#             )
#
#             # Probably do not want
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=new_dir_path,
#                 event_type=FileUpdatedWithinWatchedDirFSInputEvent,
#             )
#             await self.process_dir_event_queue_response(
#                 output_queue=output_queue,
#                 dir_path=tmp_dir_path,
#                 allowed_queue_size=1,
#                 event_type=FileUpdatedWithinWatchedDirFSInputEvent,
#             )
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=new_dir_path,
#                 event_type=FileDeletedWithinWatchedDirFSInputEvent,
#             )
#
#             await self.cancel_task(run_task)
