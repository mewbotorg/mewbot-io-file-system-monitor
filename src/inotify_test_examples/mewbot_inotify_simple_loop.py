"""
This ... seems like it should just work.

It does not - this is because of a weirdness with how file systems are handled on wsl.

"""

# pylint: disable=duplicate-code


import os
import time

from mewbot.io.file_system_monitor.mewbot_inotify.mewbot_inotify_simple import (
    INotify,
    flags,
)

inotify = INotify()
watch_flags = flags.CREATE | flags.DELETE | flags.MODIFY | flags.DELETE_SELF

TEST_MEWBOT_PATH = "/home/ajcameron"

assert os.path.exists(TEST_MEWBOT_PATH)

wd = inotify.add_watch(TEST_MEWBOT_PATH, watch_flags)

COUNT = 1

while True:
    #
    # if not os.path.exists("/tmp/inotify_test"):
    #     os.mkdir("/tmp/inotify_test")

    print(f"{COUNT = }")
    COUNT += 1

    time.sleep(20)

    # # Now create, delete and modify some files in the directory being monitored:
    # os.chdir("/tmp/inotify_test")
    # # CREATE event for a directory:
    # os.system("mkdir foo")
    # # CREATE event for a file:
    # os.system("echo hello > test.txt")
    # # MODIFY event for the file:
    # os.system("echo world >> test.txt")
    # # DELETE event for the file
    # os.system("rm test.txt")
    # # DELETE event for the directory
    # os.system("rmdir foo")
    # os.chdir("/tmp")

    # # DELETE_SELF on the original directory. # Also generates an IGNORED event
    # # indicating the watch was removed.
    # os.system("rmdir inotify_test")

    # And see the corresponding events:
    for event in inotify.read(timeout=1, read_delay=1):
        print(event)
        for flag in flags.from_mask(event.mask):
            print("    " + str(flag))
