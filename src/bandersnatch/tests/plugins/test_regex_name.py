import os
from collections import defaultdict
import re
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import pytest

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch_filter_plugins.regex_name import RegexReleaseFilter


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


class TestRegexReleaseFilter(TestCase):

    tempdir = None
    cwd = None
    config_contents = """\
[blacklist]
plugins =
    regex_release

[regex]
releases =
    .+rc\d$
"""

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

    def test_plugin_compiles_patterns(self):
        cfg = _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_release_plugins()

        assert any(type(plugin) == RegexReleaseFilter for plugin in plugins)
        plugin = next(plugin for plugin in plugins if type(plugin) == RegexReleaseFilter)
        assert plugin.patterns == [re.compile(r".+rc\d$")]

    def test_plugin_check_match(self):
        cfg = _mock_config(self.config_contents)

        plugins = bandersnatch.filter.filter_release_plugins()

        mirror = Mirror(".", Master(url="https://foo.bar.com"))
        pkg = Package('foo', 1, mirror)
        pkg.releases = {
            "foo-1.2.0rc2": {},
            "foo-1.2.0": {},
        }

        pkg._filter_releases()

        assert pkg.releases == {"foo-1.2.0": {}}


