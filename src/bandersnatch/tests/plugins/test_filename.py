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
[blacklist]
plugins =
    exclude_platform

platforms =
    windows
    macos
"""

    def test_plugin_compiles_patterns(self):
        _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_filename_plugins()

        assert any(type(plugin) == filename_name.ExcludePlatformFilter for plugin in plugins)

    def test_plugin_check_match(self):
        _mock_config(self.config_contents)

        bandersnatch.filter.filter_filename_plugins()

        mirror = Mirror(".", Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1, mirror)
        pkg.releases = {
            "1.0": [{"packagetype": "sdist", "filename": "foo-1.0-win32.tar.gz", "flag": "KEEP"},
                    {"packagetype": "bdist_msi", "filename": "foo-1.0", "flag": "DROP"},
                    {"packagetype": "bdist_wininst", "filename": "foo-1.0", "flag": "DROP"},
                    {"packagetype": "bdist_dmg", "filename": "foo-1.0", "flag": "DROP"},
                    {"packagetype": "bdist_wheel", "filename": "foo-1.0-win32.zip", "flag": "DROP"},
                    {"packagetype": "bdist_wheel", "filename": "foo-1.0-linux.tar.gz", "flag": "KEEP"},
                    {"packagetype": "bdist_wheel", "filename": "foo-1.0-macosx_10_14_x86_64.whl", "flag": "DROP"},
                    {"packagetype": "bdist_egg", "filename": "foo-1.0-win_amd64.zip", "flag": "DROP"},
                    {"packagetype": "unknown", "filename": "foo-1.0-unknown", "flag": "KEEP"}]
        }

        pkg._filter_filenames()

        files = pkg.releases["1.0"]

        assert sum(file["flag"] == "KEEP" for file in files) == 3
        assert all(file["flag"] == "DROP" for file in files) is False
