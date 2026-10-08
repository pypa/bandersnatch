from collections.abc import Iterator
from pathlib import Path

import pytest

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_filter_plugins.metadata_filter import (
    RegexProjectMetadataFilter,
    RegexReleaseFileMetadataFilter,
    SizeProjectMetadataFilter,
    VersionsCountProjectMetadataFilter,
)


def test__size__plugin__loads__and__initializes() -> None:
    mock_config("""\
[plugins]
enabled =
    size_project_metadata

[size_project_metadata]
max_package_size = 1G
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_metadata_plugins()
    names = [plugin.name for plugin in plugins]
    assert names == ["size_project_metadata"]
    assert len(plugins) == 1
    assert isinstance(plugins[0], SizeProjectMetadataFilter)
    plugin = next(p for p in plugins if isinstance(p, SizeProjectMetadataFilter))
    assert plugin.initialized


def test__filter__size__only() -> None:
    mock_config("""\
[plugins]
enabled =
    size_project_metadata

[size_project_metadata]
max_package_size = 2K
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))

    # Test that under-sized project is allowed
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": [{"size": 1024}], "1.2.1": {}},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test that over-sized project is blocked
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": [{"size": 1024}], "1.2.1": [{"size": 1025}]},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is False


def test__filter__size__or__allowlist() -> None:
    mock_config("""\
[plugins]
enabled =
    size_project_metadata

[size_project_metadata]
max_package_size = 2K

[allowlist]
packages =
    foo
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))

    # Test that under-sized, allowlisted project is allowed
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": [{"size": 1024}], "1.2.1": {}},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test that over-sized, allowlisted project is allowed
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": [{"size": 1024}], "1.2.1": [{"size": 1025}]},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test that under-sized, non-allowlisted project is allowed
    pkg = Package("bar", 1)
    pkg._metadata = {
        "info": {"name": "bar"},
        "releases": {"1.2.0": [{"size": 1024}], "1.2.1": {}},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test that over-sized, non-allowlisted project is blocked
    pkg = Package("bar", 1)
    pkg._metadata = {
        "info": {"name": "bar"},
        "releases": {"1.2.0": [{"size": 1024}], "1.2.1": [{"size": 1025}]},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is False


def test__versions_count__plugin__loads__and__initializes() -> None:
    mock_config("""\
[plugins]
enabled =
    versions_count_project_metadata

[versions_count_project_metadata]
min_versions = 3
max_versions = 10
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_metadata_plugins()
    names = [plugin.name for plugin in plugins]
    assert "versions_count_project_metadata" in names
    plugin = next(
        p for p in plugins if isinstance(p, VersionsCountProjectMetadataFilter)
    )
    assert plugin.initialized
    assert plugin.min_versions == 3
    assert plugin.max_versions == 10


def test__filter__versions_count() -> None:
    mock_config("""\
[plugins]
enabled =
    versions_count_project_metadata

[versions_count_project_metadata]
min_versions = 3
max_versions = 5
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))

    # Test under min (2 versions)
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": [], "2.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is False

    # Test at min (3 versions)
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": [], "2.0": [], "3.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test between min and max (4 versions)
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": [], "2.0": [], "3.0": [], "4.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test at max (5 versions)
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": [], "2.0": [], "3.0": [], "4.0": [], "5.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test above max (6 versions)
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": [], "2.0": [], "3.0": [], "4.0": [], "5.0": [], "6.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is False


def test__filter__versions_count__allowlist() -> None:
    mock_config("""\
[plugins]
enabled =
    versions_count_project_metadata

[versions_count_project_metadata]
min_versions = 3
max_versions = 5

[allowlist]
packages =
    foo
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))

    # Test that under-sized version count, allowlisted is allowed (bypass)
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test that over-sized version count, allowlisted is allowed (bypass)
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": [], "2.0": [], "3.0": [], "4.0": [], "5.0": [], "6.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is True

    # Test that non-allowlisted packages still get filtered correctly
    pkg = Package("bar", 1)
    pkg._metadata = {
        "info": {"name": "bar"},
        "releases": {"1.0": []},
    }
    assert pkg.filter_metadata(mirror.filters.filter_metadata_plugins()) is False


def test__versions_count__plugin__non_integer_config_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_config("""\
[plugins]
enabled =
    versions_count_project_metadata

[versions_count_project_metadata]
min_versions = not_a_number
max_versions = 5
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_metadata_plugins()
    plugin = next(
        p for p in plugins if isinstance(p, VersionsCountProjectMetadataFilter)
    )
    assert plugin.initialized
    assert any(
        "min_versions/max_versions must be integers" in record.message
        for record in caplog.records
    )
    # Plugin should be deactivated on invalid configuration.
    assert plugin.filter({"info": {"name": "foo"}, "releases": {"1.0": []}}) is True


def test__versions_count__plugin__invalid_limits_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_config("""\
[plugins]
enabled =
    versions_count_project_metadata

[versions_count_project_metadata]
min_versions = 10
max_versions = 5
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_metadata_plugins()
    plugin = next(
        p for p in plugins if isinstance(p, VersionsCountProjectMetadataFilter)
    )
    assert plugin.initialized
    assert any(
        "min_versions is greater than max_versions" in record.message
        for record in caplog.records
    )
    # Plugin should be deactivated on invalid configuration.
    assert plugin.filter({"info": {"name": "foo"}, "releases": {"1.0": []}}) is True


@pytest.fixture
def reset_regex_metadata_filters() -> Iterator[None]:
    classes = (RegexProjectMetadataFilter, RegexReleaseFileMetadataFilter)
    for cls in classes:
        cls.patterns = {}
        cls.initialized = False
    yield
    for cls in classes:
        cls.patterns = {}
        cls.initialized = False


def _release_files(*filenames: str) -> Package:
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.0": [{"filename": name} for name in filenames]},
    }
    return pkg


def _filter_release_filenames(pkg: Package, *, search: bool) -> list[str]:
    plugins = bandersnatch.filter.LoadedFilters().filter_release_file_plugins()
    assert len(plugins) == 1
    plugin = plugins[0]
    assert isinstance(plugin, RegexReleaseFileMetadataFilter)
    assert plugin.search is search
    assert "search" not in plugin.patterns
    pkg.filter_all_releases_files(plugins)
    return [item["filename"] for item in pkg.releases.get("1.0", [])]


def test__regex_release_file__search__matches_within_filename(
    reset_regex_metadata_filters: None,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_release_file_metadata

[regex_release_file_metadata]
search = true
none:release_file.filename =
    macosx_
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_file_plugins()
    plugin = plugins[0]
    assert isinstance(plugin, RegexReleaseFileMetadataFilter)
    assert plugin.search is True
    assert "search" not in plugin.patterns
    pkg = _release_files(
        "foo-1.0-macosx_x86_64.whl",
        "foo-1.0.tar.gz",
        "macosx_10_15_x86_64.whl",
    )
    pkg.filter_all_releases_files(plugins)
    assert [item["filename"] for item in pkg.releases["1.0"]] == ["foo-1.0.tar.gz"]


def test__regex_release_file__defaults_to_match(
    reset_regex_metadata_filters: None,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_release_file_metadata

[regex_release_file_metadata]
none:release_file.filename =
    macosx_
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_file_plugins()
    plugin = plugins[0]
    assert isinstance(plugin, RegexReleaseFileMetadataFilter)
    assert plugin.search is False
    pkg = _release_files(
        "foo-1.0-macosx_x86_64.whl",
        "foo-1.0.tar.gz",
        "macosx_10_15_x86_64.whl",
    )
    pkg.filter_all_releases_files(plugins)
    assert [item["filename"] for item in pkg.releases["1.0"]] == [
        "foo-1.0-macosx_x86_64.whl",
        "foo-1.0.tar.gz",
    ]


def test__regex_release_file__search_false_matches_from_start(
    reset_regex_metadata_filters: None,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_release_file_metadata

[regex_release_file_metadata]
search = false
none:release_file.filename =
    macosx_
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_file_plugins()
    plugin = plugins[0]
    assert isinstance(plugin, RegexReleaseFileMetadataFilter)
    assert plugin.search is False
    pkg = _release_files("foo-1.0-macosx_x86_64.whl", "macosx_10_15_x86_64.whl")
    pkg.filter_all_releases_files(plugins)
    assert [item["filename"] for item in pkg.releases["1.0"]] == [
        "foo-1.0-macosx_x86_64.whl",
    ]


def test__regex_release_file__search__keeps_caret_anchor(
    reset_regex_metadata_filters: None,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_release_file_metadata

[regex_release_file_metadata]
search = true
none:release_file.filename =
    ^macosx_
""")

    pkg = _release_files(
        "foo-1.0-macosx_x86_64.whl",
        "foo-1.0.tar.gz",
        "macosx_10_15_x86_64.whl",
    )
    assert _filter_release_filenames(pkg, search=True) == [
        "foo-1.0-macosx_x86_64.whl",
        "foo-1.0.tar.gz",
    ]


def test__regex_release_file__search__all_mode_matches_within_filename(
    reset_regex_metadata_filters: None,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_release_file_metadata

[regex_release_file_metadata]
search = true
all:release_file.filename =
    macosx_
""")

    pkg = _release_files("foo-1.0-macosx_x86_64.whl")
    assert _filter_release_filenames(pkg, search=True) == ["foo-1.0-macosx_x86_64.whl"]


def test__regex_release_file__invalid_search_keeps_match(
    reset_regex_metadata_filters: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_release_file_metadata

[regex_release_file_metadata]
search = not-a-boolean
none:release_file.filename =
    macosx_
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_file_plugins()
    plugin = plugins[0]
    assert isinstance(plugin, RegexReleaseFileMetadataFilter)
    assert plugin.search is False
    assert "search" not in plugin.patterns
    assert any(
        "search must be a boolean" in record.message for record in caplog.records
    )
    pkg = _release_files("foo-1.0-macosx_x86_64.whl", "macosx_10_15_x86_64.whl")
    pkg.filter_all_releases_files(plugins)
    assert [item["filename"] for item in pkg.releases["1.0"]] == [
        "foo-1.0-macosx_x86_64.whl",
    ]


def test__regex_project__search__matches_within_name(
    reset_regex_metadata_filters: None,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_project_metadata

[regex_project_metadata]
search = true
none:info.name =
    -nightly$
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_metadata_plugins()
    plugin = plugins[0]
    assert isinstance(plugin, RegexProjectMetadataFilter)
    assert plugin.search is True
    assert "search" not in plugin.patterns

    blocked = Package("foo-nightly", 1)
    blocked._metadata = {"info": {"name": "foo-nightly"}, "releases": {}}
    assert blocked.filter_metadata(plugins) is False

    kept = Package("foo", 1)
    kept._metadata = {"info": {"name": "foo"}, "releases": {}}
    assert kept.filter_metadata(plugins) is True


def test__regex_release_file__search_alone_is_not_a_pattern(
    reset_regex_metadata_filters: None,
) -> None:
    mock_config("""\
[plugins]
enabled =
    regex_release_file_metadata

[regex_release_file_metadata]
search = true
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_file_plugins()
    plugin = plugins[0]
    assert isinstance(plugin, RegexReleaseFileMetadataFilter)
    assert plugin.search is True
    assert plugin.patterns == {}
    pkg = _release_files("foo-1.0-macosx_x86_64.whl")
    pkg.filter_all_releases_files(plugins)
    assert [item["filename"] for item in pkg.releases["1.0"]] == [
        "foo-1.0-macosx_x86_64.whl",
    ]
