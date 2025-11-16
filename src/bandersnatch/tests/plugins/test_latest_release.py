import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
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
            type(plugin) is latest_name.LatestReleaseFilter for plugin in plugins
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

    def test_latest_releases_keep_latest_time(self) -> None:
        mock_config(self.config_contents + "\nsort_by = time")

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo", "version": "2.0.0"},
            "releases": {
                "1.0.0": [{"upload_time_iso_8601": "2013-10-01T15:24:37.255645Z"}],
                "1.1.0": [{"upload_time_iso_8601": "2014-10-01T15:24:37.255645Z"}],
                "1.1.1": [{"upload_time_iso_8601": "2015-10-01T15:24:37.255645Z"}],
                "1.1.1d": [{"upload_time_iso_8601": "2020-10-01T15:24:37.255645Z"}],
                "1.1.2": [{"upload_time_iso_8601": "2016-10-01T15:24:37.255645Z"}],
                "1.1.3": [{"upload_time_iso_8601": "2017-10-01T15:24:37.255645Z"}],
                "2.0.0": [{"upload_time_iso_8601": "2018-10-01T15:24:37.255645Z"}],
            },
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        assert pkg.releases == {
            "1.1.1d": [{"upload_time_iso_8601": "2020-10-01T15:24:37.255645Z"}],
            "2.0.0": [{"upload_time_iso_8601": "2018-10-01T15:24:37.255645Z"}],
        }

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

    def test_latest_releases_ensure_reusable(self) -> None:
        """
        Tests the filter multiple times to ensure no state is preserved and
        thus is reusable between packages
        """
        mock_config(self.config_contents)

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        pkg1 = Package("foo", 1)
        pkg1._metadata = {
            "info": {"name": "foo", "version": "2.0.0"},
            "releases": {
                "0.1.1": {},
                "0.1.2": {},
                "0.1.3": {},
                "1.0.0": {},
                "1.1.0": {},
                "1.2.0": {},
                "2.0.0": {},
            },
        }
        pkg2 = Package("bar", 1)
        pkg2._metadata = {
            "info": {"name": "bar", "version": "0.3.0"},
            "releases": {
                "0.1.0": {},
                "0.1.1": {},
                "0.1.2": {},
                "0.1.3": {},
                "0.1.4": {},
                "0.1.5": {},
                "0.2.0": {},
                "0.3.0": {},
            },
        }

        pkg1.filter_all_releases(mirror.filters.filter_release_plugins())
        pkg2.filter_all_releases(mirror.filters.filter_release_plugins())

        assert pkg1.releases == {"1.2.0": {}, "2.0.0": {}}
        assert pkg2.releases == {"0.2.0": {}, "0.3.0": {}}


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
            type(plugin) is latest_name.LatestReleaseFilter for plugin in plugins
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
