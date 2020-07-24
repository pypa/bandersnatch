import asynctest
import pytest
from _pytest.capture import CaptureFixture

from bandersnatch.errors import PackageNotFound, StaleMetadata
from bandersnatch.master import Master, StalePage
from bandersnatch.package import Package

EXPECTED_REL_HREFS = (
    '<a href="../../packages/2.7/f/foo/foo.whl#sha256=e3b0c44298fc1c149afbf4c8996fb924'
    + '27ae41e4649b934ca495991b7852b855">foo.whl</a><br/>\n'
    '    <a href="../../packages/any/f/foo/foo.zip#sha256=e3b0c44298fc1c149afbf4c8996f'
    + 'b92427ae41e4649b934ca495991b7852b855">foo.zip</a><br/>'
)


def test_package_accessors(package: Package) -> None:
    assert package.info == {"name": "Foo", "version": "0.1"}
    assert package.last_serial == 654_321
    assert list(package.releases.keys()) == ["0.1"]
    assert len(package.release_files) == 2
    for f in package.release_files:
        assert "filename" in f
        assert "digests" in f


def test_save_json_metadata(mirror: Mirror, package_json: Dict[str, Any]) -> None:
    package = Package("foo", 11, mirror)
    package.json_file.parent.mkdir(parents=True)
    package.json_pypi_symlink.parent.mkdir(parents=True)
    package.json_pypi_symlink.symlink_to(Path(gettempdir()))
    assert package.save_json_metadata(package_json)
    assert package.json_pypi_symlink.is_symlink()
    assert Path("../../json/foo") == Path(os.readlink(str(package.json_pypi_symlink)))


@pytest.mark.asyncio
async def test_package_sync_404_json_info_keeps_package_on_non_deleting_mirror(
    mirror: Mirror,
) -> None:

    paths = [Path("web/packages/2.4/f/foo/foo.zip"), Path("web/simple/foo/index.html")]
    touch_files(paths)

    package = Package("foo", 10, mirror)
    await package.sync(mirror.filters)
    for path in paths:
        assert path.exists()


@pytest.mark.asyncio
async def test_package_update_metadata_gives_up_after_3_stale_responses(
    caplog: CaptureFixture, master: Master
) -> None:
    master.get_package_metadata = asynctest.CoroutineMock(  # type: ignore
        side_effect=StalePage
    )
    package = Package("foo", serial=11)

    with pytest.raises(StaleMetadata):
        await package.update_metadata(master, attempts=3)
    assert master.get_package_metadata.await_count == 3  # type: ignore
    assert "not updating. Giving up" in caplog.text


@pytest.mark.asyncio
async def test_package_not_found(caplog: CaptureFixture, master: Master) -> None:
    pkg_name = "foo"
    master.get_package_metadata = asynctest.CoroutineMock(  # type: ignore
        side_effect=PackageNotFound(pkg_name)
    )
    package = Package(pkg_name, serial=11)

    with pytest.raises(PackageNotFound):
        await package.update_metadata(master)
    assert "foo no longer exists on PyPI" in caplog.text
