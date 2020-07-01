import os.path
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from typing import Any, Dict, Iterable, NoReturn

import asynctest
import pytest
from _pytest.capture import CaptureFixture
from freezegun import freeze_time

from bandersnatch.master import Master, StalePage
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package, StaleMetadata
from bandersnatch.utils import make_time_stamp

EXPECTED_REL_HREFS = (
    '<a href="../../packages/2.7/f/foo/foo.whl#sha256=e3b0c44298fc1c149afbf4c8996fb924'
    + '27ae41e4649b934ca495991b7852b855">foo.whl</a><br/>\n'
    '    <a href="../../packages/any/f/foo/foo.zip#sha256=e3b0c44298fc1c149afbf4c8996f'
    + 'b92427ae41e4649b934ca495991b7852b855">foo.zip</a><br/>'
)


def touch_files(paths: Iterable[Path]) -> None:
    for path in paths:
        if not path.parent.exists():
            path.parent.mkdir(parents=True)
        with path.open("wb") as pfp:
            pfp.close()


def test_save_json_metadata(mirror: Mirror, package_json: Dict[str, Any]) -> None:
    package = Package("foo", 11, mirror)
    package.json_file.parent.mkdir(parents=True)
    package.json_pypi_symlink.parent.mkdir(parents=True)
    package.json_pypi_symlink.symlink_to(Path(gettempdir()))
    assert package.save_json_metadata(package_json)


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_404_json_info_keeps_package_on_non_deleting_mirror(
    mirror: Mirror,
) -> None:

    paths = [Path("web/packages/2.4/f/foo/foo.zip"), Path("web/simple/foo/index.html")]
    touch_files(paths)

    package = Package("foo", 10, mirror)
    await package.sync(mirror.filters)
    for path in paths:
        assert path.exists()


@pytest.mark.asyncio  # type: ignore
async def test_package_fetch_metadata_gives_up_after_3_stale_responses(
    caplog: CaptureFixture, mirror: Mirror
) -> None:
    mirror.master.get_package_metadata = asynctest.CoroutineMock(  # type: ignore
        side_effect=StalePage
    )

    pkg_name = "foo"
    package = Package(pkg_name, 11, mirror)

    with pytest.raises(StaleMetadata):
        await package.fetch_metadata()
    assert mirror.master.get_package_metadata.await_count == 3  # type: ignore
    assert "not updating. Giving up" in caplog.text


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_with_release_no_files_syncs_simple_page(
    mirror: Mirror,
) -> None:
    mirror.packages_to_sync = {"foo": 1}
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_with_release_no_files_syncs_simple_page_with_hash(
    mirror_hash_index: Mirror,
) -> None:
    mirror_hash_index.packages_to_sync = {"foo": 1}
    package = Package("foo", 1, mirror_hash_index)
    await package.sync(mirror_hash_index.filters)

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_with_canonical_simple_page(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"Foo": 1}
    package = Package("Foo", 1, mirror)
    await package.sync(mirror.filters)

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_with_canonical_simple_page_with_hash(
    mirror_hash_index: Mirror,
) -> None:
    mirror_hash_index.packages_to_sync = {"Foo": 1}
    package = Package("Foo", 1, mirror_hash_index)
    await package.sync(mirror_hash_index.filters)

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_with_normalized_simple_page(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"Foo.bar-thing_other": 1}
    package = Package("Foo.bar-thing_other", 1, mirror)
    await package.sync(mirror.filters)

    # PEP 503 normalization
    assert (
        open("web/simple/foo-bar-thing-other/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_simple_page_root_uri(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"foo": 1}
    mirror.root_uri = "https://files.pythonhosted.org"
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    mirror.root_uri = None

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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_simple_page_with_files(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"foo": 1}
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert not mirror.errors

    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_simple_page_with_existing_dir(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"foo": 1}
    package = Package("foo", 1, mirror)
    os.makedirs(package.simple_directory)
    await package.sync(mirror.filters)
    assert not mirror.errors

    # Cross-check that simple directory hashing is disabled.
    assert not os.path.exists("web/simple/f/foo/index.html")
    assert (
        open("web/simple/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_simple_page_with_existing_dir_with_hash(
    mirror_hash_index: Mirror,
) -> None:
    mirror_hash_index.packages_to_sync = {"foo": 1}
    package = Package("foo", 1, mirror_hash_index)
    os.makedirs(package.simple_directory)
    await package.sync(mirror_hash_index.filters)

    assert not os.path.exists("web/simple/foo/index.html")
    assert (
        open("web/simple/f/foo/index.html").read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_with_error_keeps_it_on_todo_list(mirror: Mirror) -> None:
    # Make packages_to_sync to generate an error
    mirror.packages_to_sync = {"foo"}  # type: ignore
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert mirror.errors
    assert "foo" in mirror.packages_to_sync


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_downloads_release_file(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"foo": ""}
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert not mirror.errors

    assert open("web/packages/any/f/foo/foo.zip").read() == ""


@pytest.mark.asyncio  # type: ignore
async def test_package_download_rejects_non_package_directory_links(
    mirror: Mirror,
) -> None:
    mirror.packages_to_sync = {"foo"}  # type: ignore
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert mirror.errors
    assert "foo" in mirror.packages_to_sync
    assert not os.path.exists("web/foo/bar/foo/foo.zip")


@pytest.mark.asyncio  # type: ignore
async def test_sync_keeps_superfluous_files_on_nondeleting_mirror(
    mirror: Mirror,
) -> None:
    test_files = [Path("web/packages/2.4/f/foo/foo.zip")]
    touch_files(test_files)

    mirror.packages_to_sync = {"foo": ""}
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert not mirror.errors

    assert test_files[0].exists()


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_replaces_mismatching_local_files(mirror: Mirror) -> None:
    test_files = [Path("web/packages/any/f/foo/foo.zip")]
    touch_files(test_files)
    with test_files[0].open("wb") as f:
        f.write(b"this is not the release content")

    mirror.packages_to_sync = {"foo": ""}
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert not mirror.errors

    assert test_files[0].open("r").read() == ""


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_handles_non_pep_503_in_packages_to_sync(
    master: Master,
) -> None:
    with TemporaryDirectory() as td:
        mirror = Mirror(Path(td), master, stop_on_error=True)
        mirror.packages_to_sync = {"Foo": ""}
        package = Package("Foo", 1, mirror)
        await package.sync(mirror.filters)
        assert not mirror.errors


@pytest.mark.asyncio  # type: ignore
async def test_package_sync_does_not_touch_existing_local_file(mirror: Mirror) -> None:
    pkg_file_path_str = "web/packages/any/f/foo/foo.zip"
    pkg_file_path = Path(pkg_file_path_str)
    touch_files((pkg_file_path,))
    with pkg_file_path.open("w") as f:
        f.write("")
    old_stat = pkg_file_path.stat()

    mirror.packages_to_sync = {"foo": 1}
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert not mirror.errors

    # Use Pathlib + create a new object to ensure no caching
    # Only compare the relevant stat fields
    assert old_stat.st_mtime == Path(pkg_file_path_str).stat().st_mtime
    assert old_stat.st_ctime == Path(pkg_file_path_str).stat().st_ctime


def test_gen_data_requires_python(mirror: Mirror) -> None:
    fake_no_release: Dict[str, str] = {}
    fake_release = {"requires_python": ">=3.6"}
    package = Package("foo", 10, mirror)

    assert package.gen_data_requires_python(fake_no_release) == ""
    assert (
        package.gen_data_requires_python(fake_release)
        == ' data-requires-python="&gt;=3.6"'
    )


@pytest.mark.asyncio  # type: ignore
async def test_sync_incorrect_download_with_current_serial_fails(
    mirror: Mirror,
) -> None:
    mirror.packages_to_sync = {"foo": 1}
    package = Package("foo", 2, mirror)
    await package.sync(mirror.filters)

    assert not Path("web/packages/any/f/foo/foo.zip").exists()
    assert mirror.errors


@pytest.mark.asyncio  # type: ignore
async def test_sync_incorrect_download_with_old_serials_retries(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"foo": 1}
    package = Package("foo", 2, mirror)
    await package.sync(mirror.filters)

    assert not Path("web/packages/any/f/foo/foo.zip").exists()
    assert mirror.errors


@pytest.mark.asyncio  # type: ignore
async def test_survives_exceptions_from_record_finished_package(mirror: Mirror) -> None:
    def record_finished_package(name: str) -> NoReturn:
        import errno

        raise OSError(errno.EBADF, "Some transient error?")

    mirror.packages_to_sync = {"Foo": 1}
    mirror.record_finished_package = record_finished_package  # type: ignore

    package = Package("Foo", 1, mirror)
    await package.sync(mirror.filters)

    assert (
        Path("web/simple/foo/index.html").open().read()
        == """\
<!DOCTYPE html>
<html>
  <head>
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


@freeze_time("2018-10-28")  # type: ignore
@pytest.mark.asyncio  # type: ignore
async def test_keep_index_versions_stores_one_prior_version(mirror: Mirror) -> None:
    mirror.packages_to_sync = {"foo": ""}
    mirror.keep_index_versions = 1
    package = Package("foo", 1, mirror)
    await package.sync(mirror.filters)
    assert not mirror.errors

    simple_path = Path("web/simple/foo")
    versions_path = simple_path / "versions"
    version_files = os.listdir(versions_path)
    assert len(version_files) == 1
    assert version_files[0] == f"index_{package.serial}_{make_time_stamp()}.html"
    link_path = simple_path / "index.html"
    assert link_path.is_symlink()
    assert os.path.basename(os.readlink(str(link_path))) == version_files[0]


@pytest.mark.asyncio  # type: ignore
async def test_keep_index_versions_stores_different_prior_versions(
    mirror: Mirror,
) -> None:
    simple_path = Path("web/simple/foo")
    versions_path = simple_path / "versions"
    mirror.packages_to_sync = {"foo": 1}
    mirror.keep_index_versions = 2

    with freeze_time("2018-10-27"):
        package = Package("foo", 1, mirror)
        await package.sync(mirror.filters)
        assert not mirror.errors

    mirror.packages_to_sync = {"foo": 1}
    with freeze_time("2018-10-28"):
        package = Package("foo", 1, mirror)
        await package.sync(mirror.filters)
        assert not mirror.errors

    version_files = sorted(os.listdir(versions_path))
    assert len(version_files) == 2
    assert version_files[0].startswith("index_1_2018-10-27")
    assert version_files[1].startswith("index_1_2018-10-28")
    link_path = simple_path / "index.html"
    assert os.path.islink(link_path)
    assert os.path.basename(os.readlink(str(link_path))) == version_files[1]


@pytest.mark.asyncio  # type: ignore
async def test_keep_index_versions_removes_old_versions(mirror: Mirror) -> None:
    simple_path = Path("web/simple/foo/")
    versions_path = simple_path / "versions"
    versions_path.mkdir(parents=True)
    (versions_path / "index_1_2018-10-26T000000Z.html").touch()
    (versions_path / "index_1_2018-10-27T000000Z.html").touch()

    mirror.keep_index_versions = 2
    with freeze_time("2018-10-28"):
        package = Package("foo", 1, mirror)
        await package.sync(mirror.filters)

    version_files = sorted(f for f in versions_path.iterdir())
    assert len(version_files) == 2
    assert version_files[0].name.startswith("index_1_2018-10-27")
    assert version_files[1].name.startswith("index_1_2018-10-28")
    link_path = simple_path / "index.html"
    assert link_path.is_symlink()
    assert os.path.basename(os.readlink(str(link_path))) == version_files[1].name
