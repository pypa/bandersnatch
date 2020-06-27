import os
import unittest
from collections import defaultdict
from tempfile import TemporaryDirectory
from unittest import TestCase

from mock_config import mock_config

import bandersnatch.filter
from bandersnatch.configuration import BandersnatchConfig

from bandersnatch.filter import (  # isort:skip
    Filter,
    FilterProjectPlugin,
    FilterReleasePlugin,
    filter_project_plugins,
    filter_release_plugins,
)


class TestBandersnatchFilter(TestCase):
    """
    Tests for the bandersnatch filtering classes
    """

    tempdir = None
    cwd = None

    def setUp(self) -> None:
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        bandersnatch.filter.loaded_filter_plugins = defaultdict(list)
        os.chdir(self.tempdir.name)

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test__filter_project_plugins__loads(self) -> None:
        mock_config(
            """\
[plugins]
enabled = all
"""
        )
        builtin_plugin_names = [
            "blacklist_project",
            "regex_project",
            "whitelist_project",
        ]

        plugins = filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        for name in builtin_plugin_names:
            self.assertIn(name, names)

    def test__filter_release_plugins__loads(self) -> None:
        mock_config(
            """\
[plugins]
enabled = all
"""
        )
        builtin_plugin_names = [
            "blacklist_release",
            "prerelease_release",
            "regex_release",
            "exclude_platform",
            "latest_release",
        ]

        plugins = filter_release_plugins()
        names = [plugin.name for plugin in plugins]
        for name in builtin_plugin_names:
            self.assertIn(name, names)

    def test__filter_no_plugin(self) -> None:
        mock_config(
            """\
[plugins]
enabled =
"""
        )

        plugins = list(filter_release_plugins())
        self.assertEqual(len(plugins), 0)

        plugins = list(filter_project_plugins())
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


if __name__ == "__main__":
    unittest.main()
