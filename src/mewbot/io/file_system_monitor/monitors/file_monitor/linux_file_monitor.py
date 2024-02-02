"""
Linux version of the notifier - using inotify.

As this seems to be the a) most recent and b) the least on fire python inotify bindings library.
"""

from typing import Any

import asyncio

from mewbot.io.file_system_monitor.monitors.file_monitor.base_file_monitor import (
    BaseFileMonitor,
)


class LinuxFileMonitorMixin(BaseFileMonitor):
    """
    For higher performance, and greater efficiency, using inotify on linux.

    (And, not least, because watchfiles is broken on linux.
    """
    internal_queue: asyncio.Queue = asyncio.Queue()

    async def monitor_file_watcher(self) -> None:
        """
        Actually do the job of monitoring and responding to the watcher.

        If the file is detected as deleted, then shut down the watcher.
        """
        if self.watcher is None:
            self._logger.info("Unexpected case - self.watcher is None in _monitor_watcher")
            await asyncio.sleep(
                self._polling_interval
            )  # Give the rest of the loop a chance to act
            return

        # Start polling the queue
        await self._pull_off_queue()

        # Fire the notifier
        await self._run_inotify_in_executor()

    async def _pull_off_queue(self) -> None:
        """
        Pull of the internal queue, process the events, and write to the event queue.

        :return:
        """
        while True:

            try:
                target_event = await self.internal_queue.get()
            except:
                continue

            await self.process_changes({(target_event, "something happened")})

    async def process_changes(self, changes: set[tuple[Any, str]]) -> bool:
        """
        Process events pulled from inotify.

        :param changes:
        :return:
        """
        for change in changes:

            inotify_event = change[0]

            print(inotify_event)

        return False

    async def _run_inotify_in_executor(self) -> None:
        """
        inotify is not async compatible - running it in an executor.

        :return:
        """
        await asyncio.get_running_loop().run_in_executor(func=self.inotify_watcher, executor=None)

    def inotify_watcher(self) -> None:
        """
        Pull events off the inotify observer and put them on the queue.

        :return:
        """
        import inotify

        i = inotify.adapters.Inotify()

        i.add_watch(self._input_path_state.input_path)

        for event in i.event_gen(yield_nones=False):
            self.internal_queue.put(event)

