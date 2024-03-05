import os.path
import sys
import unittest.mock as mock
from collections.abc import Iterator
from os import sep
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn

import pytest
from freezegun import freeze_time

from bandersnatch import utils
from bandersnatch.configuration import BandersnatchConfig, Singleton
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.simple import SimpleFormats
from bandersnatch.tests.test_simple_fixtures import SIXTYNINE_METADATA
from bandersnatch.utils import WINDOWS, make_time_stamp

EXPECTED_REL_HREFS = (
    '<a href="../../packages/2.7/f/foo/foo.whl#sha256=e3b0c44298fc1c149afbf4c8996fb924'
    + '27ae41e4649b934ca495991b7852b855">foo.whl</a><br/>\n'
    '    <a href="../../packages/any/f/foo/foo.zip#sha256=e3b0c44298fc1c149afbf4c8996f'
    + 'b92427ae41e4649b934ca495991b7852b855">foo.zip</a><br/>'
)


class JsonDict(dict):
    """Class to fake the object returned from requests lib in master.get()"""

    def json(self) -> "JsonDict":
        return self

    def iter_content(*args: Any, **kwargs: Any) -> Iterator[bytes]:
        yield b"abcdefg69"


# master.get() returned data needs to have a .json() method and iter_content
FAKE_RELEASE_DATA = JsonDict(
    {
        "info": {"name": "foo", "version": "0.1"},
        "last_serial": 654_321,
        "releases": {
            "0.1": [
                {
                    "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                    "filename": "foo.zip",
                    "digests": {
                        "md5": "ebdad75ed9a852bbfd9be4c18bf76d00",
                        "sha256": (
                            "746e6da7eda8b75af9acbdd29808473df08a00362981f0949023e387da1a4734"
                        ),
                    },
                    "md5_digest": "ebdad75ed9a852bbfd9be4c18bf76d00",
                    "packagetype": "sdist",
                    "size": 1234,
                    "upload_time_iso_8601": "2000-01-01T01:23:45.123456Z",
                }
            ]
        },
    }
)


def touch_files(paths: list[Path]) -> None:
    for path in paths:
        if not path.parent.exists():
            path.parent.mkdir(parents=True)
        with path.open("wb") as pfp:
            pfp.close()


def test_limit_workers() -> None:
    try:
        BandersnatchMirror(Path("/tmp"), mock.Mock(), workers=11)
    except ValueError:
        pass


def test_mirror_loads_serial(tmpdir: Path) -> None:
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("5")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    m = BandersnatchMirror(tmpdir, mock.Mock())
    assert m.synced_serial == 1234


def test_mirror_recovers_from_inconsistent_serial(tmpdir: Path) -> None:
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    m = BandersnatchMirror(tmpdir, mock.Mock())
    assert m.synced_serial == 0


def test_mirror_generation_3_resets_status_files(tmpdir: Path) -> None:
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("2")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("asdf")

    m = BandersnatchMirror(tmpdir, mock.Mock())
    assert m.synced_serial == 0
    assert not os.path.exists(str(tmpdir / "todo"))
    assert not os.path.exists(str(tmpdir / "status"))
    assert open(str(tmpdir / "generation")).read() == "5"


def test_mirror_generation_4_resets_status_files(tmpdir: Path) -> None:
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("4")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("asdf")

    m = BandersnatchMirror(tmpdir, mock.Mock())
    assert m.synced_serial == 0
    assert not os.path.exists(str(tmpdir / "todo"))
    assert not os.path.exists(str(tmpdir / "status"))
    assert open(str(tmpdir / "generation")).read() == "5"


def test_mirror_filter_packages_match(tmpdir: Path) -> None:
    """
    Packages that exist in the blocklist should be removed from the list of
    packages to sync.
    """
    test_configuration = """\
[plugins]
enabled =
    blocklist_project
[blocklist]
packages =
    example1
"""
    Singleton._instances = {}
    with open("test.conf", "w") as testconfig_handle:
        testconfig_handle.write(test_configuration)
    BandersnatchConfig("test.conf")
    m = BandersnatchMirror(tmpdir, mock.Mock())
    m.packages_to_sync = {"example1": "", "example2": ""}
    m._filter_packages()
    assert "example1" not in m.packages_to_sync.keys()


def test_mirror_filter_packages_nomatch_package_with_spec(tmpdir: Path) -> None:
    """
    Package lines with a PEP440 spec on them should not be filtered from the
    list of packages.
    """
    test_configuration = """\
[plugins]
enable =
    blocklist_project
[blocklist]
packages =
    example3>2.0.0
"""
    Singleton._instances = {}
    with open("test.conf", "w") as testconfig_handle:
        testconfig_handle.write(test_configuration)
    BandersnatchConfig("test.conf")
    m = BandersnatchMirror(tmpdir, mock.Mock())
    m.packages_to_sync = {"example1": "", "example3": ""}
    m._filter_packages()
    assert "example3" in m.packages_to_sync.keys()


def test_mirror_removes_empty_todo_list(tmpdir: Path) -> None:
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("3")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("")
    BandersnatchMirror(tmpdir, mock.Mock())
    assert not os.path.exists(str(tmpdir / "todo"))


def test_mirror_removes_broken_todo_list(tmpdir: Path) -> None:
    with open(str(tmpdir / "generation"), "w") as generation:
        generation.write("3")
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("foo")
    BandersnatchMirror(tmpdir, mock.Mock())
    assert not os.path.exists(str(tmpdir / "todo"))


def test_mirror_removes_old_status_and_todo_inits_generation(tmpdir: Path) -> None:
    with open(str(tmpdir / "status"), "w") as status:
        status.write("1234")
    with open(str(tmpdir / "todo"), "w") as status:
        status.write("foo")
    BandersnatchMirror(tmpdir, mock.Mock())
    assert not os.path.exists(str(tmpdir / "todo"))
    assert not os.path.exists(str(tmpdir / "status"))
    assert open(str(tmpdir / "generation")).read().strip() == "5"


def test_mirror_with_same_homedir_needs_lock(
    mirror: BandersnatchMirror, tmpdir: Path
) -> None:
    try:
        BandersnatchMirror(mirror.homedir, mirror.master)
    except RuntimeError:
        pass
    BandersnatchMirror(mirror.homedir / "test", mirror.master)


@pytest.mark.asyncio
async def test_mirror_empty_master_gets_index(mirror: BandersnatchMirror) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={})  # type: ignore
    await mirror.synchronize()

    assert """\
last-modified
local-stats
local-stats{0}days
packages
simple
simple{0}index.html
simple{0}index.v1_html
simple{0}index.v1_json""".format(
        sep
    ) == utils.find(
        mirror.webdir
    )
    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
  </body>
</html>"""
    )
    assert open("status").read() == "0"


@pytest.mark.asyncio
async def test_mirror_empty_resume_from_todo_list(mirror: BandersnatchMirror) -> None:
    with open("todo", "w") as todo:
        todo.write("20\nfoobar 1")

    await mirror.synchronize()

    expected = """\
.lock
generation
status
web
web{0}last-modified
web{0}local-stats
web{0}local-stats{0}days
web{0}packages
web{0}packages{0}2.7
web{0}packages{0}2.7{0}f
web{0}packages{0}2.7{0}f{0}foo
web{0}packages{0}2.7{0}f{0}foo{0}foo.whl
web{0}packages{0}any
web{0}packages{0}any{0}f
web{0}packages{0}any{0}f{0}foo
web{0}packages{0}any{0}f{0}foo{0}foo.zip
web{0}simple
web{0}simple{0}foobar
web{0}simple{0}foobar{0}index.html
web{0}simple{0}foobar{0}index.v1_html
web{0}simple{0}foobar{0}index.v1_json
web{0}simple{0}index.html
web{0}simple{0}index.v1_html
web{0}simple{0}index.v1_json""".format(
        sep
    )
    if WINDOWS:
        expected = expected.replace(".lock\n", "")
    assert expected == utils.find(mirror.homedir)

    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foobar/">foobar</a><br/>
  </body>
</html>"""
    )
    assert open("status").read() == "20"


@pytest.mark.asyncio
async def test_mirror_sync_package_skip_index(mirror: BandersnatchMirror) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={"foo": 1})  # type: ignore
    mirror.json_save = True
    # Recall bootstrap so we have the json dirs
    mirror._bootstrap()
    await mirror.synchronize(sync_simple_index=False)

    assert """\
json{0}foo
last-modified
packages{0}2.7{0}f{0}foo{0}foo.whl
packages{0}any{0}f{0}foo{0}foo.zip
pypi{0}foo{0}json
simple{0}foo{0}index.html
simple{0}foo{0}index.v1_html
simple{0}foo{0}index.v1_json""".format(
        sep
    ) == utils.find(
        mirror.webdir, dirs=False
    )
    assert open("status", "rb").read() == b"1"


@pytest.mark.asyncio
async def test_mirror_sync_package(mirror: BandersnatchMirror) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={"foo": 1})  # type: ignore
    mirror.json_save = True
    # Recall bootstrap so we have the json dirs
    mirror._bootstrap()
    await mirror.synchronize()

    assert """\
json{0}foo
last-modified
packages{0}2.7{0}f{0}foo{0}foo.whl
packages{0}any{0}f{0}foo{0}foo.zip
pypi{0}foo{0}json
simple{0}foo{0}index.html
simple{0}foo{0}index.v1_html
simple{0}foo{0}index.v1_json
simple{0}index.html
simple{0}index.v1_html
simple{0}index.v1_json""".format(
        sep
    ) == utils.find(
        mirror.webdir, dirs=False
    )
    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )
    assert open("status", "rb").read() == b"1"


@pytest.mark.asyncio
async def test_mirror_sync_package_error_no_early_exit(
    mirror: BandersnatchMirror,
) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={"foo": 1})  # type: ignore
    mirror.errors = True
    changed_packages = await mirror.synchronize()

    expected = """\
.lock
generation
todo
web{0}packages{0}2.7{0}f{0}foo{0}foo.whl
web{0}packages{0}any{0}f{0}foo{0}foo.zip
web{0}simple{0}foo{0}index.html
web{0}simple{0}foo{0}index.v1_html
web{0}simple{0}foo{0}index.v1_json
web{0}simple{0}index.html
web{0}simple{0}index.v1_html
web{0}simple{0}index.v1_json""".format(
        sep
    )
    if WINDOWS:
        expected = expected.replace(".lock\n", "")
    assert expected == utils.find(mirror.homedir, dirs=False)
    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )

    assert open("todo").read() == "1\n"

    # Check the returned dict is accurate
    expected_dict = {
        "foo": {
            "web{0}packages{0}2.7{0}f{0}foo{0}foo.whl".format(sep),
            "web{0}packages{0}any{0}f{0}foo{0}foo.zip".format(sep),
        }
    }
    assert changed_packages == expected_dict


# TODO: Fix - Raises SystemExit but pytest does not like asyncio tasks
@pytest.mark.asyncio
async def mirror_sync_package_error_early_exit(mirror: BandersnatchMirror) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={"foo": 1})  # type: ignore

    with Path("web/simple/index.html").open("wb") as index:
        index.write(b"old index")
    mirror.errors = True
    mirror.stop_on_error = True
    with pytest.raises(SystemExit):
        await mirror.synchronize()

    assert """\
.lock
generation
todo
web{0}packages{0}any{0}f{0}foo{0}foo.zip
web{0}simple{0}foo{0}index.html
web{0}simple{0}index.html""".format(
        sep
    ) == utils.find(
        mirror.homedir, dirs=False
    )
    assert open("web{0}simple{0}index.html".format(sep)).read() == "old index"
    assert open("todo").read() == "1\n"


@pytest.mark.asyncio
async def test_mirror_sync_package_with_hash(
    mirror_hash_index: BandersnatchMirror,
) -> None:
    mirror_hash_index.master.all_packages = mock.AsyncMock(  # type: ignore
        return_value={"foo": 1}
    )
    await mirror_hash_index.synchronize()

    assert """\
last-modified
packages{0}2.7{0}f{0}foo{0}foo.whl
packages{0}any{0}f{0}foo{0}foo.zip
simple{0}f{0}foo{0}index.html
simple{0}f{0}foo{0}index.v1_html
simple{0}f{0}foo{0}index.v1_json
simple{0}index.html
simple{0}index.v1_html
simple{0}index.v1_json""".format(
        sep
    ) == utils.find(
        mirror_hash_index.webdir, dirs=False
    )
    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )
    assert open("status").read() == "1"


@pytest.mark.asyncio
async def test_mirror_sync_package_download_mirror(
    mirror: BandersnatchMirror,
) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={"foo": 1})  # type: ignore
    mirror.json_save = True
    # Recall bootstrap so we have the json dirs
    mirror._bootstrap()
    # This download mirror URL works, forcing not to fallback
    mirror.download_mirror = "https://pypi-mirror.example.com/pypi"
    mirror.download_mirror_no_fallback = True
    await mirror.synchronize()

    assert """\
json{0}foo
last-modified
packages{0}2.7{0}f{0}foo{0}foo.whl
packages{0}any{0}f{0}foo{0}foo.zip
pypi{0}foo{0}json
simple{0}foo{0}index.html
simple{0}foo{0}index.v1_html
simple{0}foo{0}index.v1_json
simple{0}index.html
simple{0}index.v1_html
simple{0}index.v1_json""".format(
        sep
    ) == utils.find(
        mirror.webdir, dirs=False
    )
    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )
    assert open("status", "rb").read() == b"1"


@pytest.mark.asyncio
async def test_mirror_sync_package_download_mirror_fallback(
    mirror: BandersnatchMirror,
) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={"foo": 1})  # type: ignore
    mirror.json_save = True
    # Recall bootstrap so we have the json dirs
    mirror._bootstrap()
    # This download mirror URL does not work, should fallback to normal logic
    mirror.download_mirror = "https://not-working.example.com/pypi"
    await mirror.synchronize()

    assert """\
json{0}foo
last-modified
packages{0}2.7{0}f{0}foo{0}foo.whl
packages{0}any{0}f{0}foo{0}foo.zip
pypi{0}foo{0}json
simple{0}foo{0}index.html
simple{0}foo{0}index.v1_html
simple{0}foo{0}index.v1_json
simple{0}index.html
simple{0}index.v1_html
simple{0}index.v1_json""".format(
        sep
    ) == utils.find(
        mirror.webdir, dirs=False
    )
    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )


@pytest.mark.asyncio
async def test_mirror_sync_package_download_mirror_fails(
    mirror: BandersnatchMirror,
) -> None:
    mirror.master.all_packages = mock.AsyncMock(return_value={"foo": 1})  # type: ignore
    mirror.json_save = True
    # Recall bootstrap so we have the json dirs
    mirror._bootstrap()
    # This download mirror URL does not work, forcing not to fallback
    mirror.download_mirror = "https://not-working.example.com"
    mirror.download_mirror_no_fallback = True

    with mock.patch("bandersnatch.mirror.logger.exception") as mock_log:
        await mirror.synchronize()
        # 3 calls are:
        # * Tried and failed to get /packages/any/f/foo/foo.zip
        # * Tried and failed to get /packages/2.7/f/foo/foo.whl
        # * Declared error on syncing package foo@1
        assert mock_log.call_count == 3


@pytest.mark.asyncio
async def test_mirror_serial_current_no_sync_of_packages_and_index_page(
    mirror: BandersnatchMirror,
) -> None:
    mirror.master.changed_packages = mock.AsyncMock(return_value={})  # type: ignore
    mirror.synced_serial = 1
    await mirror.synchronize()

    assert """\
last-modified""" == utils.find(
        mirror.webdir, dirs=False
    )


def test_mirror_json_metadata(
    mirror: BandersnatchMirror, package_json: dict[str, Any]
) -> None:
    package = Package("foo", serial=11)
    mirror.json_file(package.name).parent.mkdir(parents=True)
    mirror.json_pypi_symlink(package.name).parent.mkdir(parents=True)
    assert mirror.save_json_metadata(package_json, package.name)
    assert mirror.json_pypi_symlink(package.name).is_file()
    assert (
        mirror.json_pypi_symlink(package.name).read_text()
        == mirror.json_file(package.name).read_text()
    )


@pytest.mark.asyncio
async def test_metadata_404_keeps_package_on_non_deleting_mirror(
    mirror: BandersnatchMirror,
) -> None:
    paths = [Path("web/packages/2.4/f/foo/foo.zip"), Path("web/simple/foo/index.html")]
    touch_files(paths)

    mirror.packages_to_sync = {"foo": 10}
    await mirror.sync_packages()
    for path in paths:
        assert path.exists()


def test_find_package_indexes_in_dir_threaded(mirror: BandersnatchMirror) -> None:
    directories = (
        "web/simple/peerme",
        "web/simple/click",
        "web/simple/zebra",
        "web/simple/implicit",
        "web/simple/pyaib",
        "web/simple/setuptools",
        "web_hash/simple/p/peerme",
        "web_hash/simple/c/click",
        "web_hash/simple/z/zebra",
        "web_hash/simple/i/implicit",
        "web_hash/simple/p/pyaib",
        "web_hash/simple/s/setuptools",
    )
    with TemporaryDirectory() as td:
        # Create local mirror first so we '_bootstrap'
        mirror_base = Path(td)
        local_mirror = BandersnatchMirror(
            mirror_base, mirror.master, stop_on_error=True
        )
        # Create fake file system objects
        for directory in directories:
            (mirror_base / directory).mkdir(parents=True, exist_ok=True)
            (mirror_base / directory / "index.html").touch()
        with (mirror_base / "web/simple/index.html").open("w") as index:
            index.write("<html></html>")
        with (mirror_base / "web_hash/simple/index.html").open("w") as index:
            index.write("<html></html>")

        packages = [
            pkg
            for subdir in local_mirror.simple_api.get_simple_dirs(
                mirror_base / "web/simple"
            )
            for pkg in local_mirror.simple_api.find_packages_in_dir(subdir)
        ]
        local_mirror.simple_api.hash_index = True
        packages_hash = [
            pkg
            for subdir in local_mirror.simple_api.get_simple_dirs(
                mirror_base / "web_hash/simple"
            )
            for pkg in local_mirror.simple_api.find_packages_in_dir(subdir)
        ]

        assert packages == packages_hash
        assert "index.html" not in packages  # This should never be in the list
        assert len(packages) == 6  # We expect 6 packages with 6 dirs created
        assert packages[0] == "click"  # Check sorted - click should be first


def test_validate_todo(mirror: BandersnatchMirror) -> None:
    valid_todo = "69\ncooper 69\ndan 1\n"
    invalid_todo = "cooper l33t\ndan n00b\n"

    with TemporaryDirectory() as td:
        test_mirror = BandersnatchMirror(Path(td), mirror.master)
        for todo_data in (valid_todo, invalid_todo):
            with test_mirror.todolist.open("w") as tdfp:
                tdfp.write(todo_data)

            test_mirror._validate_todo()
            if todo_data == valid_todo:
                assert test_mirror.todolist.exists()
            else:
                assert not test_mirror.todolist.exists()


@pytest.mark.asyncio
async def test_package_sync_with_release_no_files_syncs_simple_page(
    mirror: BandersnatchMirror,
) -> None:
    mirror.packages_to_sync = {"foo": 1}
    await mirror.sync_packages()

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_with_release_no_files_syncs_simple_page_with_hash(
    mirror_hash_index: BandersnatchMirror,
) -> None:
    mirror_hash_index.packages_to_sync = {"foo": 1}
    await mirror_hash_index.sync_packages()

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_with_canonical_simple_page(
    mirror: BandersnatchMirror,
) -> None:
    mirror.packages_to_sync = {"Foo": 1}
    await mirror.sync_packages()

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for Foo</title>
  </head>
  <body>
    <h1>Links for Foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_with_canonical_simple_page_with_hash(
    mirror_hash_index: BandersnatchMirror,
) -> None:
    mirror_hash_index.packages_to_sync = {"Foo": 1}
    await mirror_hash_index.sync_packages()

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for Foo</title>
  </head>
  <body>
    <h1>Links for Foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_with_normalized_simple_page(
    mirror: BandersnatchMirror,
) -> None:
    mirror.packages_to_sync = {"Foo.bar-thing_other": 1}
    await mirror.sync_packages()

    # PEP 503 normalization
    assert (
        open("web/simple/foo-bar-thing-other/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for Foo.bar-thing_other</title>
  </head>
  <body>
    <h1>Links for Foo.bar-thing_other</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_simple_page_root_uri(mirror: BandersnatchMirror) -> None:
    mirror.packages_to_sync = {"foo": 1}
    mirror.simple_api.root_uri = "https://files.pythonhosted.org"
    await mirror.sync_packages()
    mirror.simple_api.root_uri = None

    expected_root_uri_hrefs = (
        '<a href="https://files.pythonhosted.org/packages/2.7/f/foo/foo.whl#sha256=e3b'
        + '0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855">foo.whl</a>'
        + '<br/>\n    <a href="https://files.pythonhosted.org/packages/any/f/foo/foo.'
        + "zip#sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        + '">foo.zip</a><br/>'
    )

    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            expected_root_uri_hrefs
        )
    )


@pytest.mark.asyncio
async def test_package_sync_simple_page_with_files(mirror: BandersnatchMirror) -> None:
    mirror.packages_to_sync = {"foo": 1}
    await mirror.sync_packages()
    assert not mirror.errors

    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_simple_page_with_existing_dir(
    mirror: BandersnatchMirror,
) -> None:
    mirror.packages_to_sync = {"foo": 1}
    package = Package("foo", serial=1)
    os.makedirs(mirror.simple_directory(package))
    await mirror.sync_packages()
    assert not mirror.errors

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_simple_page_with_existing_dir_with_hash(
    mirror_hash_index: BandersnatchMirror,
) -> None:
    mirror_hash_index.packages_to_sync = {"foo": 1}
    package = Package("foo", serial=1)
    os.makedirs(mirror_hash_index.simple_directory(package))
    await mirror_hash_index.sync_packages()

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for foo</title>
  </head>
  <body>
    <h1>Links for foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )


@pytest.mark.asyncio
async def test_package_sync_with_error_keeps_it_on_todo_list(
    mirror: BandersnatchMirror,
) -> None:
    # Make packages_to_sync to generate an error
    mirror.packages_to_sync = {"foo"}  # type: ignore
    await mirror.sync_packages()
    assert mirror.errors
    assert "foo" in mirror.packages_to_sync


@pytest.mark.asyncio
async def test_package_sync_downloads_release_file(mirror: BandersnatchMirror) -> None:
    mirror.packages_to_sync = {"foo": 0}
    await mirror.sync_packages()
    assert not mirror.errors

    assert open("web/packages/any/f/foo/foo.zip").read() == ""


@pytest.mark.asyncio
async def test_package_sync_skips_release_file(mirror: BandersnatchMirror) -> None:
    mirror.release_files_save = False
    mirror.packages_to_sync = {"foo": 0}
    await mirror.sync_packages()
    assert not mirror.errors

    assert not os.path.exists("web/packages/any/f/foo/foo.zip")


@pytest.mark.asyncio
async def test_package_download_rejects_non_package_directory_links(
    mirror: BandersnatchMirror,
) -> None:
    mirror.packages_to_sync = {"foo"}  # type: ignore
    await mirror.sync_packages()
    assert mirror.errors
    assert "foo" in mirror.packages_to_sync
    assert not os.path.exists("web/foo/bar/foo/foo.zip")


@pytest.mark.asyncio
async def test_sync_keeps_superfluous_files_on_nondeleting_mirror(
    mirror: BandersnatchMirror,
) -> None:
    test_files = [Path("web/packages/2.4/f/foo/foo.zip")]
    touch_files(test_files)

    mirror.packages_to_sync = {"foo": 1}
    await mirror.sync_packages()
    assert not mirror.errors

    assert test_files[0].exists()


@pytest.mark.asyncio
async def test_package_sync_replaces_mismatching_local_files(
    mirror: BandersnatchMirror,
) -> None:
    test_files = [Path("web/packages/any/f/foo/foo.zip")]
    touch_files(test_files)
    with test_files[0].open("wb") as f:
        f.write(b"this is not the release content")

    mirror.packages_to_sync = {"foo": 1}
    await mirror.sync_packages()
    assert not mirror.errors

    assert test_files[0].open("r").read() == ""


@pytest.mark.asyncio
async def test_package_sync_handles_non_pep_503_in_packages_to_sync(
    master: Master,
) -> None:
    with TemporaryDirectory() as td:
        mirror = BandersnatchMirror(Path(td), master, stop_on_error=True)
        mirror.packages_to_sync = {"Foo": 1}
        await mirror.sync_packages()
        assert not mirror.errors


@pytest.mark.asyncio
async def test_package_sync_does_not_touch_existing_local_file(
    mirror: BandersnatchMirror,
) -> None:
    pkg_file_path_str = "web/packages/any/f/foo/foo.zip"
    pkg_file_path = Path(pkg_file_path_str)
    touch_files([pkg_file_path])
    with pkg_file_path.open("w") as f:
        f.write("")
    # Here mtime is used to store upload time
    # 949454625.123456 => 2000-02-02T01:23:45.123456Z in conftest.py
    mtime = 949454625.123456
    os.utime(pkg_file_path, (mtime, mtime))
    old_stat = pkg_file_path.stat()

    mirror.packages_to_sync = {"foo": 1}
    await mirror.sync_packages()
    assert not mirror.errors

    # Use Pathlib + create a new object to ensure no caching
    # Only compare the relevant stat fields
    assert old_stat.st_mtime == Path(pkg_file_path_str).stat().st_mtime
    assert old_stat.st_ctime == Path(pkg_file_path_str).stat().st_ctime


def test_gen_html_file_tags(mirror: BandersnatchMirror) -> None:
    fake_no_release: dict[str, str] = {}

    # only requires_python
    fake_release_1 = {"requires_python": ">=3.6"}

    # only data_yanked
    fake_release_2 = {"yanked": True, "yanked_reason": "Broken release"}

    # requires_python and data_yanked
    fake_release_3 = {
        "requires_python": ">=3.6",
        "yanked": True,
        "yanked_reason": "Broken release",
    }

    assert mirror.simple_api.gen_html_file_tags(fake_no_release) == ""
    assert (
        mirror.simple_api.gen_html_file_tags(fake_release_1)
        == ' data-requires-python="&gt;=3.6"'
    )
    assert (
        mirror.simple_api.gen_html_file_tags(fake_release_2)
        == ' data-yanked="Broken release"'
    )
    assert (
        mirror.simple_api.gen_html_file_tags(fake_release_3)
        == ' data-requires-python="&gt;=3.6" data-yanked="Broken release"'
    )


@pytest.mark.asyncio
async def test_sync_incorrect_download_with_current_serial_fails(
    mirror: BandersnatchMirror,
) -> None:
    # ???
    mirror.packages_to_sync = {"foo": 2}
    await mirror.sync_packages()

    assert not Path("web/packages/any/f/foo/foo.zip").exists()
    assert mirror.errors


@pytest.mark.asyncio
async def test_sync_incorrect_download_with_old_serials_retries(
    mirror: BandersnatchMirror,
) -> None:
    mirror.packages_to_sync = {"foo": 2}
    await mirror.sync_packages()

    assert not Path("web/packages/any/f/foo/foo.zip").exists()
    assert mirror.errors


@pytest.mark.asyncio
async def test_survives_exceptions_from_record_finished_package(
    mirror: BandersnatchMirror,
) -> None:
    def record_finished_package(name: str) -> NoReturn:
        import errno

        raise OSError(errno.EBADF, "Some transient error?")

    mirror.packages_to_sync = {"Foo": 1}
    mirror.record_finished_package = record_finished_package  # type: ignore

    await mirror.sync_packages()

    assert (
        Path("web/simple/foo/index.html").open().read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for Foo</title>
  </head>
  <body>
    <h1>Links for Foo</h1>
    {}
  </body>
</html>
<!--SERIAL 654321-->\
""".format(
            EXPECTED_REL_HREFS
        )
    )
    assert mirror.errors


@freeze_time("2018-10-28")
@pytest.mark.asyncio
async def test_keep_index_versions_stores_one_prior_version(
    mirror: BandersnatchMirror,
) -> None:
    mirror.packages_to_sync = {"foo": 1}
    mirror.keep_index_versions = 1
    await mirror.sync_packages()
    assert not mirror.errors

    simple_path = Path("web/simple/foo")
    versions_path = simple_path / "versions"
    version_files = sorted(list(versions_path.iterdir()))
    assert len(version_files) == 3  # html, v1_html, v1_json
    assert version_files[0].name == f"index_1_{make_time_stamp()}.html"
    assert version_files[2].name == f"index_1_{make_time_stamp()}.v1_json"
    link_path = simple_path / "index.html"
    assert link_path.is_symlink()
    assert link_path.resolve().name == version_files[0].name


@pytest.mark.asyncio
async def test_keep_index_versions_stores_different_prior_versions(
    mirror: BandersnatchMirror,
) -> None:
    simple_path = Path("web/simple/foo")
    versions_path = simple_path / "versions"
    mirror.packages_to_sync = {"foo": 1}
    mirror.keep_index_versions = 2

    with freeze_time("2018-10-27"):
        await mirror.sync_packages()
        assert not mirror.errors

    mirror.packages_to_sync = {"foo": 1}
    with freeze_time("2018-10-28"):
        await mirror.sync_packages()
        assert not mirror.errors

    version_files = sorted(os.listdir(versions_path))
    assert len(version_files) == 6
    assert version_files[0].startswith("index_1_2018-10-27")
    assert version_files[3].startswith("index_1_2018-10-28")
    html_link_path = simple_path / "index.html"
    json_link_path = simple_path / "index.html"
    assert html_link_path.is_symlink()
    assert json_link_path.is_symlink()
    assert html_link_path.resolve().name == version_files[3]


@pytest.mark.asyncio
async def test_keep_index_versions_removes_old_versions(
    mirror: BandersnatchMirror,
) -> None:
    simple_path = Path("web/simple/foo/")
    versions_path = simple_path / "versions"
    versions_path.mkdir(parents=True)
    (versions_path / "index_1_2018-10-26T000000Z.html").touch()
    (versions_path / "index_1_2018-10-27T000000Z.html").touch()

    mirror.keep_index_versions = 2
    with freeze_time("2018-10-28"):
        mirror.packages_to_sync = {"foo": 1}
        await mirror.sync_packages()

    version_files = sorted(f for f in versions_path.iterdir())
    assert len(version_files) == 4  # Old + new html + v1_html/json
    assert version_files[0].name.startswith("index_1_2018-10-27")
    assert version_files[1].name.startswith("index_1_2018-10-28")
    link_path = simple_path / "index.html"
    assert link_path.is_symlink()
    assert os.path.basename(os.readlink(str(link_path))) == version_files[1].name


@pytest.mark.asyncio
async def test_cleanup_non_pep_503_paths(mirror: BandersnatchMirror) -> None:
    raw_package_name = "CatDogPython69"
    package = Package(raw_package_name)
    await mirror.cleanup_non_pep_503_paths(package)

    # Create a non normalized directory
    touch_files([mirror.webdir / "simple" / raw_package_name / "index.html"])

    mirror.cleanup = True
    with mock.patch("bandersnatch.mirror.Path.unlink") as mocked_unlink, mock.patch(
        "bandersnatch.mirror.Path.rmdir"
    ) as mocked_rmdir:
        await mirror.cleanup_non_pep_503_paths(package)
        assert mocked_unlink.call_count == 1  # number you expect
        assert mocked_rmdir.call_count == 1  # Or number you expect here


def test_determine_packages_to_sync(mirror: BandersnatchMirror) -> None:
    mirror.synced_serial = 24
    mirror.packages_to_sync = {"black": 69, "foobar": 47, "barfoo": 68}
    target_serial = mirror.find_target_serial()
    assert target_serial == 69


def test_write_simple_pages(mirror: BandersnatchMirror) -> None:
    html_content = SimpleFormats(html="html", json="")
    json_content = SimpleFormats(html="", json="json")
    package = Package("69")
    package._metadata = SIXTYNINE_METADATA
    with TemporaryDirectory() as td:
        td_path = Path(td)
        package_simple_dir = td_path / "web" / "simple" / package.name
        package_simple_dir.mkdir(parents=True)
        mirror.homedir = mirror.storage_backend.PATH_BACKEND(str(td_path))
        # Run function for each format separately only
        mirror.write_simple_pages(package, html_content)
        mirror.write_simple_pages(package, json_content)
    # Expect .html, .v1_html and .v1_json ...
    assert 3 == len(mirror.diff_file_list)


if __name__ == "__main__":
    pytest.main(sys.argv)
