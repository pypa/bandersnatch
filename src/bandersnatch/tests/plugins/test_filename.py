import os
from collections import defaultdict
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package
from bandersnatch_filter_plugins import filename_name


def _mock_config(contents, filename="test.conf"):
    """
    Creates a config file with contents and loads them into a
    BandersnatchConfig instance.
    """
    with open(filename, "w") as fd:
        fd.write(contents)

    instance = BandersnatchConfig()
    instance.config_file = filename
    instance.load_configuration()
    return instance


class BasePluginTestCase(TestCase):

    tempdir = None
    cwd = None

    def setUp(self):
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        bandersnatch.filter.loaded_filter_plugins = defaultdict(list)
        os.chdir(self.tempdir.name)

    def tearDown(self):
        if self.tempdir:
            os.chdir(self.cwd)
            self.tempdir.cleanup()
            self.tempdir = None


class TestExcludePlatformFilter(BasePluginTestCase):

    config_contents = """\
[plugins]
enabled =
    exclude_platform

[blacklist]
platforms =
    windows
    freebsd
    macos
    linux-armv7l
"""

    def test_plugin_compiles_patterns(self):
        _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_release_plugins()

        assert any(
            type(plugin) == filename_name.ExcludePlatformFilter for plugin in plugins
        )

    def test_exclude_platform(self):
        """
        Tests the platform filter for what it will keep and excluded
        based on the config provided. It is expected to drop all windows,
        freebsd and macos packages while only dropping linux-armv7l from
        linux packages
        """
        _mock_config(self.config_contents)

        bandersnatch.filter.filter_release_plugins()

        mirror = Mirror(".", Master(url="https://foo.bar.com"))
        pkg = Package("foobar", 1, mirror)
        pkg.info = {"name": "foobar", "version": "1.0"}
        pkg.releases = {
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
            ],
            "0.2": [
                {
                    "packagetype": "bdist_egg",
                    "filename": "foobar-0.1-freebsd-6.0-RELEASE-i386.egg",
                    "flag": "DROP",
                }
            ],
        }

        # count the files we should keep
        rv = pkg.releases.values()
        keep_count = sum(f["flag"] == "KEEP" for r in rv for f in r)

        pkg._filter_releases()

        # we should have the same keep count and no drop
        rv = pkg.releases.values()
        assert sum(f["flag"] == "KEEP" for r in rv for f in r) == keep_count
        assert all(f["flag"] == "DROP" for r in rv for f in r) is False

        # the release "0.2" should have been deleted since there is no more file in it
        assert len(pkg.releases.keys()) == 2
