import os
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest import TestCase

import pytest

from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.tests.mock_config import mock_config

from bandersnatch.filter import (  # isort:skip
    Filter,
    FilterProjectPlugin,
    FilterReleasePlugin,
    LoadedFilters,
)

pytestmark = pytest.mark.asyncio(loop_scope="class")


class TestBandersnatchFilter(TestCase):
    """
    Tests for the bandersnatch filtering classes
    """

    tempdir = None
    cwd = None

    def setUp(self) -> None:
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        os.chdir(self.tempdir.name)
        sys.stderr.write(self.tempdir.name)
        sys.stderr.flush()

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test__filter_project_plugins__loads(self) -> None:
        mock_config("""\
[plugins]
enabled = all
""")
        builtin_plugin_names = [
            "blocklist_project",
            "regex_project",
            "allowlist_project",
        ]

        plugins = LoadedFilters().filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        for name in builtin_plugin_names:
            self.assertIn(name, names)

    def test__filter_release_plugins__loads(self) -> None:
        mock_config("""\
[plugins]
enabled = all
""")
        builtin_plugin_names = [
            "blocklist_release",
            "prerelease_release",
            "regex_release",
            "latest_release",
        ]

        plugins = LoadedFilters().filter_release_plugins()
        names = [plugin.name for plugin in plugins]
        for name in builtin_plugin_names:
            self.assertIn(name, names)

    def test__filter_no_plugin(self) -> None:
        mock_config("""\
[plugins]
enabled =
""")

        plugins = LoadedFilters().filter_release_plugins()
        self.assertEqual(len(plugins), 0)

        plugins = LoadedFilters().filter_project_plugins()
        self.assertEqual(len(plugins), 0)

    def test__filter_base_clases(self) -> None:
        """
        Test the base filter classes
        """

        plugin = Filter()
        self.assertEqual(plugin.name, "filter")
        try:
            plugin.initialize_plugin()
            error = False
        except Exception:
            error = True
        self.assertFalse(error)

        plugin = FilterReleasePlugin()
        self.assertIsInstance(plugin, Filter)
        self.assertEqual(plugin.name, "release_plugin")
        try:
            plugin.filter({})
            error = False
        except Exception:
            error = True
        self.assertFalse(error)

        plugin = FilterProjectPlugin()
        self.assertIsInstance(plugin, Filter)
        self.assertEqual(plugin.name, "project_plugin")
        try:
            result = plugin.check_match(key="value")
            error = False
            self.assertIsInstance(result, bool)
        except Exception:
            error = True
        self.assertFalse(error)

    def test_deprecated_keys(self) -> None:
        instance = BandersnatchConfig()
        instance.read_string("[allowlist]\npackages=foo\n[blocklist]\npackages=bar\n")

        plugin = Filter()
        assert plugin.allowlist.name == "allowlist"
        assert plugin.blocklist.name == "blocklist"

    def test__filter_project_blocklist_allowlist__pep503_normalize(self) -> None:
        mock_config("""\
[plugins]
enabled =
    blocklist_project
    allowlist_project

[blocklist]
packages =
    SampleProject
    trove----classifiers

[allowlist]
packages =
    SampleProject
    trove----classifiers
""")

        plugins = {
            plugin.name: plugin for plugin in LoadedFilters().filter_project_plugins()
        }

        self.assertTrue(plugins["blocklist_project"].check_match(name="sampleproject"))
        self.assertTrue(
            plugins["blocklist_project"].check_match(name="trove-classifiers")
        )
        self.assertFalse(plugins["allowlist_project"].check_match(name="sampleproject"))
        self.assertFalse(
            plugins["allowlist_project"].check_match(name="trove-classifiers")
        )


if __name__ == "__main__":
    unittest.main()
