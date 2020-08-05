import os
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from mock_config import mock_config

import bandersnatch.filter
import bandersnatch.storage
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package


class TestAllowListProject(TestCase):
    """
    Tests for the bandersnatch filtering classes
    """

    tempdir = None
    cwd = None

    def setUp(self) -> None:
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        bandersnatch.storage.loaded_storage_plugins = defaultdict(list)
        os.chdir(self.tempdir.name)

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None

    def test__plugin__loads__explicitly_enabled(self) -> None:
        mock_config(
            contents="""\
[plugins]
enabled =
    allowlist_project
"""
        )

        plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertListEqual(names, ["allowlist_project"])
        self.assertEqual(len(plugins), 1)

    def test__plugin__loads__default(self) -> None:
        mock_config(
            """\
[mirror]
storage-backend = filesystem

[plugins]
"""
        )

        plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertNotIn("allowlist_project", names)

    def test__filter__matches__package(self) -> None:
        mock_config(
            """\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo
"""
        )

        mirror = Mirror(Path("."), Master(url="https://foo.bar.com"))
        mirror.packages_to_sync = {"foo": ""}
        mirror._filter_packages()

        self.assertIn("foo", mirror.packages_to_sync.keys())

    def test__filter__nomatch_package(self) -> None:
        mock_config(
            """\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo
"""
        )

        mirror = Mirror(Path("."), Master(url="https://foo.bar.com"))
        mirror.packages_to_sync = {"foo": "", "foo2": ""}
        mirror._filter_packages()

        self.assertIn("foo", mirror.packages_to_sync.keys())
        self.assertNotIn("foo2", mirror.packages_to_sync.keys())

    def test__filter__name_only(self) -> None:
        mock_config(
            """\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo==1.2.3
"""
        )

        mirror = Mirror(Path("."), Master(url="https://foo.bar.com"))
        mirror.packages_to_sync = {"foo": "4.5.6"}
        mirror._filter_packages()

        self.assertIn("foo", mirror.packages_to_sync.keys())


class TestAllowlistRelease(TestCase):
    """
    Tests for the bandersnatch filtering classes
    """

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

    def test__plugin__loads__explicitly_enabled(self) -> None:
        mock_config(
            """\
[plugins]
enabled =
    allowlist_release
"""
        )

        plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertListEqual(names, ["allowlist_release"])
        self.assertEqual(len(plugins), 1)

    def test__plugin__doesnt_load__explicitly__disabled(self) -> None:
        mock_config(
            """\
[plugins]
enabled =
    allowlist_package
"""
        )

        plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertNotIn("allowlist_release", names)

    def test__filter__matches__release(self) -> None:
        mock_config(
            """\
[plugins]
enabled =
    allowlist_release
[allowlist]
packages =
    foo==1.2.0
"""
        )

        mirror = Mirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1, mirror)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {"1.2.0": {}, "1.2.1": {}},
        }

        pkg._filter_all_releases(mirror.filters.filter_release_plugins())

        self.assertEqual(pkg.releases, {"1.2.0": {}})
