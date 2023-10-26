# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Get a FileSytemMonitorIO bot loaded - check it loads the right components.
"""

from __future__ import annotations

from typing import Type

import os.path
import tempfile

from mewbot.api.v1 import IOConfig
from mewbot.io.file_system_monitor import FileSystemMonitorIO
from mewbot.test import BaseTestClassWithConfig

# pylint: disable=R0903
#  Disable "too few public methods" for test cases - most test files will be classes used for
#  grouping and then individual tests alongside these

TEST_YAML_FOR_LOAD = """

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

kind: IOConfig
implementation: mewbot.io.file_system_monitor.FileSystemMonitorIO
uuid: aaaaaaaa-aaaa-4aaa-0001-aaaaaaaaaa00
properties:
  input_path: 'INPUT_PATH_HERE'
  input_path_type: 'file'

---

kind: Behaviour
implementation: mewbot.api.v1.Behaviour
uuid: aaaaaaaa-aaaa-4aaa-0001-aaaaaaaaaa01
properties:
  name: 'Target File Change Alerts'
triggers:
  - kind: Trigger
    implementation: examples.file_system_bots.file_input_monitor_bot.FileSystemAllCommandTrigger
    uuid: aaaaaaaa-aaaa-4aaa-0001-aaaaaaaaaa02
    properties: {}
conditions: []
actions:
  - kind: Action
    implementation: examples.file_system_bots.file_input_monitor_bot.FileSystemInputPrintResponse
    uuid: aaaaaaaa-aaaa-4aaa-0001-aaaaaaaaaa03
    properties: {}

"""


tmp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with

TARGET_FILE = os.path.join(tmp_dir.name, "target_file.txt")
with open(TARGET_FILE, "w", encoding="utf-8") as target_file_out:
    target_file_out.write("This is some test text so the file exists.")

tmp_yaml = os.path.join(tmp_dir.name, "test_fs_monitor.yaml")
with open(tmp_yaml, "w", encoding="utf-8") as tmp_yaml_file:
    tmp_yaml_file.write(TEST_YAML_FOR_LOAD.replace("INPUT_PATH_HERE", TARGET_FILE))


class TestIoFileSystem(BaseTestClassWithConfig[FileSystemMonitorIO]):
    """
    Tests loading a bot which includes a FileSystemMonitorIO.
    """

    config_file: str = tmp_yaml
    implementation: Type[FileSystemMonitorIO] = FileSystemMonitorIO

    def test_check_class(self) -> None:
        """
        Checks that the correct class has loaded.

        :return:
        """
        assert isinstance(self.component, FileSystemMonitorIO)
        assert isinstance(self.component, IOConfig)

    def test_class_properties_input_path(self) -> None:
        """
        Tests that the class properties defined in the yaml have loaded.

        :return:
        """
        assert self.component.input_path == TARGET_FILE

    def test_class_properties_input_path_type(self) -> None:
        """
        Tests that the class properties defined in the yaml have loaded.

        :return:
        """
        assert self.component.input_path == TARGET_FILE

        self.component.input_path = "this is not a valid path"
        assert self.component.input_path == "this is not a valid path"

        assert self.component.input_path_type == "file"

        # Should work
        self.component.input_path_type = "dir"

        # Should not work
        try:
            self.component.input_path_type = "some invalid nonsense"
        except AssertionError:
            pass

    def test_class_get_inputs_method(self) -> None:
        """
        Tests that the get_inputs method returns sensible results.

        :return:
        """
        registered_inputs = self.component.get_inputs()
        assert registered_inputs is not None

        # Zero out the input and check it reloads properly
        self.component._input = None  # pylint: disable=protected-access
        registered_inputs = self.component.get_inputs()
        assert registered_inputs is not None

        # Should work
        self.component.input_path_type = "dir"

        # Zero out the input and check it reloads properly
        self.component._input = None  # pylint: disable=protected-access
        registered_inputs = self.component.get_inputs()
        assert registered_inputs is not None

        # This should fail
        self.component._input_path_type = "some nonense"  # pylint: disable=protected-access
        try:
            self.component.get_inputs()
        except AssertionError:
            pass

    def test_class_get_outputs_method(self) -> None:
        """
        Tests that the get_outputs method does not yield anything.

        :return:
        """
        assert not self.component.get_outputs()
