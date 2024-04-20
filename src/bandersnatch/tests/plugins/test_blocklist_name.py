import os
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.package import Package
from bandersnatch.tests.unittest_factories import mock_config, mock_mirror


class TestBlockListProject(TestCase):
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
        bc = mock_config(
            """\
[plugins]
enabled =
    blocklist_project
"""
        )

        plugins = bandersnatch.filter.LoadedFilters(config=bc).filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertListEqual(names, ["blocklist_project"])
        self.assertEqual(len(plugins), 1)

    def test__plugin__doesnt_load__explicitly__disabled(self) -> None:
        bc = mock_config(
            """\
[plugins]
enabled =
    blocklist_release
"""
        )

        plugins = bandersnatch.filter.LoadedFilters(config=bc).filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertNotIn("blocklist_project", names)

    def test__plugin__loads__default(self) -> None:
        bc = mock_config(
            """\
[blocklist]
"""
        )

        plugins = bandersnatch.filter.LoadedFilters(config=bc).filter_project_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertNotIn("blocklist_project", names)

    def test__filter__matches__package(self) -> None:
        mirror = mock_mirror(
            """\
[plugins]
enabled =
    blocklist_project
[blocklist]
packages =
    foo
"""
        )

        mirror.packages_to_sync = {"foo": ""}
        mirror._filter_packages()

        self.assertNotIn("foo", mirror.packages_to_sync.keys())

    def test__filter__nomatch_package(self) -> None:
        mirror = mock_mirror(
            """\
        [blocklist]
        plugins =
            blocklist_project
        packages =
            foo
        """
        )

        mirror.packages_to_sync = {"foo2": ""}
        mirror._filter_packages()

        self.assertIn("foo2", mirror.packages_to_sync.keys())

    def test__filter__name_only(self) -> None:
        mirror = mock_mirror(
            """\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    blocklist_project

[blocklist]
packages =
    foo==1.2.3
"""
        )

        mirror.packages_to_sync = {"foo": "", "foo2": ""}
        mirror._filter_packages()

        self.assertIn("foo", mirror.packages_to_sync.keys())
        self.assertIn("foo2", mirror.packages_to_sync.keys())

    def test__filter__varying__specifiers(self) -> None:
        mirror = mock_mirror(
            """\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    blocklist_project

[blocklist]
packages =
    foo==1.2.3
    bar~=3.0,<=1.5
    snu
"""
        )

        mirror.packages_to_sync = {
            "foo": "",
            "foo2": "",
            "bar": "",
            "snu": "",
        }
        mirror._filter_packages()

        self.assertEqual({"foo": "", "foo2": "", "bar": ""}, mirror.packages_to_sync)


class TestBlockListRelease(TestCase):
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
        bc = mock_config(
            """\
[plugins]
enabled =
    blocklist_release
"""
        )

        plugins = bandersnatch.filter.LoadedFilters(config=bc).filter_release_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertListEqual(names, ["blocklist_release"])
        self.assertEqual(len(plugins), 1)

    def test__plugin__doesnt_load__explicitly__disabled(self) -> None:
        bc = mock_config(
            """\
[plugins]
enabled =
    blocklist_package
"""
        )

        plugins = bandersnatch.filter.LoadedFilters(config=bc).filter_release_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertNotIn("blocklist_release", names)

    def test__filter__matches__release(self) -> None:
        mirror = mock_mirror(
            """\
[plugins]
enabled =
    blocklist_release
[blocklist]
packages =
    foo==1.2.0
"""
        )

        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {"1.2.0": {}, "1.2.1": {}},
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        self.assertEqual(pkg.releases, {"1.2.1": {}})

    def test__dont__filter__prereleases(self) -> None:
        mirror = mock_mirror(
            """\
[plugins]
enabled =
    blocklist_release
[blocklist]
packages =
    foo<=1.2.0
"""
        )

        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {
                "1.1.0a2": {},
                "1.1.1beta1": {},
                "1.2.0": {},
                "1.2.1": {},
                "1.2.2alpha3": {},
                "1.2.3rc1": {},
            },
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        self.assertEqual(pkg.releases, {"1.2.1": {}, "1.2.2alpha3": {}, "1.2.3rc1": {}})

    def test__casing__no__affect(self) -> None:
        mirror = mock_mirror(
            """\
[plugins]
enabled =
    blocklist_release
[blocklist]
packages =
    Foo<=1.2.0
"""
        )

        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {"1.2.0": {}, "1.2.1": {}},
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        self.assertEqual(pkg.releases, {"1.2.1": {}})
