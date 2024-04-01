#
#  This file is part of Inotify Recursive.
#
#  Copyright (c) 2019 Torben Haase <https://pixelsvsbytes.com>
#
#  Inotify Recursive is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any
#  later version.
#
#  Inotify Recursive is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
#  FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
#  details. You should have received a copy of the GNU General Public License
#  along with Inotify Recursive. If not, see <https://www.gnu.org/licenses/>.
#
################################################################################

"""
Part of the internal mewbot version of inotifyrecursive.
"""

from typing import Any, Callable, Optional, TypedDict

import logging
import os

import mewbot.io.file_system_monitor.mewbot_inotify.mewbot_inotify_simple as inotify_simple

# Re-export public exports of inotify_simple
# pylint: disable = invalid-name
flags = inotify_simple.flags
# pylint: disable = invalid-name
masks = inotify_simple.masks
parse_events = inotify_simple.parse_events
Event = inotify_simple.Event


class InotifyTypedDict(TypedDict):
    """
    Typed dict for the internal cache which stores inotify data for recursion.
    """

    children: dict[int, "InotifyTypedDict"]
    filter: int
    mask: int
    name: str | bytes
    parent: int


class INotify(inotify_simple.INotify):
    """
    Recursive inotify monitor system.
    """

    __info: dict[int, dict[str, Any]]

    __cleanup_queue: list[int]

    def __init__(self) -> None:
        """
        Recursive version of inotify simple - intended to extend the watch to all subfolders.
        """
        inotify_simple.INotify.__init__(self)
        self.__info = {}
        self.__cleanup_queue = []

    # Dealing with the too many arguments would involve excessive interface changes
    def __add_info(  # pylint: disable=too-many-arguments
        self,
        wd: int,
        name: str | bytes,
        mask: int,
        in_filter: Callable[[str | bytes, int, bool], bool] | None,
        parent: int,
    ) -> None:
        self.__info[wd] = {
            "children": {},
            "filter": in_filter,
            "mask": mask,
            "name": name,
            "parent": parent,
        }
        if parent != -1:
            self.__info[parent]["children"][name] = wd
        logging.debug("Added info for watch %d: %s", wd, self.__info[wd])

    def __clr_info(self, wd: int) -> None:
        self.__cleanup_queue.append(wd)
        logging.debug("Enlist info for watch %d for clean-up", wd)

    def __clr_infos(self) -> None:
        for wd in self.__cleanup_queue:
            self.__rm_info(wd)
        self.__cleanup_queue = []

    def __set_info(self, wd: int, name: str | bytes, parent: int) -> None:
        old_parent = self.__info[wd]["parent"]
        if old_parent != -1:
            old_name = self.__info[wd]["name"]
            del self.__info[old_parent]["children"][old_name]
        self.__info[wd]["name"] = name
        self.__info[wd]["parent"] = parent
        if parent != -1:
            self.__info[parent]["children"][name] = wd
        logging.debug("Updated info for watch %d: %s", wd, self.__info[wd])

    def __rm_info(self, wd: int) -> None:
        """
        Remove a file descriptor from the internal info cache.

        :param wd:
        :return:
        """
        name = self.__info[wd]["name"]
        parent = self.__info[wd]["parent"]
        del self.__info[parent]["children"][name]
        del self.__info[wd]
        logging.debug("Removed info for watch %d", wd)

    def __add_watch_recursive(  # pylint: disable = too-many-arguments # noqa
        self,
        path: str | bytes,
        mask: int,
        local_filter: Optional[Callable[[str | bytes, int, bool], bool]],
        name: str | bytes,
        parent: int,
        loose: bool = True,
    ) -> int | None:
        """
        Recursively add a dir and all it's subfolders.

        :param path:
        :param mask:
        :param local_filter:
        :param name:
        :param parent:
        :param loose:
        :return:
        """
        try:
            if local_filter is not None and not local_filter(name, parent, True):
                logging.debug("Name has been filtered, not adding watch: %s", name)
                return None
            wd = inotify_simple.INotify.add_watch(
                self,
                path,
                mask | flags.IGNORED | flags.CREATE | flags.MOVED_FROM | flags.MOVED_TO,
            )
            logging.debug("Added watch %d", wd)
            if parent == -1:
                name = path
            if wd in self.__info:
                self.__set_info(wd, name, parent)
            else:
                self.__add_info(wd, name, mask, local_filter, parent)
                for entry in os.listdir(path):
                    entrypath = os.path.join(path, entry)  # type: ignore
                    if os.path.isdir(entrypath):
                        self.__add_watch_recursive(entrypath, mask, local_filter, entry, wd)
            return wd
        except OSError as e:
            if loose and e.errno == 2:
                logging.debug("Cannot add watch, path not found: %s", path)
                return None
            raise

    def __rm_watch_recursive(self, wd: int, loose: bool = True) -> None:
        """
        Recursively remove a watch from this an all sub-dirs.

        :param wd:
        :param loose:
        :return:
        """
        try:
            if wd in self.__info:
                children = self.__info[wd]["children"]
                for name in children:
                    self.__rm_watch_recursive(children[name])
                inotify_simple.INotify.rm_watch(self, wd)
                logging.debug("Removed watch %d", wd)
        except OSError as e:
            if loose and e.errno == 22:
                logging.debug("Cannot remove watch, descriptor does not exist: %d", wd)
                return
            raise

    def add_watch_recursive(
        self,
        path: str | bytes,
        mask: int,
        local_filter: Optional[Callable[[str | bytes, int, bool], bool]] = None,
    ) -> int | None:
        """
        Recursively add a watch - adding a watch for every sub-dir in the tree.

        :param path:
        :param mask:
        :param local_filter:
        :return:
        """
        name = os.path.split(path)[1]
        return self.__add_watch_recursive(path, mask, local_filter, name, -1, False)

    def rm_watch_recursive(self, wd: int) -> None:
        """
        Recursively remove a watch on every dir in a tree.

        :param wd:
        :return:
        """
        self.__rm_watch_recursive(wd, False)

    def get_path(self, wd: int) -> str | bytes:
        """
        Get the originating path from the wd.

        :param wd:
        :return:
        """
        path = self.__info[wd]["name"]
        parent = self.__info[wd]["parent"]
        while parent != -1:
            wd = parent
            path = os.path.join(self.__info[wd]["name"], path)
            parent = self.__info[wd]["parent"]
        assert isinstance(path, (bytes, str)), "keep mypy happy"
        return path

    # I would not have overridden and added a timeout - but changing it would require
    # rearchitecting the underlying package to an unacceptable degree
    # Also - fake8 does not like the level of complexity of this functon...
    def read(  # type: ignore  # noqa
        self,
        timeout: Optional[int] | Optional[float] = None,
        read_delay: Optional[int] = None,
    ) -> list[Event]:
        """
        Attempt to read inotify information out of the file descriptor.

        :param timeout:
        :param read_delay:
        :return:
        """
        self.__clr_infos()
        events = []
        moved_from: dict[int, int] = {}
        for event in inotify_simple.INotify.read(
            self, timeout=timeout, read_delay=read_delay
        ):
            if event.wd in self.__info:
                info = self.__info[event.wd]
                mask = info["mask"]
                local_filter = info["filter"]
                if local_filter is not None and not local_filter(
                    event.name, event.wd, event.mask & flags.ISDIR
                ):
                    logging.debug(
                        "Name has been filtered, not processing event: %s", event.name
                    )
                    continue
                if event.mask & flags.ISDIR:
                    if event.mask & (flags.CREATE | flags.MOVED_TO):
                        path = os.path.join(self.get_path(event.wd), event.name)
                        self.__add_watch_recursive(
                            path, mask, info["filter"], event.name, event.wd
                        )
                        if event.mask & flags.MOVED_TO and event.cookie in moved_from:
                            del moved_from[event.cookie]
                    elif event.mask & flags.MOVED_FROM:
                        try:
                            moved_from[event.cookie] = info["children"][event.name]
                        except KeyError:
                            logging.debug(
                                "%s no longer present in %s", event.name, info["children"]
                            )

                elif event.mask & flags.IGNORED:
                    self.__clr_info(event.wd)
                if event.mask & mask:
                    events.append(event)
            else:
                events.append(event)
        for cookie in moved_from:  # pylint: disable=consider-using-dict-items
            self.rm_watch_recursive(moved_from[cookie])
        return events
