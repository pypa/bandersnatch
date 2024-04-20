import os
import re
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.unittest_factories import mock_config, mock_mirror
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
    config_match_package = """\
[filter_prerelease]
packages =
    duckdb
"""

    def test_plugin_includes_predefined_patterns(self) -> None:
        bc = mock_config(self.config_contents)

        plugins = bandersnatch.filter.LoadedFilters(config=bc).filter_release_plugins()

        assert any(
            type(plugin) is prerelease_name.PreReleaseFilter for plugin in plugins
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

    def _check_filter(self, mirror: BandersnatchMirror, package: str) -> bool:
        pkg = Package(package, serial=1)
        pkg._metadata = {
            "info": {"name": package, "version": "1.2.0"},
            "releases": {
                "1.2.0alpha1": {},
                "1.2.0a2": {},
                "1.2.0beta1": {},
                "1.2.0b2": {},
                "1.2.0rc1": {},
                "1.2.0.dev912": {},
                "1.2.0": {},
            },
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        return bool(pkg.releases == {"1.2.0": {}})

    def test_plugin_filter_all(self) -> None:
        mirror = mock_mirror(self.config_contents)
        assert self._check_filter(mirror, "foo") is True
        assert self._check_filter(mirror, "duckdb") is True

    def test_plugin_filter_packages(self) -> None:
        mirror = mock_mirror(self.config_contents + self.config_match_package)
        assert self._check_filter(mirror, "foo") is False
        assert self._check_filter(mirror, "duckdb") is True
