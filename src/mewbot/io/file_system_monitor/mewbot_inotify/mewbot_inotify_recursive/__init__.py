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
Internal version of inotify recursive - modified to conform to modern typing standards.

Licensing for this component is different from the rest of this module.
See above in this file.
"""

from mewbot.io.file_system_monitor.mewbot_inotify.mewbot_inotify_recursive.inotifyrecursive import (
    Event,
    INotify,
    flags,
    masks,
    parse_events,
)

__all__ = ["flags", "masks", "parse_events", "Event", "INotify"]
