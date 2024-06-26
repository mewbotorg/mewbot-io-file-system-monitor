# Copyright (c) 2016, Chris Billington
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided wi6h the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Version of inotify simple, modified to be mypy compatible.
"""
from typing import Any, Callable, Optional

import os
import pathlib
from collections import namedtuple
from ctypes import CDLL, c_int, get_errno
from ctypes.util import find_library
from enum import IntEnum
from errno import EINTR
from struct import calcsize, unpack_from
from time import sleep

try:
    from fcntl import ioctl as FCNTL_IOCTL  # type: ignore
except ModuleNotFoundError:
    FCNTL_IOCTL = None

from io import FileIO
from os import fsdecode, fsencode

POLL: Optional[Any] = None
try:
    from select import poll as select_poll

    POLL = select_poll
except ImportError:
    POLL = None


FIONREAD: Optional[int] = None
try:
    from termios import FIONREAD as terminos_fionread  # type: ignore

    FIONREAD = terminos_fionread
except ModuleNotFoundError:
    FIONREAD = None


__version__ = "1.3.5"

__all__ = ["Event", "INotify", "flags", "masks", "parse_events"]

_LIBC = None


def _libc_call(function: Callable[[Any], int], *args: Any) -> int:
    """
    Wrapper which raises errors and retries on EINTR.
    """
    while True:
        rc = function(*args)
        if rc != -1:
            return rc
        errno = get_errno()
        if errno != EINTR:
            raise OSError(errno, os.strerror(errno))


#: A ``namedtuple`` (wd, mask, cookie, name) for an inotify event. On Python 3 the
#: :attr:`~inotify_simple.Event.name`  field is a ``str`` decoded with
#: ``os.fsdecode()``, on Python 2 it is ``bytes``.
Event = namedtuple("Event", ["wd", "mask", "cookie", "name"])

_EVENT_FMT = "iIII"
_EVENT_SIZE = calcsize(_EVENT_FMT)


class INotify(FileIO):
    """
    The inotify file descriptor returned by ``inotify_init()``.

    You are free to use it directly with ``os.read`` if you'd prefer not to call
    :func:`~inotify_simple.INotify.read` for some reason.
    Also, available as :func:`~inotify_simple.INotify.fileno`
    """

    fd: property = property(FileIO.fileno)

    def __init__(self, inheritable: bool = False, nonblocking: bool = False) -> None:
        """
        File-like object wrapping ``inotify_init1()``.

         Raises ``OSError`` on failure.
        :func:`~inotify_simple.INotify.close` should be called when no longer needed.
        Can be used as a context manager to ensure it is closed, and can be used
        directly by functions expecting a file-like object, such as ``select``, or with
        functions expecting a file descriptor via
        :func:`~inotify_simple.INotify.fileno`.

        Args:
            inheritable (bool): whether the inotify file descriptor will be inherited by
                child processes. The default,``False``, corresponds to passing the
                ``IN_CLOEXEC`` flag to ``inotify_init1()``. Setting this flag when
                opening filedescriptors is the default behaviour of Python standard
                library functions since PEP 446. On Python < 3.3, the file descriptor
                will be inheritable and this argument has no effect, one must instead
                use fcntl to set FD_CLOEXEC to make it non-inheritable.

            nonblocking (bool): whether to open the inotify file descriptor in
                nonblocking mode, corresponding to passing the ``IN_NONBLOCK`` flag to
                ``inotify_init1()``. This does not affect the normal behaviour of
                :func:`~inotify_simple.INotify.read`, which uses ``poll()`` to control
                blocking behaviour according to the given timeout, but will cause other
                reads of the file descriptor (for example if the application reads data
                manually with ``os.read(fd)``) to raise ``BlockingIOError`` if no data
                is available.
        """
        try:
            libc_so = find_library("c")
        except RuntimeError:  # Python on Synology NASs raises a RuntimeError
            libc_so = None
        global _LIBC  # pylint: disable=global-statement
        _LIBC = _LIBC or CDLL(libc_so or "libc.so.6", use_errno=True)
        zero_cloexec = getattr(os, "O_CLOEXEC", 0)  # Only defined in Python 3.3+
        # pylint: disable=no-member
        current_flags = (not inheritable) * zero_cloexec | bool(nonblocking) * os.O_NONBLOCK
        FileIO.__init__(self, _libc_call(_LIBC.inotify_init1, current_flags), mode="rb")

        assert POLL is not None, "this position should never be reached"

        self._poller = POLL()
        self._poller.register(self.fileno())

    def add_watch(self, path: str | bytes | pathlib.Path, mask: int) -> int:
        """
        Calls the underlying c library to add a watch on a particular path.

        Wrapper around ``inotify_add_watch()``.

        Returns the watch descriptor or raises an ``OSError`` on failure.

        Args:
            path (str, bytes, or PathLike): The path to watch. Will be encoded with
                ``os.fsencode()`` before being passed to ``inotify_add_watch()``.

            mask (int): The mask of events to watch for. Can be constructed by
                bitwise-ORing :class:`~inotify_simple.flags` together.

        Returns:
            int: watch descriptor
        """
        assert _LIBC is not None, "_LIBC was, unexpectedly, None"

        # Explicit conversion of Path to str required on Python < 3.6
        path = str(path) if hasattr(path, "parts") else path
        return _libc_call(_LIBC.inotify_add_watch, self.fileno(), fsencode(path), mask)

    def rm_watch(self, wd: int) -> None:
        """
        Removes the watch from the underlying lib.

        Wrapper around ``inotify_rm_watch()``.

        Raises ``OSError`` on failure.

        Args:
            wd (int): The watch descriptor to remove
        """
        assert _LIBC is not None, "_LIBC was, unexpectedly, None"

        _libc_call(_LIBC.inotify_rm_watch, self.fileno(), wd)

    # I would not have subclass read and change the interface ...
    def read(  # type: ignore
        self, timeout: int | float | None = None, read_delay: Optional[int] = None
    ) -> list[Event]:
        """
        Read the inotify file descriptor and return the resulting namedtuples.

         These are :attr:`~inotify_simple.Event`  naemtuples - (wd, mask, cookie, name).

        Args:
            timeout (int): The time in milliseconds to wait for events if there are
                none. If negative or ``None``, block until there are events. If zero,
                return immediately if there are no events to be read.

            read_delay (int): If there are no events immediately available for reading,
                then this is the time in milliseconds to wait after the first event
                arrives before reading the file descriptor. This allows further events
                to accumulate before reading, which allows the kernel to coalesce like
                events and can decrease the number of events the application needs to
                process. However, this also increases the risk that the event queue will
                overflow due to not being emptied fast enough.

        Returns:
            generator: generator producing :attr:`~inotify_simple.Event` namedtuples

        .. warning::
            If the same inotify file descriptor is being read by multiple threads
            simultaneously, this method may attempt to read the file descriptor when no
            data is available. It may return zero events, or block until more events
            arrive (regardless of the requested timeout), or in the case that the
            :func:`~inotify_simple.INotify` object was instantiated with
            ``nonblocking=True``, raise ``BlockingIOError``.
        """
        data = self._readall()
        if not data and timeout != 0 and self._poller.poll(timeout):
            if read_delay is not None:
                sleep(read_delay / 1000.0)
            data = self._readall()
        return parse_events(data)

    def _readall(self) -> bytes:
        """
        Read bytes from the file descriptor.

        :return:
        """
        bytes_avail = c_int()
        FCNTL_IOCTL(self, FIONREAD, bytes_avail)
        if not bytes_avail.value:
            return b""
        return os.read(self.fileno(), bytes_avail.value)


def parse_events(data: bytes) -> list[Event]:
    """
    Unpack data read from an inotify file descriptor into :attr:`~inotify_simple.Event` namedtuples.

    (wd, mask, cookie, name).
    This function can be used if the application has read raw data from the inotify file
    descriptor rather than calling :func:`~inotify_simple.INotify.read`.

    Args:
        data (bytes): A bytestring as read from an inotify file descriptor.

    Returns:
        list: list of :attr:`~inotify_simple.Event` namedtuples
    """
    pos = 0
    events = []
    while pos < len(data):
        wd, mask, cookie, namesize = unpack_from(_EVENT_FMT, data, pos)
        pos += _EVENT_SIZE + namesize
        data_pos = pos - namesize
        name = data[data_pos:pos].split(b"\x00", 1)[0]
        events.append(Event(wd, mask, cookie, fsdecode(name)))
    return events


class Flags(IntEnum):
    """
    Inotify flags as defined in ``inotify.h`` but with ``IN_`` prefix omitted.

    Includes a convenience method :func:`~inotify_simple.flags.from_mask` for extracting
    flags from a mask.
    """

    ACCESS = 0x00000001  #: File was accessed
    MODIFY = 0x00000002  #: File was modified
    ATTRIB = 0x00000004  #: Metadata changed
    CLOSE_WRITE = 0x00000008  #: Writable file was closed
    CLOSE_NOWRITE = 0x00000010  #: Unwritable file closed
    OPEN = 0x00000020  #: File was opened
    MOVED_FROM = 0x00000040  #: File was moved from X
    MOVED_TO = 0x00000080  #: File was moved to Y
    CREATE = 0x00000100  #: Subfile was created
    DELETE = 0x00000200  #: Subfile was deleted
    DELETE_SELF = 0x00000400  #: Self was deleted
    MOVE_SELF = 0x00000800  #: Self was moved

    UNMOUNT = 0x00002000  #: Backing fs was unmounted
    Q_OVERFLOW = 0x00004000  #: Event queue overflowed
    IGNORED = 0x00008000  #: File was ignored

    ONLYDIR = 0x01000000  #: only watch the path if it is a directory
    DONT_FOLLOW = 0x02000000  #: don't follow a sym link
    EXCL_UNLINK = 0x04000000  #: exclude events on unlinked objects
    MASK_ADD = 0x20000000  #: add to the mask of an already existing watch
    ISDIR = 0x40000000  #: event occurred against dir
    ONESHOT = 0x80000000  #: only send event once

    @classmethod
    def from_mask(cls, mask: int) -> list[int]:
        """Convenience method that returns a list of every flag in a mask."""
        return [flag for flag in cls.__members__.values() if flag & mask]


# Changing the interface is not worth it
# pylint: disable = invalid-name
flags = Flags


# pylint: disable = invalid-name
class masks(IntEnum):
    """Convenience masks as defined in ``inotify.h`` but with ``IN_`` prefix omitted."""

    #: helper event mask equal to ``flags.CLOSE_WRITE | flags.CLOSE_NOWRITE``
    CLOSE = flags.CLOSE_WRITE | flags.CLOSE_NOWRITE
    #: helper event mask equal to ``flags.MOVED_FROM | flags.MOVED_TO``
    MOVE = flags.MOVED_FROM | flags.MOVED_TO

    #: bitwise-OR of all the events that can be passed to
    #: :func:`~inotify_simple.INotify.add_watch`
    ALL_EVENTS = (
        flags.ACCESS
        | flags.MODIFY
        | flags.ATTRIB
        | flags.CLOSE_WRITE
        | flags.CLOSE_NOWRITE
        | flags.OPEN
        | flags.MOVED_FROM
        | flags.MOVED_TO
        | flags.CREATE
        | flags.DELETE
        | flags.DELETE_SELF
        | flags.MOVE_SELF
    )
