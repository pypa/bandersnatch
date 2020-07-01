import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from mock_config import mock_config

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package
from bandersnatch_filter_plugins import prerelease_name


class BasePluginTestCase(TestCase):

    tempdir = None
    cwd = None

    def setUp(self) -> None:
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        os.chdir(self.tempdir.name)

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None


class TestRegexReleaseFilter(BasePluginTestCase):

    config_contents = """\
[plugins]
enabled =
    prerelease_release
"""

    def test_plugin_includes_predefined_patterns(self) -> None:
        mock_config(self.config_contents)

        plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()

        assert any(
            type(plugin) == prerelease_name.PreReleaseFilter for plugin in plugins
        )
        plugin = next(
            plugin
            for plugin in plugins
            if isinstance(plugin, prerelease_name.PreReleaseFilter)
        )
        expected_patterns = [
            re.compile(pattern_string) for pattern_string in plugin.PRERELEASE_PATTERNS
        ]
        assert plugin.patterns == expected_patterns

    def test_plugin_check_match(self) -> None:
        mock_config(self.config_contents)

        mirror = Mirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1, mirror)
        pkg.info = {"name": "foo", "version": "1.2.0"}
        pkg.releases = {
            "1.2.0alpha1": {},
            "1.2.0a2": {},
            "1.2.0beta1": {},
            "1.2.0b2": {},
            "1.2.0rc1": {},
            "1.2.0": {},
        }

        pkg._filter_releases(mirror.filters.filter_release_plugins())

        assert pkg.releases == {"1.2.0": {}}
