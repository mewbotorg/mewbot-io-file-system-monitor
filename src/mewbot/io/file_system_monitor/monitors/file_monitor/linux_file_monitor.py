"""
Linux version of the notifier - using inotify.

As this seems to be the a) most recent and b) the least on fire python inotify bindings library.
"""

from typing import Any, Optional

import asyncio

from mewbot.io.file_system_monitor.monitors.file_monitor.base_file_monitor import (
    BaseFileMonitor,
)
from mewbot.io.file_system_monitor.mewbot_inotify.mewbot_inotify_recursive import (
    Event,
    INotify,
    flags,
)
from mewbot.io.file_system_monitor.mewbot_inotify.mewbot_inotify_simple import (
    flags,
)

from mewbot.io.file_system_monitor.fs_events import FileUpdatedAtWatchLocationFSInputEvent, FileDeletedFromWatchLocationFSInputEvent

# Todo: Put the watchdog version here as well


class InotifyLinuxFileMonitorMixin(BaseFileMonitor):
    """
    For higher performance, and greater efficiency, using inotify on linux.

    (And, not least, because watchfiles is broken on linux.
    """

    internal_queue: asyncio.Queue = asyncio.Queue()

    inotify: Optional[INotify] = None

    async def monitor_file_watcher(self) -> None:
        """
        Actually do the job of monitoring and responding to the watcher.

        If the file is detected as deleted, then shut down the watcher.
        """
        if self.inotify is None:

            self._logger.info("inotify is None - starting inotify")

        # Fire the watcher
        watcher_status = await self.watch_file()

        if watcher_status is None:
            self._logger.info("Shutdown seen by monitor_file_watcher - shutting down")
        else:
            self._logger.info("Unexpeted status seen by monitor_file_watcher from watch_file - %s", watcher_status)

        return None

    async def _pull_off_queue(self) -> bool:
        """
        Pull of the internal queue, process the events, and write to the event queue.

        :return:
        """
        self._logger.info("About to start watching queue")

        while True:

            # Give the loop a chance to do something else
            await asyncio.sleep(0.1)
            try:
                target_event = await self.internal_queue.get()
            except Exception as e:
                self._logger.info("Exception when pulling from internal queue - %s", e)
                continue

            self._logger.info("Processing - %s", target_event)

            # If an event is None, shutdown called - stop processing the queue
            if target_event is None:
                self._logger.info("_pull_off_queue has detected file_deleted - shutdown")
                return True

            shutdown_now = await self.process_changes({(target_event, "something happened")})
            if shutdown_now:
                self._logger.info("process_changes has called shutdown")
                return True

            # Corner case
            if self.inotify is None:
                return True

    async def process_changes(self, changes: set[tuple[Any, str]]) -> bool:
        """
        Process events pulled from inotify.

        :param changes:
        :return:
        """
        for change in changes:
            inotify_event = change[0]

            event_flags = {_ for _ in flags.from_mask(inotify_event.mask)}

            if event_flags == {flags.MODIFY}:
                await self._process_file_modification_event(inotify_event)
                continue

            # Kill the loop and note that the file has been deleted
            if event_flags == {flags.DELETE_SELF}:
                await self._process_file_deleted_at_input(inotify_event)
                self._logger.info("process_changes shutting down.")
                return True

            if event_flags == {flags.IGNORED}:
                continue

            self._logger.info(f"Event with flags {event_flags = } could not be processed.")

        # No shutdown events where detected
        return False

    async def _process_file_modification_event(self, inotify_file_mod_event: Event) -> bool:
        """
        Process a file modification event.

        :return:
        """

        await self.send(
            FileUpdatedAtWatchLocationFSInputEvent(
                base_event=inotify_file_mod_event, path=self.input_path
            )
        )

        return True

    async def _process_file_deleted_at_input(self, inotify_file_del_event: Event) -> bool:
        """
        The watched file has been deleted.

        :param inotify_file_del_event:
        :return:
        """
        await self.send(
            FileDeletedFromWatchLocationFSInputEvent(
                base_event=inotify_file_del_event, path=self.input_path
            )
        )

        return True

    def _trigger_shutdown(self, *args):
        """
        Poison pills the internal queue with None - which should trigger shutdown.

        :param args:
        :return:
        """

        self._logger.info("_trigger_shutdown  called with args - %s", str(args))

        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                self.internal_queue.put_nowait, None
            )
        except RuntimeError:  # Can happen when the shutdown is not clean
            return

    async def watch_file(self) -> None:
        """
        Pull events off the inotify observer and put them on the queue.

        :return:
        """
        await asyncio.sleep(2)

        self._logger.info("About to run inotify on a file")

        inotify = INotify()

        self.inotify = inotify

        watch_flags = (
            flags.MODIFY
            | flags.ATTRIB
            | flags.MOVED_FROM
            | flags.MOVED_TO
            | flags.CREATE
            | flags.DELETE
            | flags.DELETE_SELF
            | flags.MOVE_SELF
            | flags.ISDIR
        )

        wd = inotify.add_watch(self._input_path_state.input_path, watch_flags)

        # self._logger.info("Starting inotify poll - polling every 0.1 seconds - with inotify %s", inotify)

        while True:

            # self._logger.info("In loop - pulling events")

            events = tuple((event, event.name) for event in inotify.read(timeout=0.1))

            # self._logger.info("Got events - %", str(events))

            shutdown = await self.process_changes(events)

            if shutdown:
                self._logger.info("Shutdown called - ending loop")
                break

            # Give the rest of the loop a chance to do something
            await asyncio.sleep(0.1)

        self._logger.info("Ending inotify poll - %s", wd)


LinuxFileMonitorMixin = InotifyLinuxFileMonitorMixin