# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Utils to simplify the process of testing dir and file monitors.
"""

from typing import Any, List, Optional, Tuple, Type, Union

import asyncio

from mewbot.api.v1 import InputEvent

from mewbot.io.file_system_monitor import DirTypeFSInput, FileTypeFSInput
from mewbot.io.file_system_monitor.fs_events import (
    DirCreatedAtWatchLocationFSInputEvent,
    DirCreatedWithinWatchedDirFSInputEvent,
    DirDeletedFromWatchedDirFSInputEvent,
    DirMovedWithinWatchedDirFSInputEvent,
    DirUpdatedAtWatchLocationFSInputEvent,
    DirUpdatedWithinWatchedDirFSInputEvent,
    FileAtWatchLocInputEvent,
    FileCreatedAtWatchLocationFSInputEvent,
    FileCreatedWithinWatchedDirFSInputEvent,
    FileDeletedFromWatchLocationFSInputEvent,
    FileDeletedWithinWatchedDirFSInputEvent,
    FileMovedWithinWatchedDirFSInputEvent,
    FileUpdatedAtWatchLocationFSInputEvent,
    FileUpdatedWithinWatchedDirFSInputEvent,
)

# pylint: disable=invalid-name, too-many-lines
# for clarity, factory functions should be named after the things they test


class GeneralUtils:
    """
    General utils to assist in testing the folder store monitor IOConfig.
    """

    @staticmethod
    async def _get_worker(
        output_queue: asyncio.Queue[InputEvent], rtn_event: List[InputEvent]
    ) -> None:
        """
        Retrieve an event from the queue and put it on the list.

        Used when multiple events may be produced by a single interaction.
        Sometimes we just need to drain down the entire queue and then examine the output.
        :param output_queue:
        :param rtn_event:
        :return:
        """
        rtn_event.append(await output_queue.get())

    async def timeout_get(
        self, output_queue: asyncio.Queue[InputEvent], timeout: float = 20.0
    ) -> InputEvent:
        """
        Pull from a queue with an included timeout.

        Used when we can't be sure all elements will be added to a queue immediately.
        (Windows file system events seem prone to this - a series of events rather than a single
        one).
        :param output_queue:
        :param timeout:
        :return:
        """

        rtn_event: List[InputEvent] = []
        await asyncio.wait_for(self._get_worker(output_queue, rtn_event), timeout=timeout)
        if len(rtn_event) == 1:
            return rtn_event[0]
        if len(rtn_event) == 0:
            raise asyncio.QueueEmpty
        raise NotImplementedError(f"Unexpected case {rtn_event}")

    @staticmethod
    def dump_queue_to_list(output_queue: asyncio.Queue[InputEvent]) -> List[InputEvent]:
        """
        Take a queue - extract all the entries and return them as a list.
        """
        input_events = []
        while True:
            try:
                input_events.append(output_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        return input_events

    @staticmethod
    async def get_DirTypeFSInput(
        input_path: str,
    ) -> Tuple[asyncio.Task[None], asyncio.Queue[InputEvent], DirTypeFSInput]:
        """
        Get a directory type file system monitor input.

        :param input_path:
        :return:
        """

        test_fs_input = DirTypeFSInput(input_path=input_path)
        assert isinstance(test_fs_input, DirTypeFSInput)

        output_queue: asyncio.Queue[InputEvent] = asyncio.Queue()
        test_fs_input.queue = output_queue

        # We need to retain control of the thread to delay shutdown
        # And to probe the results
        run_task = asyncio.get_running_loop().create_task(test_fs_input.run())

        # Give the class a chance to actually do init
        await asyncio.sleep(0.5)

        return run_task, output_queue, test_fs_input

    @staticmethod
    async def get_FileTypeFSInput(
        input_path: str,
    ) -> Tuple[asyncio.Task[None], asyncio.Queue[InputEvent]]:
        """
        Get a File type FS Input.

        :param input_path:
        :return:
        """

        test_fs_input = FileTypeFSInput(input_path=input_path)
        assert isinstance(test_fs_input, FileTypeFSInput)

        output_queue: asyncio.Queue[InputEvent] = asyncio.Queue()
        test_fs_input.queue = output_queue

        # We need to retain control of the thread to delay shutdown
        # And to probe the results
        run_task = asyncio.get_running_loop().create_task(test_fs_input.run())

        return run_task, output_queue

    @staticmethod
    async def cancel_task(run_task: asyncio.Task[None]) -> None:
        """
        Safely call cancel on the given task - catching the resulting exception.

        :param run_task:
        :return:
        """

        # Otherwise the queue seems to be blocking pytest from a clean exit.
        try:
            run_task.cancel()
            await run_task
        except asyncio.exceptions.CancelledError:
            pass

    @staticmethod
    async def verify_queue_size(
        output_queue: asyncio.Queue[InputEvent],
        task_done: bool = True,
        allowed_queue_size: Union[int, list[int]] = 0,
    ) -> None:
        """
        Check the given queue declares that it has the correct size.

        :param output_queue: The queue to check
        :param task_done: Call `task_done` on the given queue to clear it for shutdown.
        :param allowed_queue_size: Is the queue allowed not to be empty?
        :return:
        """
        if isinstance(allowed_queue_size, int):
            allowed_queue_size = [
                allowed_queue_size,
            ]
        if 0 not in allowed_queue_size:
            allowed_queue_size.append(0)

        # There should be no other events in the queue
        output_queue_qsize = output_queue.qsize()
        if allowed_queue_size:
            # Note - this is somewhat alarming!
            assert output_queue_qsize in allowed_queue_size, (
                f"Output queue actually has {output_queue_qsize} entries "
                f"- the allowed_queue_size should be one of {allowed_queue_size}"
            )
        else:
            assert output_queue_qsize == 0, (
                f"Output queue actually has {output_queue_qsize} entries "
                f"- None are allowed"
            )

        # Indicate to the queue that task processing is complete
        if task_done:
            output_queue.task_done()


class FileSystemTestUtilsFileEvents(GeneralUtils):
    """
    Base class for tests to file monitors in particular.
    """

    async def process_file_event_queue_response(  # pylint: disable=too-many-arguments
        self,
        output_queue: asyncio.Queue[InputEvent],
        event_type: Any,
        file_path: Optional[str] = None,
        allowed_queue_size: Union[int, list[int]] = 0,
        message: Optional[str] = None,
    ) -> None:
        """
        Get the next event off the queue.

        Check that it's one for a file being created with expected file path.
        """

        # This should have generated an event
        try:
            queue_out = await self.timeout_get(output_queue)
        except Exception as exp:
            raise AssertionError(message) from exp

        self.validate_file_input_event(
            input_event=queue_out, event_type=event_type, file_path=file_path, message=message
        )

        await self.verify_queue_size(output_queue, allowed_queue_size=allowed_queue_size)

    def check_queue_for_file_input_event(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        event_type: Type[FileAtWatchLocInputEvent],
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check that there is an event of the given type somewhere in the queue.

        :param output_queue:
        :param event_type:
        :param file_path:
        :param message:
        :return:
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, event_type):
                self.validate_file_input_event(
                    input_event=event,
                    event_type=event_type,
                    file_path=file_path,
                    message=message,
                )
                return

        raise AssertionError(
            f"CreatedFileFSInputEvent not found in input_events - {input_events}"
        )

    @staticmethod
    def validate_file_input_event(
        input_event: InputEvent,
        event_type: Union[
            Type[FileAtWatchLocInputEvent],
            Type[FileCreatedAtWatchLocationFSInputEvent],
            Type[FileDeletedFromWatchLocationFSInputEvent],
            type[FileDeletedWithinWatchedDirFSInputEvent],
        ],
        file_path: Optional[str] = None,
        message: Optional[str] = "",
    ) -> None:
        """
        Check that the given input event is of the expected type.

        :param input_event:
        :param event_type:
        :param file_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, event_type
        ), f"Expected event of type {event_type.__name__} - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if file_path is not None:
            assert isinstance(
                input_event,
                event_type,
            )
            input_event_path = getattr(input_event, "path")

            assert (
                input_event_path == file_path
            ), f"Expected {input_event_path}, got {file_path}"

    def check_queue_for_file_creation_input_event_within_watch_loc(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a CreatedFileFSInputEvent in it.

        :param output_queue:
        :param file_path:
        :param message:
        :return:
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, FileCreatedWithinWatchedDirFSInputEvent):
                self.validate_file_creation_within_watch_loc_input_event(
                    input_event=event, file_path=file_path, message=message
                )
                return

        raise AssertionError(
            f"CreatedFileFSInputEvent not found in input_events - {input_events}"
        )

    def check_queue_for_file_creation_input_event_at_watch_loc(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a CreatedFileFSInputEvent in it.

        :param output_queue:
        :param file_path:
        :param message:
        :return:
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, FileCreatedAtWatchLocationFSInputEvent):
                self.validate_file_creation_at_watch_loc_input_event(
                    input_event=event, file_path=file_path, message=message
                )
                return

        raise AssertionError(
            f"CreatedFileFSInputEvent not found in input_events - {input_events}"
        )

    @staticmethod
    def validate_file_creation_at_watch_loc_input_event(
        input_event: InputEvent,
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the file creation event is correct.

        :param input_event:
        :param file_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, FileCreatedAtWatchLocationFSInputEvent
        ), f"Expected CreatedFileFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if file_path is not None:
            assert input_event.path == file_path

    @staticmethod
    def validate_file_creation_within_watch_loc_input_event(
        input_event: InputEvent,
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the file creation event is correct.

        :param input_event:
        :param file_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, FileCreatedWithinWatchedDirFSInputEvent
        ), f"Expected CreatedFileFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if file_path is not None:
            assert input_event.path == file_path

    def check_queue_for_file_update_input_event_at_watch_loc(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a FileCreatedAtWatchLocationFSInputEvent in it.

        Sometimes this is the best we can do - check to see if there is a creation event
        _somewhere_.
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, FileUpdatedAtWatchLocationFSInputEvent):
                self.validate_file_update_input_event_at_watch_loc(
                    input_event=event, file_path=file_path, message=message
                )
                return

        raise AssertionError(
            f"UpdatedFileFSInputEvent not found in input_events - {input_events}"
        )

    def check_queue_for_file_update_input_event_within_watch_loc(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a FileCreatedAtWatchLocationFSInputEvent in it.

        Sometimes this is the best we can do - check to see if there is a creation event
        _somewhere_.
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, FileUpdatedWithinWatchedDirFSInputEvent):
                self.validate_file_update_input_event_within_watch_loc(
                    input_event=event, file_path=file_path, message=message
                )
                return

        raise AssertionError(
            f"UpdatedFileFSInputEvent not found in input_events - {input_events}"
        )

    @staticmethod
    def validate_file_update_input_event_within_watch_loc(
        input_event: InputEvent,
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check that a file update event has been produced with the expected path.

        :param input_event: Input event to check
        :param file_path: Path at which the update should be registered.
        :param message: Message to be included with the error - if there is one.
        :return:
        """
        assert isinstance(
            input_event, FileUpdatedWithinWatchedDirFSInputEvent
        ), f"Expected UpdatedFileFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if file_path is not None:
            assert file_path == input_event.path

    @staticmethod
    def validate_file_update_input_event_at_watch_loc(
        input_event: InputEvent,
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check that a file update event has been produced with the expected path.

        :param input_event: Input event to check
        :param file_path: Path at which the update should be registered.
        :param message: Message to be included with the error - if there is one.
        :return:
        """
        assert isinstance(
            input_event, FileUpdatedAtWatchLocationFSInputEvent
        ), f"Expected UpdatedFileFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if file_path is not None:
            assert file_path == input_event.path

    def check_queue_for_file_move_input_event(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        file_src_parth: Optional[str] = None,
        file_dst_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a FileMovedFromWatchLocationFSInputEvent in it.
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, FileMovedWithinWatchedDirFSInputEvent):
                self.validate_file_move_input_event(
                    input_event=event,
                    file_src_parth=file_src_parth,
                    file_dst_path=file_dst_path,
                    message=message,
                )
                return

        raise AssertionError(
            f"UpdatedDirFSInputEvent not found in input_events - {input_events}"
        )

    async def process_file_move_queue_response(
        self,
        output_queue: asyncio.Queue[InputEvent],
        file_src_parth: Optional[str] = None,
        file_dst_path: Optional[str] = None,
        allowed_queue_size: int = 0,
    ) -> None:
        """
        Get the next event off the queue - check that it's one for the input file being deleted.
        """
        # This should have generated an event
        queue_out = await self.timeout_get(output_queue)
        self.validate_file_move_input_event(
            input_event=queue_out,
            file_src_parth=file_src_parth,
            file_dst_path=file_dst_path,
        )

        await self.verify_queue_size(output_queue, allowed_queue_size=allowed_queue_size)

    @staticmethod
    def validate_file_move_input_event(
        input_event: InputEvent,
        file_src_parth: Optional[str] = None,
        file_dst_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Validate that a file move event is being produced.

        :param input_event:
        :param file_src_parth:
        :param file_dst_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, FileMovedWithinWatchedDirFSInputEvent
        ), f"Expected MovedFileFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if file_src_parth is not None:
            assert input_event.file_src == file_src_parth

        if file_dst_path is not None:
            assert input_event.path == file_dst_path

    def check_queue_for_file_deletion_input_event(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a CreatedFileFSInputEvent in it.
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, FileDeletedFromWatchLocationFSInputEvent):
                self.validate_file_deletion_input_event(
                    input_event=event, file_path=file_path, message=message
                )
                return

        raise AssertionError(
            f"DeletedFileFSInputEvent not found in input_events - {input_events}"
        )

    @staticmethod
    def validate_file_deletion_input_event(
        input_event: InputEvent,
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check a file deletion event has been registered from the monitored location.

        :param input_event:
        :param file_path:
        :param message:
        :return:
        """
        if file_path is not None:
            assert isinstance(
                input_event, FileDeletedFromWatchLocationFSInputEvent
            ), f"expected DeletedFileFSInputEvent - got {input_event}" + (
                f" - {message}" if message else ""
            )
            assert file_path == input_event.path, (
                f"file path does not match expected - wanted {file_path}, "
                f"got {input_event.path}"
            )
        else:
            assert isinstance(
                input_event, FileDeletedFromWatchLocationFSInputEvent
            ), f"expected DeletedFileFSInputEvent - got {input_event}" + (
                f" - {message}" if message else ""
            )


class FileSystemTestUtilsDirEvents(GeneralUtils):
    """
    Events generated by watching a dir.
    """

    async def process_dir_event_queue_response(
        self,
        output_queue: asyncio.Queue[InputEvent],
        event_type: Type[InputEvent],
        dir_path: Optional[str] = None,
        allowed_queue_size: Union[int, list[int]] = 1,
    ) -> None:
        """
        Grab the next queue event - check it's a Dir type event.
        """

        # This should have generated an event
        queue_out = await self.timeout_get(output_queue)
        self.validate_dir_input_event(
            input_event=queue_out, event_type=event_type, dir_path=dir_path
        )

        await self.verify_queue_size(output_queue, allowed_queue_size=allowed_queue_size)

    def check_queue_for_dir_input_event(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        event_type: Type[DirTypeFSInput] | type[DirMovedWithinWatchedDirFSInputEvent],
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the queue has a dir input event.

        :param output_queue:
        :param event_type:
        :param dir_path:
        :param message:
        :return:
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, event_type):
                self.validate_dir_input_event(
                    input_event=event,
                    event_type=event_type,
                    dir_path=dir_path,
                    message=message,
                )
                return

        raise AssertionError(
            f"CreatedFileFSInputEvent not found in input_events - {input_events}"
        )

    @staticmethod
    def validate_dir_input_event(
        input_event: InputEvent,
        event_type: type[InputEvent]
        | type[DirTypeFSInput]
        | type[DirMovedWithinWatchedDirFSInputEvent],
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Validate a dir type input event has the correct form.

        :param input_event:
        :param event_type:
        :param dir_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, event_type
        ), f"Expected event of type {event_type.__name__} - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if dir_path is not None:
            ie_path = getattr(input_event, "path")

            assert ie_path == dir_path, f"expected {dir_path}, got {ie_path}"

    @staticmethod
    def validate_dir_creation_input_event(
        input_event: InputEvent,
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Validate that the given event is a dir creation event - as expected.

        :param input_event:
        :param dir_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, DirCreatedWithinWatchedDirFSInputEvent
        ), f"Expected CreatedDirFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )
        if dir_path is not None:
            assert input_event.path == dir_path

    def check_queue_for_dir_update_input_event_within_watched_dir(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a CreatedFileFSInputEvent in it.
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, DirUpdatedWithinWatchedDirFSInputEvent):
                self.validate_dir_update_input_event_within_watched_dir(
                    input_event=event, dir_path=dir_path, message=message
                )
                return

        raise AssertionError(
            f"UpdatedDirFSInputEvent not found in input_events - {input_events}"
        )

    def check_queue_for_dir_update_input_event_of_watched_dir(
        self,
        output_queue: Union[asyncio.Queue[InputEvent], List[InputEvent]],
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Check the given queue to see that there is a CreatedFileFSInputEvent in it.
        """
        if isinstance(output_queue, asyncio.Queue):
            input_events = self.dump_queue_to_list(output_queue)
        elif isinstance(output_queue, list):
            input_events = output_queue
        else:
            raise NotImplementedError(f"{output_queue} of unsupported type")

        for event in input_events:
            if isinstance(event, DirUpdatedAtWatchLocationFSInputEvent):
                self.validate_dir_update_input_event_of_watched_dir(
                    input_event=event, dir_path=dir_path, message=message
                )
                return

        raise AssertionError(
            f"UpdatedDirFSInputEvent not found in input_events - {input_events}"
        )

    @staticmethod
    def validate_dir_update_input_event_within_watched_dir(
        input_event: InputEvent,
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Validate a directory update input event.

        :param input_event:
        :param dir_path:
        :param message:
        :return:
        """
        err_str = f"Expected UpdatedDirFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )
        assert isinstance(input_event, DirUpdatedWithinWatchedDirFSInputEvent), err_str

        if dir_path is not None:
            assert (
                input_event.path == dir_path
            ), f"expected {dir_path} - got {input_event.path}"

    @staticmethod
    def validate_dir_update_input_event_of_watched_dir(
        input_event: InputEvent,
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Validate a directory update input event.

        :param input_event:
        :param dir_path:
        :param message:
        :return:
        """
        err_str = f"Expected UpdatedDirFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )
        assert isinstance(input_event, DirUpdatedAtWatchLocationFSInputEvent), err_str

        if dir_path is not None:
            assert (
                input_event.path == dir_path
            ), f"expected {dir_path} - got {input_event.path}"

    async def process_input_file_creation_response(
        self, output_queue: asyncio.Queue[InputEvent], file_path: str = "", message: str = ""
    ) -> None:
        """
        This event is emitted when we're in file mode, monitoring a file, which does not yet exist.
        """

        # This should have generated an event
        queue_out = await self.timeout_get(output_queue)
        self.validate_input_file_creation_input_event(
            input_event=queue_out, file_path=file_path, message=message
        )

        await self.verify_queue_size(output_queue)

    @staticmethod
    def validate_input_file_creation_input_event(
        input_event: InputEvent,
        file_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Validate that the input file has been registered created.

        :param input_event:
        :param file_path:
        :param message:
        :return:
        """
        assert isinstance(input_event, FileCreatedAtWatchLocationFSInputEvent)
        if file_path:
            err_str = (
                f"Expected FileCreatedAtWatchLocationFSInputEvent - "
                f"got {input_event}" + (f" - {message}" if message else "")
            )
            assert input_event.path == file_path, err_str

    @staticmethod
    def validate_input_dir_creation_input_event(
        input_event: InputEvent,
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        A directory has been created at the monitored location.

        :param input_event:
        :param dir_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, DirCreatedAtWatchLocationFSInputEvent
        ), f"Expected DirCreatedAtWatchLocationFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )
        if dir_path:
            assert input_event.path == dir_path, (
                f"dir_path is not as expected - theo - {dir_path} - "
                f"actual {input_event.path}" + (message if message else "")
            )

    async def process_dir_move_queue_response(
        self,
        output_queue: asyncio.Queue[InputEvent],
        dir_src_parth: Optional[str] = None,
        dir_dst_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Get the next event off the queue - check that it's one for the input file being deleted.
        """
        # This should have generated an event
        queue_out = await self.timeout_get(output_queue)
        self.validate_dir_move_input_event(
            input_event=queue_out,
            dir_src_parth=dir_src_parth,
            dir_dst_path=dir_dst_path,
            message=message,
        )

        await self.verify_queue_size(output_queue)

    @staticmethod
    def validate_dir_move_input_event(
        input_event: InputEvent,
        dir_src_parth: Optional[str] = None,
        dir_dst_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        A move has been detected within the monitored folder.

        :param input_event:
        :param dir_src_parth:
        :param dir_dst_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, DirMovedWithinWatchedDirFSInputEvent
        ), f"Expected MovedDirFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if dir_src_parth is not None:
            assert input_event.path == dir_src_parth
            assert input_event.dir_src_path == dir_src_parth

        if dir_dst_path is not None:
            assert input_event.dir_dst_path == dir_dst_path

    @staticmethod
    def validate_dir_deletion_input_event(
        input_event: InputEvent,
        dir_path: Optional[str] = None,
        message: str = "",
    ) -> None:
        """
        Validate a dir deletion event is as expected.

        :param input_event:
        :param dir_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, DirDeletedFromWatchedDirFSInputEvent
        ), f"Expected DeletedDirFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )

        if dir_path is not None:
            assert input_event.path == dir_path

    @staticmethod
    def validate_input_file_deletion_input_event(
        input_event: InputEvent,
        file_path: str = "",
        message: str = "",
    ) -> None:
        """
        The input file - which was being watched for changes - has been deleted.

        :param input_event:
        :param file_path:
        :param message:
        :return:
        """
        assert isinstance(
            input_event, FileDeletedFromWatchLocationFSInputEvent
        ), f"Expected DeletedDirFSInputEvent - got {input_event}" + (
            f" - {message}" if message else ""
        )
        if file_path:
            assert (
                input_event.path == file_path
            ), f"File path was not as expected - expected {file_path} - got {input_event.path}"
