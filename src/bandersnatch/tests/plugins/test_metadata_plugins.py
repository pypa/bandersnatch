import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_filter_plugins.metadata_filter import SizeProjectMetadataFilter


class TestSizeProjectMetadataFilter(TestCase):
    """
    Tests for the bandersnatch filtering by project size
    """

    def setUp(self) -> None:
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        os.chdir(self.tempdir.name)

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()

    def test__size__plugin__loads__and__initializes(self) -> None:
        mock_config(
            """\
[plugins]
enabled =
    size_project_metadata

[size_project_metadata]
max_package_size = 1G
"""
        )

        plugins = bandersnatch.filter.LoadedFilters().filter_metadata_plugins()
        names = [plugin.name for plugin in plugins]
        self.assertListEqual(names, ["size_project_metadata"])
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], SizeProjectMetadataFilter)
        plugin: SizeProjectMetadataFilter = cast(SizeProjectMetadataFilter, plugins[0])
        self.assertTrue(plugin.initialized)

    def test__filter__size__only(self) -> None:
        mock_config(
            """\
[plugins]
enabled =
    size_project_metadata

[size_project_metadata]
max_package_size = 2K
"""
        )

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))

        # Test that under-sized project is allowed
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {"1.2.0": [{"size": 1024}], "1.2.1": {}},
        }
        self.assertTrue(pkg.filter_metadata(mirror.filters.filter_metadata_plugins()))

        # Test that over-sized project is blocked
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {"1.2.0": [{"size": 1024}], "1.2.1": [{"size": 1025}]},
        }
        self.assertFalse(pkg.filter_metadata(mirror.filters.filter_metadata_plugins()))

    def test__filter__size__or__allowlist(self) -> None:
        mock_config(
            """\
[plugins]
enabled =
    size_project_metadata

[size_project_metadata]
max_package_size = 2K

[allowlist]
packages =
    foo
"""
        )

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))

        # Test that under-sized, allowlisted project is allowed
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {"1.2.0": [{"size": 1024}], "1.2.1": {}},
        }
        self.assertTrue(pkg.filter_metadata(mirror.filters.filter_metadata_plugins()))

        # Test that over-sized, allowlisted project is allowed
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo"},
            "releases": {"1.2.0": [{"size": 1024}], "1.2.1": [{"size": 1025}]},
        }
        self.assertTrue(pkg.filter_metadata(mirror.filters.filter_metadata_plugins()))

        # Test that under-sized, non-allowlisted project is allowed
        pkg = Package("bar", 1)
        pkg._metadata = {
            "info": {"name": "bar"},
            "releases": {"1.2.0": [{"size": 1024}], "1.2.1": {}},
        }
        self.assertTrue(pkg.filter_metadata(mirror.filters.filter_metadata_plugins()))

        # Test that over-sized, non-allowlisted project is blocked
        pkg = Package("bar", 1)
        pkg._metadata = {
            "info": {"name": "bar"},
            "releases": {"1.2.0": [{"size": 1024}], "1.2.1": [{"size": 1025}]},
        }
        self.assertFalse(pkg.filter_metadata(mirror.filters.filter_metadata_plugins()))
