import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_filter_plugins import regex_name


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


class TestRegexReleaseFilter(BasePluginTestCase):
    config_contents = """\
[plugins]
enabled =
    regex_release

[filter_regex]
releases =
    .+rc\\d$
    .+alpha\\d$
"""

    def test_plugin_compiles_patterns(self) -> None:
        mock_config(self.config_contents)

        plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()

        assert any(type(plugin) is regex_name.RegexReleaseFilter for plugin in plugins)
        plugin = next(
            plugin
            for plugin in plugins
            if isinstance(plugin, regex_name.RegexReleaseFilter)
        )
        assert plugin.patterns == [re.compile(r".+rc\d$"), re.compile(r".+alpha\d$")]

    def test_plugin_check_match(self) -> None:
        mock_config(self.config_contents)

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        pkg = Package("foo", 1)
        pkg._metadata = {
            "info": {"name": "foo", "version": "foo-1.2.0"},
            "releases": {"foo-1.2.0rc2": {}, "foo-1.2.0": {}, "foo-1.2.0alpha2": {}},
        }

        pkg.filter_all_releases(mirror.filters.filter_release_plugins())

        assert pkg.releases == {"foo-1.2.0": {}}


class TestRegexProjectFilter(BasePluginTestCase):
    config_contents = """\
[plugins]
enabled =
    regex_project

[filter_regex]
packages =
    .+-evil$
    .+-neutral$
"""

    def test_plugin_compiles_patterns(self) -> None:
        mock_config(self.config_contents)

        plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()

        assert any(type(plugin) is regex_name.RegexProjectFilter for plugin in plugins)
        plugin = next(
            plugin
            for plugin in plugins
            if isinstance(plugin, regex_name.RegexProjectFilter)
        )
        assert plugin.patterns == [re.compile(r".+-evil$"), re.compile(r".+-neutral$")]

    def test_plugin_check_match(self) -> None:
        mock_config(self.config_contents)

        mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
        mirror.packages_to_sync = {"foo-good": "", "foo-evil": "", "foo-neutral": ""}
        mirror._filter_packages()

        assert list(mirror.packages_to_sync.keys()) == ["foo-good"]
