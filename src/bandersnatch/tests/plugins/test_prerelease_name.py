import re
from pathlib import Path

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_filter_plugins import prerelease_name

_PRERELEASE_CONFIG = """\
[plugins]
enabled =
    prerelease_release
"""

_DUCKDB_EXCEPTION_CONFIG = """\
[filter_prerelease]
packages =
    duckdb
"""


def test_prerelease_plugin_includes_predefined_patterns() -> None:
    mock_config(_PRERELEASE_CONFIG)

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()

    assert any(type(plugin) is prerelease_name.PreReleaseFilter for plugin in plugins)
    plugin = next(
        plugin
        for plugin in plugins
        if isinstance(plugin, prerelease_name.PreReleaseFilter)
    )
    expected_patterns = [
        re.compile(pattern_string) for pattern_string in plugin.PRERELEASE_PATTERNS
    ]
    assert plugin.patterns == expected_patterns


def _check_filter(package: str) -> bool:
    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package(package, serial=1)
    pkg._metadata = {
        "info": {"name": package, "version": "1.2.0"},
        "releases": {
            "1.2.0alpha1": {},
            "1.2.0a2": {},
            "1.2.0beta1": {},
            "1.2.0b2": {},
            "1.2.0rc1": {},
            "1.2.0.dev912": {},
            "1.2.0": {},
        },
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    return bool(pkg.releases == {"1.2.0": {}})


def test_prerelease_plugin_filter_all() -> None:
    mock_config(_PRERELEASE_CONFIG)
    assert _check_filter("foo") is True
    assert _check_filter("duckdb") is True


def test_prerelease_plugin_filter_packages() -> None:
    mock_config(_PRERELEASE_CONFIG + _DUCKDB_EXCEPTION_CONFIG)
    assert _check_filter("foo") is False
    assert _check_filter("duckdb") is True
