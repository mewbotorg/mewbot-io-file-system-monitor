
# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
setup.py intended for a mewbot.io namespace plugin.
"""


import codecs
import os
from pathlib import Path

import setuptools


# From https://packaging.python.org/en/latest/guides/single-sourcing-package-version/
# (the first solution seemed a pretty sensible option for a non-namespaced package)
def read(rel_path):
    """
    Read a file based on it's relatvie path.

    :param rel_path:
    :return:
    """
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    """
    Get a version string looking object from a relative path

    :param rel_path:
    :return:
    """
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


# Finding the right README.md and inheriting the mewbot licence
current_file = Path(__file__)
root_repo_dir = current_file.parents[2]
assert root_repo_dir.exists()

with open(current_file.parent.joinpath("README.md"), "r", encoding="utf-8") as rmf:
    long_description = rmf.read()

with open(current_file.parent.joinpath("requirements.txt"), "r", encoding="utf-8") as rf:
    requirements = list(x for x in rf.read().splitlines(False) if x and not x.startswith("#"))

# Reading the LICENSE file and parsing the results
# LICENSE file should contain a symlink to the licence in the LICENSES folder
# Held in the root of the repo

with Path("LICENSE.md").open("r", encoding="utf-8") as license_file:
    license_text = license_file.read()

cand_full_license_path = Path(license_text.strip())

# We have a symlink to the license - read it
if cand_full_license_path.exists():
    true_license_ident = os.path.splitext(license_text.split(r"/")[-1])[0]

    with cand_full_license_path.open("r", encoding="utf-8") as true_license_file:
        true_license_text = true_license_file.read()

else:
    raise NotImplementedError(
        f"Cannot programmatically determine license_ident from license. "
        f"Link '{license_text}' may be invalid. "
        "If you have added your own license in the LICENSE.md file, please move it to the "
        "LICENSES folder in the root of the repo and replace the LICENSE.md file wih a symlink "
        "to that resource."
    )

# There are a number of bits of special sauce in this call
# - You can fill it out manually - for your project
# - You can copy this and make the appropriate changes
# - Or you can run "mewbot make_namespace_plugin" - and follow the onscreen instructions.
#   Which should take care of most of the fiddly bits for you.
setuptools.setup(
    name='mewbot-io-file-system-monitor',

    python_requires=">=3.10",  # Might be relaxed later

    version=get_version('src/mewbot/io/file_system_monitor/__init__.py'),

    install_requires=requirements,

    author='Alex Cameron',
    author_email="mewbot@quicksilver.london",

    maintainer='Alex Cameron',
    maintainer_email='mewbot@quicksilver.london',

    license=true_license_text,

    url='https://github.com/mewbotorg/mewbot-io-file_system_monitor',
    project_urls={
        "Bug Tracker": "https://github.com/mewbotorg/mewbot-file-system-monitor/issues",
    },

    description='A plugin which allows mewbot to watch a file system for events (files being created, files being moved e.t.c).',
    long_description=long_description,
    long_description_content_type="text/markdown",

    packages=setuptools.find_namespace_packages(where="src", include=["mewbot.*"]),
    package_dir={"": "src"},

    package_data={"": ["py.typed"]},

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',

        # "Framework :: mewbot",

        'Programming Language :: Python',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',

{ % if cookiecutter.license == "MIT" - %}
        'License :: OSI Approved :: MIT License',
{ % - elif cookiecutter.license == "BSD-3" - %}
        'License :: OSI Approved :: BSD License',
{ % - elif cookiecutter.license == "GNU GPL v3.0" - %}
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
{ % - elif cookiecutter.license == "Apache Software License 2.0" - %}
        'License :: OSI Approved :: Apache Software License',
{ % - elif cookiecutter.license == "Mozilla Public License 2.0" - %}
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
{ % - endif %}

    ],

    entry_points = {"mewbotv1": ["file_system_monitor = mewbot.io.file_system_monitor"]}


)
