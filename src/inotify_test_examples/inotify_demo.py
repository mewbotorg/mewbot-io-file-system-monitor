"""
Conclusion: inotify is borked (on wsl).
"""


import inotify.adapters  # type: ignore


def _main():
    i = inotify.adapters.Inotify()

    i.add_watch("/mnt/c/mewbot/test_dir")

    with open("/mnt/c/mewbot/test_dir/teeessttinng", "w"):
        pass

    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event

        print("PATH=[{}] FILENAME=[{}] EVENT_TYPES={}".format(path, filename, type_names))


if __name__ == "__main__":
    _main()
