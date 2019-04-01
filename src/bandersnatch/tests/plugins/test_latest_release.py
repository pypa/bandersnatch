import os
from collections import defaultdict
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package
from bandersnatch_filter_plugins import latest_name


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


class TestLatestReleaseFilter(BasePluginTestCase):

    config_contents = """\
[blacklist]
plugins =
    latest_release

[latest_release]
keep = 2
"""

    def test_plugin_compiles_patterns(self):
        _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_release_plugins()

        assert any(
            type(plugin) == latest_name.LatestReleaseFilter for plugin in plugins
        )
        plugin = next(
            plugin
            for plugin in plugins
            if type(plugin) == latest_name.LatestReleaseFilter
        )
        assert plugin.keep == 2

    def test_plugin_check_match(self):
        _mock_config(self.config_contents)

        bandersnatch.filter.filter_release_plugins()

        mirror = Mirror(".", Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1, mirror)
        pkg.releases = {
            "1.0.0": {},
            "1.1.0": {},
            "1.1.1": {},
            "1.1.2": {},
            "1.1.3": {},
            "2.0.0": {},
        }

        pkg._filter_latest()

        assert pkg.releases == {"1.1.3": {}, "2.0.0": {}}


class TestLatestReleaseFilter2(BasePluginTestCase):

    config_contents = """\
[blacklist]
plugins =
    latest_release
"""

    def test_plugin_compiles_patterns(self):
        _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_release_plugins()

        assert any(
            type(plugin) == latest_name.LatestReleaseFilter for plugin in plugins
        )
        plugin = next(
            plugin
            for plugin in plugins
            if type(plugin) == latest_name.LatestReleaseFilter
        )
        assert plugin.keep == 0

    def test_plugin_check_match(self):
        _mock_config(self.config_contents)

        bandersnatch.filter.filter_release_plugins()

        mirror = Mirror(".", Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1, mirror)
        pkg.releases = {
            "1.0.0": {},
            "1.1.0": {},
            "1.1.1": {},
            "1.1.2": {},
            "1.1.3": {},
            "2.0.0": {},
        }

        pkg._filter_latest()

        assert pkg.releases == {
            "1.0.0": {},
            "1.1.0": {},
            "1.1.1": {},
            "1.1.2": {},
            "1.1.3": {},
            "2.0.0": {},
        }
