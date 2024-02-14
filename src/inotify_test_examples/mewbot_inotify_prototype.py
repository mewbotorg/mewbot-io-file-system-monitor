"""
Tests if we can implement the guts of inotify without the problematic features.

I.e. the polling. Which seems to break everything.

From what I understand
 - retrieve the ctypes inotify interface
 - feed it a file handle
 - it will then write events to that file handle
 - you can then read and process these events
 - or do something funky with the file handle to generate internal queue events directly
 - unfortunately, inotify is not recursive
 - so need to add recursive handlers as folder creation is detected
 - also need to walk the tree when we start and add monitors to all valid paths in it
 - because we



"""


