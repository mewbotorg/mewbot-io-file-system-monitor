# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Monitoring a directory for changes and monitoring a file for changes are very different processes.

As such, different classes are used for each of them.
"""

from __future__ import annotations

import aiopath  # type: ignore

from mewbot.io.file_system_monitor.monitors.dir_monitor.event_handler import (
    MewbotEventHandler,
)

from mewbot.io.file_system_monitor.monitors.dir_monitor.linux_file_system_observer import LinuxFileSystemObserver
from mewbot.io.file_system_monitor.monitors.dir_monitor.windows_file_system_observer import WindowsFileSystemObserver


__all__ = ["LinuxFileSystemObserver", "WindowsFileSystemObserver"]