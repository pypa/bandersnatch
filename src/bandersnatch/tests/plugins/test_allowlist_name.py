from pathlib import Path

import bandersnatch.filter
import bandersnatch.storage
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config

# AllowList Project


def test__allowlist_project__loads__explicitly_enabled() -> None:
    mock_config(contents="""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_project
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()
    names = [plugin.name for plugin in plugins]
    assert names == ["allowlist_project"]
    assert len(plugins) == 1


def test__allowlist_project__loads__default() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_project_plugins()
    names = [plugin.name for plugin in plugins]
    assert "allowlist_project" not in names


def test__allowlist_project__filter__matches__package() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": ""}
    mirror._filter_packages()

    assert "foo" in mirror.packages_to_sync.keys()


def test__allowlist_project__filter__nomatch_package() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": "", "foo2": ""}
    mirror._filter_packages()

    assert "foo" in mirror.packages_to_sync.keys()
    assert "foo2" not in mirror.packages_to_sync.keys()


def test__allowlist_project__filter__name_only() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo==1.2.3
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": "", "foo2": ""}
    mirror._filter_packages()

    assert "foo" in mirror.packages_to_sync.keys()
    assert "foo2" not in mirror.packages_to_sync.keys()


def test__allowlist_project__filter__varying__specifiers() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo==1.2.3
    bar~=3.0,<=1.5
""")
    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {
        "foo": "",
        "bar": "",
        "snu": "",
    }
    mirror._filter_packages()

    assert {"foo": "", "bar": ""} == mirror.packages_to_sync


def test__allowlist_project__filter__commented__out() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_project

[allowlist]
packages =
    foo==1.2.3   # inline comment
#    bar
""")
    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {
        "foo": "",
        "bar": "",
        "snu": "",
    }
    mirror._filter_packages()

    assert {"foo": ""} == mirror.packages_to_sync


# AllowList Release


def test__allowlist_release__loads__explicitly_enabled() -> None:
    mock_config("""\
[plugins]
enabled =
    allowlist_release
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
    names = [plugin.name for plugin in plugins]
    assert names == ["allowlist_release"]
    assert len(plugins) == 1


def test__allowlist_release__doesnt_load__explicitly__disabled() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_package
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
    names = [plugin.name for plugin in plugins]
    assert "allowlist_release" not in names


def test__allowlist_release__filter__matches__release() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_release
[allowlist]
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

    assert pkg.releases == {"1.2.0": {}}


def test__allowlist_release__filter__matches__release__commented__inline() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_release
[allowlist]
packages =
    foo==1.2.0      # some inline comment
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": {}, "1.2.1": {}},
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    assert pkg.releases == {"1.2.0": {}}


def test__allowlist_release__dont__filter__prereleases() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_release
[allowlist]
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

    assert pkg.releases == {"1.1.0a2": {}, "1.1.1beta1": {}, "1.2.0": {}}


def test__allowlist_release__casing__no__affect() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_release
[allowlist]
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

    assert pkg.releases == {"1.2.0": {}}


# AllowList Requirements


def test__allowlist_requirements__loads__explicitly_enabled() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    project_requirements_pinned
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
    names = [plugin.name for plugin in plugins]
    assert names == ["project_requirements_pinned"]
    assert len(plugins) == 1


def test__allowlist_requirements__doesnt_load__explicitly__disabled() -> None:
    mock_config("""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    allowlist_package
""")

    plugins = bandersnatch.filter.LoadedFilters().filter_release_plugins()
    names = [plugin.name for plugin in plugins]
    assert "project_requirements" not in names


def test__allowlist_requirements__filter__matches__release(tmp_path: Path) -> None:
    with open(tmp_path / "requirements.txt", "w") as fh:
        fh.write("""\
#    This is needed for workshop 1
#
foo==1.2.0             # via -r requirements.in
""")

    mock_config(f"""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    project_requirements
    project_requirements_pinned
[allowlist]
requirements_path = {tmp_path}
requirements =
    requirements.txt
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": {}, "1.2.1": {}},
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    assert {"1.2.0": {}} == pkg.releases


def test__allowlist_requirements__filter__matches__release_latest(
    tmp_path: Path,
) -> None:
    with open(tmp_path / "requirements.txt", "w") as fh:
        fh.write("""\
foo==1.2.0             # via -r requirements.in
""")

    mock_config(f"""\
[mirror]
storage-backend = filesystem

[plugins]
enabled =
    project_requirements
    project_requirements_pinned
    latest_release
[latest_release]
keep = 2
[allowlist]
requirements_path = {tmp_path}
requirements =
    requirements.txt
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    pkg = Package("foo", 1)
    pkg._metadata = {
        "info": {"name": "foo"},
        "releases": {"1.2.0": {}, "1.2.1": {}, "1.2.2": {}},
    }

    pkg.filter_all_releases(mirror.filters.filter_release_plugins())

    assert {"1.2.0": {}} == pkg.releases


def test__allowlist_requirements__filter__find_files(tmp_path: Path) -> None:
    absolute_file_path = tmp_path / "requirements.txt"
    with open(absolute_file_path, "w") as fh:
        fh.write("""\
#    This is needed for workshop 1
#
foo==1.2.0             # via -r requirements.in
""")

    mock_config(f"""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    project_requirements
[allowlist]
requirements =
    {absolute_file_path}
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": "", "bar": "", "baz": ""}
    mirror._filter_packages()
    assert {"foo": ""} == mirror.packages_to_sync


def test__allowlist_requirements__filter__requirements__pip__options(
    tmp_path: Path,
) -> None:
    absolute_file_path = tmp_path / "requirements.txt"
    with open(absolute_file_path, "w") as fh:
        fh.write("""\
--extra-index-url https://self-hosted-foo.netname/simple
--trusted-host self-hosted-foo.netname
foo==1.2.0             # via -r requirements.in
""")

    mock_config(f"""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    project_requirements
[allowlist]
requirements =
    {absolute_file_path}
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": "", "bar": "", "baz": ""}
    mirror._filter_packages()
    assert {"foo": ""} == mirror.packages_to_sync


def test__allowlist_requirements__filter__find__glob__files(tmp_path: Path) -> None:
    with open(tmp_path / "requirements-project1.txt", "w") as fh:
        fh.write("""\
#
foo==1.2.0             # via -r requirements.in
""")

    with open(tmp_path / "requirements-project2.txt", "w") as fh:
        fh.write("""\
#
bar==2.3.0             # via -r requirements.in
""")

    with open(tmp_path / "project3.txt", "w") as fh:
        fh.write("""\
#
baz==4.5.1             # via -r requirements.in
""")

    mock_config(f"""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    project_requirements
[allowlist]
requirements_path = {tmp_path}
requirements =
    # Importing all the requirements-*.txt from the chosen folder
    requirements-*.txt
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": "", "bar": "", "baz": ""}
    mirror._filter_packages()

    assert "foo" in mirror.packages_to_sync
    assert "bar" in mirror.packages_to_sync
    assert "baz" not in mirror.packages_to_sync


def test__allowlist_requirements__filter__requirements__utf16__encoding(
    tmp_path: Path,
) -> None:
    absolute_file_path = tmp_path / "requirements.txt"
    with open(absolute_file_path, "w", encoding="UTF-16") as fh:
        fh.write("""\
foo==1.2.0             # via -r requirements.in
""")

    mock_config(f"""\
[mirror]
storage-backend = filesystem
workers = 2

[plugins]
enabled =
    project_requirements
[allowlist]
requirements =
    {absolute_file_path}
""")

    mirror = BandersnatchMirror(Path("."), Master(url="https://foo.bar.com"))
    mirror.packages_to_sync = {"foo": "", "bar": "", "baz": ""}
    mirror._filter_packages()
    assert {"foo": ""} == mirror.packages_to_sync
