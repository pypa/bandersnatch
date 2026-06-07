import re
from pathlib import Path

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_filter_plugins import regex_name

# Regex Release Filter

_REGEX_RELEASE_CONFIG = """\
[plugins]
enabled =
    regex_release

[filter_regex]
releases =
    .+rc\\d$
    .+alpha\\d$
"""


def test_regex_release_compiles_patterns() -> None:
    mock_config(_REGEX_RELEASE_CONFIG)

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()

    assert any(type(plugin) is regex_name.RegexReleaseFilter for plugin in plugins)
    plugin = next(
        plugin
        for plugin in plugins
        if isinstance(plugin, regex_name.RegexReleaseFilter)
    )
    assert plugin.patterns == [re.compile(r".+rc\d$"), re.compile(r".+alpha\d$")]


def test_regex_release_check_match() -> None:
    mock_config(_REGEX_RELEASE_CONFIG)

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo", "version": "foo-1.2.0"},
        "releases": {"foo-1.2.0rc2": {}, "foo-1.2.0": {}, "foo-1.2.0alpha2": {}},
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    assert pkg.releases == {"foo-1.2.0": {}}


# Regex Project Filter

_REGEX_PROJECT_CONFIG = """\
[plugins]
enabled =
    regex_project

[filter_regex]
packages =
    .+-evil$
    .+-neutral$
"""


def test_regex_project_compiles_patterns() -> None:
    mock_config(_REGEX_PROJECT_CONFIG)

    plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()

    assert any(type(plugin) is regex_name.RegexProjectFilter for plugin in plugins)
    plugin = next(
        plugin
        for plugin in plugins
        if isinstance(plugin, regex_name.RegexProjectFilter)
    )
    assert plugin.patterns == [re.compile(r".+-evil$"), re.compile(r".+-neutral$")]


def test_regex_project_check_match() -> None:
    mock_config(_REGEX_PROJECT_CONFIG)

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo-good": "", "foo-evil": "", "foo-neutral": ""}
    mirror._filter_packages()

    assert list(mirror.packages_to_sync.keys()) == ["foo-good"]
