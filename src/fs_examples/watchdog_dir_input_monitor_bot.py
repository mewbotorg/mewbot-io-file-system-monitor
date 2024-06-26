"""
MMonitor a single directory - recursively looking for changes inside it.
"""


import logging
import sys
import time

from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    logging.info("start watching directory %s", path)
    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)  # type: ignore
    observer.start()  # type: ignore
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()  # type: ignore
        observer.join()
