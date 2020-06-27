import os
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Union
from unittest import TestCase

import bandersnatch.filter
import bandersnatch.storage
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror

TEST_CONF = "test.conf"


def _mock_config(contents: str, filename: str = TEST_CONF) -> BandersnatchConfig:
    """
    Creates a config file with contents and loads them into a
    BandersnatchConfig instance.
    """
    with open(filename, "w") as fd:
        fd.write(contents)

    instance = BandersnatchConfig()
    instance.config_file = filename
    instance.load_configuration()
    return instance


class TestWhitelistProject(TestCase):
    """
    Tests for the bandersnatch filtering classes
    """

    tempdir = None
    cwd = None

    def setUp(self) -> None:
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        bandersnatch.filter.loaded_filter_plugins = defaultdict(list)
        bandersnatch.storage.loaded_storage_plugins = defaultdict(list)
        os.chdir(self.tempdir.name)

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test__plugin__loads__explicitly_enabled(self) -> None:
        _mock_config(
            contents="""\
[plugins]
enabled =
    whitelist_project
"""
        )

        plugins = bandersnatch.filter.filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertListEqual(names, ["whitelist_project"])
        self.assertEqual(len(plugins), 1)

    def test__plugin__loads__default(self) -> None:
        _mock_config(
            """\
[mirror]
storage-backend = filesystem

[plugins]
"""
        )

        plugins = bandersnatch.filter.filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertNotIn("whitelist_project", names)

    def test__filter__matches__package(self) -> None:
        _mock_config(
            """\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    whitelist_project

[whitelist]
packages =
    foo
"""
        )

        mirror = Mirror(Path("."), Master(url="https://foo.bar.com"))
        mirror.packages_to_sync = {"foo": ""}
        mirror._filter_packages()

        self.assertIn("foo", mirror.packages_to_sync.keys())

    def test__filter__nomatch_package(self) -> None:
        _mock_config(
            """\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    whitelist_project

[whitelist]
packages =
    foo
"""
        )

        mirror = Mirror(Path("."), Master(url="https://foo.bar.com"))
        mirror.packages_to_sync = {"foo": "", "foo2": ""}
        mirror._filter_packages()

        self.assertIn("foo", mirror.packages_to_sync.keys())
        self.assertNotIn("foo2", mirror.packages_to_sync.keys())
