import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from mock_config import mock_config

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch_filter_plugins import latest_name


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


class TestLatestReleaseFilter(BasePluginTestCase):

    config_contents = """\
[plugins]
enabled =
    latest_release

[latest_release]
keep = 2
"""

    def test_plugin_compiles_patterns(self) -> None:
        mock_config(self.config_contents)

        plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()

        assert any(
            type(plugin) == latest_name.LatestReleaseFilter for plugin in plugins
        )
        plugin = next(
            plugin
            for plugin in plugins
            if isinstance(plugin, latest_name.LatestReleaseFilter)
        )
        assert plugin.keep == 2

    def test_latest_releases_keep_latest(self) -> None:
        mock_config(self.config_contents)

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo", "version": "2.0.0"},
            "releases": {
                "1.0.0": {},
                "1.1.0": {},
                "1.1.1": {},
                "1.1.2": {},
                "1.1.3": {},
                "2.0.0": {},
            },
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        assert pkg.releases == {"1.1.3": {}, "2.0.0": {}}

    def test_latest_releases_keep_stable(self) -> None:
        mock_config(self.config_contents)

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo", "version": "2.0.0"},  # stable version
            "releases": {
                "1.0.0": {},
                "1.1.0": {},
                "1.1.1": {},
                "1.1.2": {},
                "1.1.3": {},
                "2.0.0": {},  # <= stable version, keep it
                "2.0.1b1": {},
                "2.0.1b2": {},  # <= most recent, keep it
            },
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        assert pkg.releases == {"2.0.1b2": {}, "2.0.0": {}}


class TestLatestReleaseFilterUninitialized(BasePluginTestCase):

    config_contents = """\
[plugins]
enabled =
    latest_release
"""

    def test_plugin_compiles_patterns(self) -> None:
        mock_config(self.config_contents)

        plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()

        assert any(
            type(plugin) == latest_name.LatestReleaseFilter for plugin in plugins
        )
        plugin = next(
            plugin
            for plugin in plugins
            if isinstance(plugin, latest_name.LatestReleaseFilter)
        )
        assert plugin.keep == 0

    def test_latest_releases_uninitialized(self) -> None:
        mock_config(self.config_contents)

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo", "version": "2.0.0"},
            "releases": {
                "1.0.0": {},
                "1.1.0": {},
                "1.1.1": {},
                "1.1.2": {},
                "1.1.3": {},
                "2.0.0": {},
            },
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        assert pkg.releases == {
            "1.0.0": {},
            "1.1.0": {},
            "1.1.1": {},
            "1.1.2": {},
            "1.1.3": {},
            "2.0.0": {},
        }
