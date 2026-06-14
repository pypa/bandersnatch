from pathlib import Path

import pytest

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_filter_plugins.metadata_filter import (
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
    assert not plugin.initialized
    assert any(
        "min_versions is greater than max_versions" in record.message
        for record in caplog.records
    )
