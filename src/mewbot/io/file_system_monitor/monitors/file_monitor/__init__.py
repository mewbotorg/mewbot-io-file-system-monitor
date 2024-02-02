# !/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Stores the file monitor components for the file system monitor.
"""

from __future__ import annotations

import sys

from mewbot.io.file_system_monitor.monitors.file_monitor.windows_file_monitor import (
    WindowsFileMonitorMixin
)
from mewbot.io.file_system_monitor.monitors.file_monitor.linux_file_monitor import LinuxFileMonitorMixin

if sys.platform == "win32":
    BaseFileMonitorMixin = WindowsFileMonitorMixin
else:
    BaseFileMonitorMixin = LinuxFileMonitorMixin

__all__ = ["BaseFileMonitorMixin"]
