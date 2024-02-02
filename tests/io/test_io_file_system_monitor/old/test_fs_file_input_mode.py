#     @pytest.mark.asyncio
#     @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only test")
#     async def test_FileTypeFSInput_create_update_delete_target_file_loop_windows(
#         self,
#     ) -> None:
#         """
#         Create, update, then delete a file in a loop.
#
#         Designed to detected if we're getting stale events for a ghost file.
#         1 - Start without a file at all.
#         2 - Starting the input
#         3 - Create a file - check for the file creation event
#         3 - Append to that file - check this produces the expected event
#         4 - Delete the file - looking for the event
#         4 - Do it a few times - check the results continue to be produced
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             input_path = os.path.join(tmp_dir_path, "test_file_delete_me.txt")
#
#             run_task, output_queue = await self.get_FileTypeFSInput(input_path)
#
#             for i in range(10):
#                 await self.create_overwrite_update_unlink_file(
#                     input_path=input_path, output_queue=output_queue, i=str(i)
#                 )
#
#                 await self.process_file_event_queue_response(
#                     output_queue=output_queue,
#                     file_path=input_path,
#                     event_type=FileDeletedFromWatchLocationFSInputEvent,
#                 )
#
#             await self.cancel_task(run_task)
#
#     async def create_overwrite_update_unlink_file(
#         self, input_path: str, output_queue: asyncio.Queue[InputEvent], i: str = "Not in loop"
#     ) -> None:
#         """
#         Create a file - then update, modify and finally delete it.
#
#         :param input_path:
#         :param output_queue:
#         :param i:
#         :return:
#         """
#
#         with open(input_path, "w", encoding="utf-8") as test_outfile:
#             test_outfile.write(
#                 f"\nThe testing will continue until moral improves - probably!- time {i}"
#             )
#         await self.process_file_event_queue_response(
#             output_queue=output_queue,
#             file_path=input_path,
#             event_type=FileCreatedAtWatchLocationFSInputEvent,
#         )
#
#         with open(input_path, "w", encoding="utf-8") as test_outfile:
#             test_outfile.write(
#                 f"\nThe testing will continue until moral improves - again! - time {i}"
#             )
#
#         await self.process_file_event_queue_response(
#             output_queue=output_queue,
#             event_type=FileUpdatedAtWatchLocationFSInputEvent,
#             file_path=input_path,
#         )
#
#         with open(input_path, "a", encoding="utf-8") as test_outfile:
#             test_outfile.write(
#                 f"\nThe testing will continue until moral improves - really! - time {i}"
#             )
#
#         await self.process_file_event_queue_response(
#             output_queue=output_queue,
#             event_type=FileUpdatedAtWatchLocationFSInputEvent,
#             file_path=input_path,
#         )
#         os.unlink(input_path)
#
#     @pytest.mark.asyncio
#     @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
#     async def test_FileTypeFSInput_create_update_delete_target_file_loop_linux(self) -> None:
#         """
#         Linux version of running the create-update-delete loop.
#
#         (diagnostic check - that this fails on linux or not).
#         1 - Start without a file at all.
#         2 - Starting the input
#         3 - Create a file - check for the file creation event
#         3 - Append to that file - check this produces the expected event
#         4 - Delete the file - looking for the event
#         4 - Do it a few times - check the results continue to be produced
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             input_path = os.path.join(tmp_dir_path, "test_file_delete_me.txt")
#
#             run_task, output_queue = await self.get_FileTypeFSInput(input_path)
#
#             for _ in range(10):
#                 await self.create_overwrite_update_unlink_file(input_path, output_queue)
#
#                 await asyncio.sleep(0.5)
#
#                 queue_length = output_queue.qsize()
#
#                 if queue_length == 2:
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         event_type=FileUpdatedAtWatchLocationFSInputEvent,
#                         file_path=input_path,
#                         allowed_queue_size=1,
#                     )
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         event_type=FileDeletedFromWatchLocationFSInputEvent,
#                         file_path=input_path,
#                     )
#                 elif queue_length == 1:
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         event_type=FileDeletedFromWatchLocationFSInputEvent,
#                         file_path=input_path,
#                     )
#                 else:
#                     raise NotImplementedError(f"unexpected queue length - {queue_length}")
#
#             await self.cancel_task(run_task)
#
#     async def create_update_input_file(
#         self, file_path: str, output_queue: asyncio.Queue[InputEvent]
#     ) -> None:
#         """
#         Create an input file and then update it.
#
#         :param file_path:
#         :param output_queue:
#         :return:
#         """
#
#         with open(file_path, "w", encoding="utf-8") as test_outfile:
#             test_outfile.write("We are testing mewbot!")
#
#         await self.process_file_event_queue_response(
#             output_queue=output_queue,
#             file_path=file_path,
#             event_type=FileCreatedAtWatchLocationFSInputEvent,
#         )
#
#         with open(file_path, "w", encoding="utf-8") as test_outfile:
#             test_outfile.write(
#                 f"\nThe testing will continue until moral improves! {str(uuid.uuid4())}"
#             )
#
#         await self.process_file_event_queue_response(
#             output_queue=output_queue,
#             file_path=file_path,
#             event_type=FileUpdatedAtWatchLocationFSInputEvent,
#         )
#
#     @pytest.mark.asyncio
#     @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only test")
#     async def test_FileTypeFSInput_existing_file_io_in_non_existing_file_windows(
#         self,
#     ) -> None:
#         """
#         Start file type input on a non-existent file - then create it.
#
#         1 - Start without a file at all.
#         2 - Starting the input
#         3 - Create a file - check for the file creation event
#         3 - Append to that file - check this produces the expected event
#         4 - Delete the file - looking for the event
#         4 - Do it a few times - check the results continue to be produced
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             # io will be done on this file
#             tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")
#
#             run_task, output_queue = await self.get_FileTypeFSInput(tmp_file_path)
#
#             # Give the class a chance to actually do init
#             await asyncio.sleep(0.5)
#
#             await self.create_update_input_file(
#                 file_path=tmp_file_path, output_queue=output_queue
#             )
#
#             # Otherwise the queue seems to be blocking pytest from a clean exit.
#             await self.cancel_task(run_task)
#
#             # Tests are NOW making a clean exist after this test
#             # This seems to have been a problem with the presence of a queue
#
#     async def update_delete_file_loop(
#         self, tmp_file_path: str, output_queue: asyncio.Queue[InputEvent]
#     ) -> None:
#         """
#         Update a file, delete it, then recreate it in a loop.
#
#         Five iterations.
#         Intended to catch transitory file events when a file is repeatedly deleted and recreated.
#         :param tmp_file_path:
#         :param output_queue:
#         :return:
#         """
#
#         for i in range(5):
#             # Generate some events which should end up in the queue
#             # - Using blocking methods - this should still work
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write(
#                     f"\nThe testing will continue until moral improves! "
#                     f"But my moral is already so high - time {i}"
#                 )
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=tmp_file_path,
#                 event_type=FileUpdatedAtWatchLocationFSInputEvent,
#             )
#
#             # Delete the file - then recreate it
#             os.unlink(tmp_file_path)
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=tmp_file_path,
#                 event_type=FileDeletedFromWatchLocationFSInputEvent,
#             )
#
#             # Generate some events which should end up in the queue
#             # - Using blocking methods - this should still work
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write(
#                     "\nThe testing will continue until moral improves! Please... no...."
#                 )
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=tmp_file_path,
#                 event_type=FileCreatedAtWatchLocationFSInputEvent,
#             )
#
#     @pytest.mark.asyncio
#     @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
#     async def test_FileTypeFSInput_existing_file_io_in_non_existing_file_linux(self) -> None:
#         """
#         Start without  file, create it, append to it and loop - looking for ghost events.
#
#         1 - Start without a file at all.
#         2 - Starting the input
#         3 - Create a file - check for the file creation event
#         3 - Append to that file - check this produces the expected event
#         4 - Delete the file - looking for the event
#         4 - Do it a few times - check the results continue to be produced
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             # io will be done on this file
#             tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")
#
#             test_fs_input = FileTypeFSInput(input_path=tmp_file_path)
#             assert isinstance(test_fs_input, FileTypeFSInput)
#
#             output_queue: asyncio.Queue[InputEvent] = asyncio.Queue()
#             test_fs_input.queue = output_queue
#
#             # We need to retain control of the thread to delay shutdown
#             # And to probe the results
#             run_task = asyncio.get_running_loop().create_task(test_fs_input.run())
#
#             # Give the class a chance to actually do init
#             await asyncio.sleep(0.5)
#
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write("We are testing mewbot!")
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=tmp_file_path,
#                 event_type=FileCreatedAtWatchLocationFSInputEvent,
#             )
#
#             # Generate some events which should end up in the queue
#             # - Using blocking methods - this should still work
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write(
#                     "\nThe testing will continue until moral improves!"
#                     " - With Professioalism! A word we CANNOT spell."
#                 )
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=tmp_file_path,
#                 event_type=FileUpdatedAtWatchLocationFSInputEvent,
#             )
#
#             for i in range(5):
#                 # Generate some events which should end up in the queue
#                 # - Using blocking methods - this should still work
#                 with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                     test_outfile.write(
#                         f"\nThe testing will continue until moral improves! "
#                         f"{str(uuid.uuid4())}- time {i}"
#                     )
#
#                 await self.process_file_event_queue_response(
#                     output_queue=output_queue,
#                     file_path=tmp_file_path,
#                     event_type=FileUpdatedAtWatchLocationFSInputEvent,
#                 )
#
#                 # Delete the file - then recreate it
#                 os.unlink(tmp_file_path)
#
#                 await asyncio.sleep(0.5)
#
#                 queue_length = output_queue.qsize()
#
#                 if queue_length == 2:
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         file_path=tmp_file_path,
#                         allowed_queue_size=1,
#                         event_type=FileUpdatedAtWatchLocationFSInputEvent,
#                     )
#
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         file_path=tmp_file_path,
#                         event_type=FileDeletedFromWatchLocationFSInputEvent,
#                     )
#
#                 elif queue_length == 1:
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         file_path=tmp_file_path,
#                         event_type=FileDeletedFromWatchLocationFSInputEvent,
#                     )
#
#                 else:
#                     raise NotImplementedError(f"Unexpected queue length - {queue_length}")
#
#                 # Generate some events which should end up in the queue
#                 # - Using blocking methods - this should still work
#                 with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                     test_outfile.write(
#                         "\nThe testing will continue until moral improves!"
#                         " If this does not improve your moral ... that's fair, tbh."
#                     )
#
#                 await self.process_file_event_queue_response(
#                     output_queue=output_queue,
#                     event_type=FileCreatedAtWatchLocationFSInputEvent,
#                     file_path=tmp_file_path,
#                 )
#
#             # Otherwise the queue seems to be blocking pytest from a clean exit.
#             await self.cancel_task(run_task)
#
#             # Tests are NOW making a clean exist after this test
#             # This seems to have been a problem with the presence of a queue
#
#     @pytest.mark.asyncio
#     @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only test")
#     async def test_FileTypeFSInput_existing_dir_deleted_and_replaced_with_file_windows(
#         self,
#     ) -> None:
#         """
#         Start with no file - create - delete - create again, mod that file, del it, loop.
#
#         The aim of this class of tests is to make sure that we are normalising the raw events
#         properly.
#         Windows has a nasty habit of producing a number of gibberish events.
#         Including, but not limited to
#          - files updated after they're gone
#          - files created, then deleted again
#         we've had to apply some smoothing to produce sensible results.
#         These tests check that smoothing.
#
#         1 - Start without a file at all.
#         2 - Starting the input
#         3 - create a dir at the monitored location - this should do nothing
#         4 - delete that dir
#         5 - Create a file - check for the file creation event
#         6 - Append to that file - check this produces the expected event
#         7 - Delete the file - looking for the event
#         8 - Do it a few times - check the results continue to be produced
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             # io will be done on this file
#             tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")
#
#             run_task, output_queue = await self.get_FileTypeFSInput(tmp_file_path)
#
#             # Give the class a chance to actually do init
#             await asyncio.sleep(0.5)
#
#             # Make a dir - the class should not respond
#             os.mkdir(tmp_file_path)
#
#             await asyncio.sleep(0.5)
#
#             await self.verify_queue_size(output_queue, task_done=False)
#
#             # Delete the file - the class should also not respond
#             os.rmdir(tmp_file_path)
#
#             await asyncio.sleep(0.5)
#
#             await self.verify_queue_size(output_queue, task_done=False)
#
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write(f"We are testing mewbot! {str(uuid.uuid4())}")
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 file_path=tmp_file_path,
#                 event_type=FileCreatedAtWatchLocationFSInputEvent,
#             )
#
#             assert output_queue.qsize() == 0
#
#             # Generate some events which should end up in the queue
#             # - Using blocking methods - this should still work
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write(
#                     f"\nThe testing will continue until moral improves! {str(uuid.uuid4())}"
#                 )
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue, event_type=FileUpdatedAtWatchLocationFSInputEvent
#             )
#
#             await self.update_delete_file_loop(
#                 tmp_file_path=tmp_file_path, output_queue=output_queue
#             )
#
#             # Otherwise the queue seems to be blocking pytest from a clean exit.
#             await self.cancel_task(run_task)
#
#             # Tests are NOW making a clean exist after this test
#             # This seems to have been a problem with the presence of a queue
#
#     @pytest.mark.asyncio
#     @pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux (like) only test")
#     async def test_FileTypeFSInput_existing_dir_deleted_and_replaced_with_file_linux(
#         self,
#     ) -> None:
#         """
#         Create and delete a file at a location in a loop.
#
#         1 - Start without a file at all.
#         2 - Starting the input
#         3 - create a dir at the monitored location - this should do nothing
#         4 - delete that dir
#         5 - Create a file - check for the file creation event
#         6 - Append to that file - check this produces the expected event
#         7 - Delete the file - looking for the event
#         8 - Do it a few times - check the results continue to be produced
#         """
#         with tempfile.TemporaryDirectory() as tmp_dir_path:
#             # io will be done on this file
#             tmp_file_path = os.path.join(tmp_dir_path, "mewbot_test_file.test")
#
#             run_task, output_queue = await self.get_FileTypeFSInput(tmp_file_path)
#
#             # Give the class a chance to actually do init
#             await asyncio.sleep(0.5)
#
#             # Make a dir - the class should not respond
#             os.mkdir(tmp_file_path)
#
#             await asyncio.sleep(0.5)
#
#             await self.verify_queue_size(output_queue, task_done=False)
#
#             # Delete the file - the class should also not respond
#             os.rmdir(tmp_file_path)
#
#             await asyncio.sleep(0.5)
#
#             await self.verify_queue_size(output_queue, task_done=False)
#
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write("We are testing mewbot!")
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 event_type=FileCreatedAtWatchLocationFSInputEvent,
#                 file_path=tmp_file_path,
#             )
#
#             # Generate some events which should end up in the queue
#             # - Using blocking methods - this should still work
#             with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                 test_outfile.write("\nThe testing will continue until moral improves!")
#
#             await self.process_file_event_queue_response(
#                 output_queue=output_queue,
#                 event_type=FileUpdatedAtWatchLocationFSInputEvent,
#                 file_path=tmp_file_path,
#             )
#
#             for i in range(5):
#                 # Generate some events which should end up in the queue
#                 # - Using blocking methods - this should still work
#                 with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                     test_outfile.write(
#                         f"\nThe testing will continue until moral improves! - time {i}"
#                     )
#                 await self.process_file_event_queue_response(
#                     output_queue=output_queue,
#                     event_type=FileUpdatedAtWatchLocationFSInputEvent,
#                     file_path=tmp_file_path,
#                 )
#
#                 # Delete the file - then recreate it
#                 os.unlink(tmp_file_path)
#
#                 await asyncio.sleep(0.5)
#
#                 queue_length = output_queue.qsize()
#
#                 if queue_length == 2:
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         file_path=tmp_file_path,
#                         allowed_queue_size=1,
#                         event_type=FileUpdatedAtWatchLocationFSInputEvent,
#                     )
#
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         file_path=tmp_file_path,
#                         event_type=FileDeletedFromWatchLocationFSInputEvent,
#                     )
#
#                 elif queue_length == 1:
#                     await self.process_file_event_queue_response(
#                         output_queue=output_queue,
#                         file_path=tmp_file_path,
#                         event_type=FileDeletedFromWatchLocationFSInputEvent,
#                     )
#
#                 else:
#                     raise NotImplementedError(f"Unexpected queue_length - {queue_length}")
#
#                 # Generate some events which should end up in the queue
#                 # - Using blocking methods - this should still work
#                 with open(tmp_file_path, "w", encoding="utf-8") as test_outfile:
#                     test_outfile.write("\nThe testing will continue until moral improves!")
#
#                 await self.process_file_event_queue_response(
#                     output_queue=output_queue,
#                     event_type=FileCreatedAtWatchLocationFSInputEvent,
#                 )
#
#             # Otherwise the queue seems to be blocking pytest from a clean exit.
#             await self.cancel_task(run_task)
#
#             # Tests are NOW making a clean exist after this test
#             # This seems to have been a problem with the presence of a queue
#
#     # @pytest.mark.asyncio
#     # async def test_FileTypeFSInput_create_update_delete_target_file_dir_overwrite(
#     #     self,
#     # ) -> None:
#     #     """
#     #     Tests creating, updating, deleting and overwriting a file in a loop.
#     #
#     #     1 - Start without a file at all.
#     #     2 - Starting the input
#     #     3 - Create a file - check for the file creation event
#     #     3 - Append to that file - check this produces the expected event
#     #     4 - Overwrite the file with a dir - this should crash the observer
#     #         But it should be caught and an appopriate event generated
#     #     """
#     #     with tempfile.TemporaryDirectory() as tmp_dir_path:
#     #
#     #         input_path = os.path.join(tmp_dir_path, "test_file_delete_me.txt")
#     #
#     #         run_task, output_queue = await self.get_FileTypeFSInput(input_path)
#     #
#     #         for i in range(10):
#     #
#     #             with open(input_path, "w", encoding="utf-8") as test_outfile:
#     #                 test_outfile.write(
#     #                     f"\nThe testing will continue until moral improves! - time {i}"
#     #                 )
#     #             await self.process_input_file_creation_response(output_queue)
#     #
#     #             with open(input_path, "w", encoding="utf-8") as test_outfile:
#     #                 test_outfile.write(
#     #                     f"\nThe testing will continue until moral improves! - time {i}"
#     #                 )
#     #
#     #             await self.process_file_update_response(output_queue)
#     #
#     #             with open(input_path, "a", encoding="utf-8") as test_outfile:
#     #                 test_outfile.write(
#     #                     f"\nThe testing will continue until moral improves! - time {i}"
#     #                 )
#     #
#     #             await self.process_file_update_response(output_queue)
#     #
#     #             test_dir_path = os.path.join(tmp_dir_path, "test_dir_del_me")
#     #             os.mkdir(test_dir_path)
#     #
#     #             # Attempt to copy a dir over the top of the input file
#     #             # this should fail with no effect.
#     #             try:
#     #                 shutil.copytree(test_dir_path, input_path)
#     #             except FileExistsError:
#     #                 pass
#     #
#     #             shutil.rmtree(test_dir_path)
#     #             os.unlink(input_path)
#     #
#     #             await self.process_input_file_deletion_response(output_queue)
#     #
#     #             # Make a folder at the monitored path - this should produce no result
#     #             os.mkdir(input_path)
#     #
#     #             shutil.rmtree(input_path)
#     #
#     #         await self.cancel_task(run_task)
