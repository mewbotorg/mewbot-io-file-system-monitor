"""
Conclusion: inotify is borked (on wsl).
"""

# inotify cannot (or should not) be installed on windows systems

# pylint: disable = import-error
# pylint: disable=duplicate-code
import inotify.adapters  # type: ignore


def _main():
    """
    Run inotify on the specified path.

    :return:
    """
    i = inotify.adapters.Inotify()

    i.add_watch("/mnt/c/mewbot/test_dir")

    with open("/mnt/c/mewbot/test_dir/teeessttinng", "w", encoding="utf-8"):
        pass

    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event

        print(f"PATH=[{path}] FILENAME=[{filename}] EVENT_TYPES={type_names}")


if __name__ == "__main__":
    _main()
