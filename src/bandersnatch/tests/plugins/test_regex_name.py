import os
import re
from collections import defaultdict
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package
from bandersnatch_filter_plugins import regex_name


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


class TestRegexReleaseFilter(BasePluginTestCase):

    config_contents = """\
[blacklist]
plugins =
    regex_release

[filter_regex]
releases =
    .+rc\\d$
"""

    def test_plugin_compiles_patterns(self):
        _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_release_plugins()

        assert any(type(plugin) == regex_name.RegexReleaseFilter for plugin in plugins)
        plugin = next(
            plugin
            for plugin in plugins
            if type(plugin) == regex_name.RegexReleaseFilter
        )
        assert plugin.patterns == [re.compile(r".+rc\d$")]

    def test_plugin_check_match(self):
        _mock_config(self.config_contents)

        bandersnatch.filter.filter_release_plugins()

        mirror = Mirror(".", Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1, mirror)
        pkg.releases = {"foo-1.2.0rc2": {}, "foo-1.2.0": {}}

        pkg._filter_releases()

        assert pkg.releases == {"foo-1.2.0": {}}


class TestRegexProjectFilter(BasePluginTestCase):

    config_contents = """\
[blacklist]
plugins =
    regex_project

[filter_regex]
packages =
    .+-evil$
"""

    def test_plugin_compiles_patterns(self):
        _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_project_plugins()

        assert any(type(plugin) == regex_name.RegexProjectFilter for plugin in plugins)
        plugin = next(
            plugin
            for plugin in plugins
            if type(plugin) == regex_name.RegexProjectFilter
        )
        assert plugin.patterns == [re.compile(r".+-evil$")]

    def test_plugin_check_match(self):
        _mock_config(self.config_contents)

        bandersnatch.filter.filter_release_plugins()

        mirror = Mirror(".", Master(url="https://foo.bar.com"))
        mirror.packages_to_sync = {"foo-good": {}, "foo-evil": {}}
        mirror._filter_packages()

        assert list(mirror.packages_to_sync.keys()) == ["foo-good"]
