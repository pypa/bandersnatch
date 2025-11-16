import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_filter_plugins import filename_name


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


class TestExcludePlatformFilter(BasePluginTestCase):
    config_contents = """\
[plugins]
enabled =
    exclude_platform

[blocklist]
platforms =
    windows
    freebsd
    macos
    linux_armv7l
    py3
    py3.5
    py3.7
    py3.9
"""

    def test_plugin_compiles_patterns(self) -> None:
        mock_config(self.config_contents)

        plugins = bandersnatch.filter.LoadedFilters().filter_release_file_plugins()

        assert any(
            type(plugin) is filename_name.ExcludePlatformFilter for plugin in plugins
        )

    def test_exclude_platform(self) -> None:
        """
        Tests the platform filter for what it will keep and excluded
        based on the config provided. It is expected to drop all windows,
        freebsd and macos packages while only dropping linux-armv7l from
        linux packages
        """
        mock_config(self.config_contents)

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foobar", 1)
        pkg._metadata = {
            "info": {"name": "foobar", "version": "1.0"},
            "releases": {
                "1.0": [
                    {
                        "packagetype": "sdist",
                        "filename": "foobar-1.0-win32.tar.gz",
                        "flag": "KEEP",
                    },
                    {
                        "packagetype": "bdist_msi",
                        "filename": "foobar-1.0.msi",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_wininst",
                        "filename": "foobar-1.0.exe",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_dmg",
                        "filename": "foobar-1.0.dmg",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-1.0-win32.zip",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-1.0-linux.tar.gz",
                        "flag": "KEEP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-1.0-manylinux1_i686.whl",
                        "flag": "KEEP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-1.0-linux_armv7l.whl",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-1.0-macosx_10_14_x86_64.whl",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_egg",
                        "filename": "foobar-1.0-win_amd64.zip",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "unknown",
                        "filename": "foobar-1.0-unknown",
                        "flag": "KEEP",
                    },
                ],
                "0.1": [
                    {
                        "packagetype": "sdist",
                        "filename": "foobar-0.1-win32.msi",
                        "flag": "KEEP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-0.1-win32.whl",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-0.1-py3-none-any.whl",
                        "flag": "DROP",
                    },
                ],
                "0.2": [
                    {
                        "packagetype": "bdist_egg",
                        "filename": "foobar-0.1-freebsd-6.0-RELEASE-i386.egg",
                        "flag": "DROP",
                    }
                ],
                "0.3": [
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-0.3-cp35-cp35m-manylinux1_x86_64.whl",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-0.3-cp36-cp36m-manylinux1_x86_64.whl",
                        "flag": "KEEP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-0.3-cp37-manylinux1_x86_64.whl",
                        "flag": "DROP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-0.3-pp38-pypy38-manylinux1_x86_64.whl",
                        "flag": "KEEP",
                    },
                    {
                        "packagetype": "bdist_wheel",
                        "filename": "foobar-0.3-cp39-cp39m-manylinux1_x86_64.whl",
                        "flag": "DROP",
                    },
                ],
            },
        }

        # count the files we should keep
        rv = pkg.releases.values()
        keep_count = sum(f["flag"] == "KEEP" for r in rv for f in r)

        pkg.filter_all_releases_files(mirror.filters.filter_release_file_plugins())

        # we should have the same keep count and no drop
        rv = pkg.releases.values()
        assert sum(f["flag"] == "KEEP" for r in rv for f in r) == keep_count
        assert sum(f["flag"] == "DROP" for r in rv for f in r) == 0

        # the release "0.2" should have been deleted since there is no more file in it
        assert len(pkg.releases.keys()) == 3
