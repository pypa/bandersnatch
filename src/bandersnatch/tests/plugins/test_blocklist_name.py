from pathlib import Path

import bandersnatch.filter
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config

# BlockList Project


def test__blocklist_project__loads__explicitly_enabled() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_project
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()
    names = [plugin.name for plugin in plugins]
    assert names == ["blocklist_project"]
    assert len(plugins) == 1


def test__blocklist_project__doesnt_load__explicitly__disabled() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_release
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()
    names = [plugin.name for plugin in plugins]
    assert "blocklist_project" not in names


def test__blocklist_project__loads__default() -> None:
    mock_config("""\
[blocklist]
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()
    names = [plugin.name for plugin in plugins]
    assert "blocklist_project" not in names


def test__blocklist_project__filter__matches__package() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_project
[blocklist]
packages =
    foo
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": ""}
    mirror._filter_packages()

    assert "foo" not in mirror.packages_to_sync.keys()


def test__blocklist_project__filter__nomatch_package() -> None:
    mock_config("""\
        [blocklist]
        plugins =
            blocklist_project
        packages =
            foo
        """)

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo2": ""}
    mirror._filter_packages()

    assert "foo2" in mirror.packages_to_sync.keys()


def test__blocklist_project__filter__name_only() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    blocklist_project

[blocklist]
packages =
    foo==1.2.3
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": "", "foo2": ""}
    mirror._filter_packages()

    assert "foo" in mirror.packages_to_sync.keys()
    assert "foo2" in mirror.packages_to_sync.keys()


def test__blocklist_project__filter__varying__specifiers() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    blocklist_project

[blocklist]
packages =
    foo==1.2.3
    bar~=3.0,<=1.5
    snu
""")
    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {
        "foo": "",
        "foo2": "",
        "bar": "",
        "snu": "",
    }
    mirror._filter_packages()

    assert {"foo": "", "foo2": "", "bar": ""} == mirror.packages_to_sync


# BlockList Release


def test__blocklist_release__loads__explicitly_enabled() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_release
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
    names = [plugin.name for plugin in plugins]
    assert names == ["blocklist_release"]
    assert len(plugins) == 1


def test__blocklist_release__doesnt_load__explicitly__disabled() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_package
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
    names = [plugin.name for plugin in plugins]
    assert "blocklist_release" not in names


def test__blocklist_release__filter__matches__release() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_release
[blocklist]
packages =
    foo==1.2.0
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": {}, "1.2.1": {}},
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    assert pkg.releases == {"1.2.1": {}}


def test__blocklist_release__dont__filter__prereleases() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_release
[blocklist]
packages =
    foo<=1.2.0
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {
            "1.1.0a2": {},
            "1.1.1beta1": {},
            "1.2.0": {},
            "1.2.1": {},
            "1.2.2alpha3": {},
            "1.2.3rc1": {},
        },
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    assert pkg.releases == {"1.2.1": {}, "1.2.2alpha3": {}, "1.2.3rc1": {}}


def test__blocklist_release__casing__no__affect() -> None:
    mock_config("""\
[plugins]
enabled =
    blocklist_release
[blocklist]
packages =
    Foo<=1.2.0
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": {}, "1.2.1": {}},
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    assert pkg.releases == {"1.2.1": {}}
