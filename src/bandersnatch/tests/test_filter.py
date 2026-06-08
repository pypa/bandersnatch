from pathlib import Path

import pytest

from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.tests.mock_config import mock_config

from bandersnatch.filter import (  # isort:skip
    Filter,
    FilterProjectPlugin,
    FilterReleasePlugin,
    LoadedFilters,
)


@pytest.fixture(autouse=True)
def isolated_tmpdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def test__filter_project_plugins__loads() -> None:
    mock_config("""\
[plugins]
enabled = all
""")
    builtin_plugin_names = [
        "blocklist_project",
        "regex_project",
        "allowlist_project",
    ]

    plugins = LoadedFilters().filter_project_plugins()
    names = [plugin.name for plugin in plugins]
    for name in builtin_plugin_names:
        assert name in names


def test__filter_release_plugins__loads() -> None:
    mock_config("""\
[plugins]
enabled = all
""")
    builtin_plugin_names = [
        "blocklist_release",
        "prerelease_release",
        "regex_release",
        "latest_release",
    ]

    plugins = LoadedFilters().filter_release_plugins()
    names = [plugin.name for plugin in plugins]
    for name in builtin_plugin_names:
        assert name in names


def test__filter_no_plugin() -> None:
    mock_config("""\
[plugins]
enabled =
""")

    plugins = LoadedFilters().filter_release_plugins()
    assert len(plugins) == 0

    plugins = LoadedFilters().filter_project_plugins()
    assert len(plugins) == 0


def test__filter_base_classes() -> None:
    """Test the base filter classes."""

    plugin = Filter()
    assert plugin.name == "filter"
    try:
        plugin.initialize_plugin()
        error = False
    except Exception:
        error = True
    assert not error

    plugin = FilterReleasePlugin()
    assert isinstance(plugin, Filter)
    assert plugin.name == "release_plugin"
    try:
        plugin.filter({})
        error = False
    except Exception:
        error = True
    assert not error

    plugin = FilterProjectPlugin()
    assert isinstance(plugin, Filter)
    assert plugin.name == "project_plugin"
    try:
        result = plugin.check_match(key="value")
        error = False
        assert isinstance(result, bool)
    except Exception:
        error = True
    assert not error


def test_deprecated_keys() -> None:
    instance = BandersnatchConfig()
    instance.read_string("[allowlist]\npackages=foo\n[blocklist]\npackages=bar\n")

    plugin = Filter()
    assert plugin.allowlist.name == "allowlist"
    assert plugin.blocklist.name == "blocklist"


def test__filter_project_blocklist_allowlist__pep503_normalize() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_project
    allowlist_project

[blocklist]
packages =
    SampleProject
    trove----classifiers

[allowlist]
packages =
    SampleProject
    trove----classifiers
""")

    plugins = {
        plugin.name: plugin for plugin in LoadedFilters().filter_project_plugins()
    }

    assert plugins["blocklist_project"].check_match(name="sampleproject")
    assert plugins["blocklist_project"].check_match(name="trove-classifiers")
    assert not plugins["allowlist_project"].check_match(name="sampleproject")
    assert not plugins["allowlist_project"].check_match(name="trove-classifiers")
