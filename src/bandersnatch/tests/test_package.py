from asyncio import TimeoutError
from unittest.mock import AsyncMock

import pytest
from _pytest.capture import CaptureFixture

from bandersnatch.errors import ConnectionTimeout, PackageNotFound, StaleMetadata
from bandersnatch.master import Master, StalePage
from bandersnatch.package import Package


def test_package_accessors(package: Package) -> None:
    assert package.info == {"name": "Foo", "version": "0.1"}
    assert package.last_serial == 654_321
    assert list(package.releases.keys()) == ["0.1"]
    assert len(package.release_files) == 2
    for f in package.release_files:
        assert "filename" in f
        assert "digests" in f


@pytest.mark.asyncio
async def test_package_update_metadata_gives_up_after_3_stale_responses(
    caplog: CaptureFixture, master: Master
) -> None:
    master.get_package_metadata = AsyncMock(side_effect=StalePage)  # type: ignore
    package = Package("foo", serial=11)

    with pytest.raises(StaleMetadata):
        await package.update_metadata(master, attempts=3)
    assert master.get_package_metadata.await_count == 3
    assert "not updating. Giving up" in caplog.text


@pytest.mark.asyncio
async def test_package_not_found(caplog: CaptureFixture, master: Master) -> None:
    pkg_name = "foo"
    master.get_package_metadata = AsyncMock(  # type: ignore
        side_effect=PackageNotFound(pkg_name)
    )
    package = Package(pkg_name, serial=11)

    with pytest.raises(PackageNotFound):
        await package.update_metadata(master)
    assert "foo no longer exists on PyPI" in caplog.text


@pytest.mark.asyncio
async def test_package_update_metadata_gives_up_after_3_timeouts(
    caplog: CaptureFixture, master: Master
) -> None:
    master.get_package_metadata = AsyncMock(side_effect=TimeoutError)  # type: ignore
    package = Package("foo", serial=11)

    with pytest.raises(ConnectionTimeout) as timeout:
        await package.update_metadata(master, attempts=3)
        assert "Connection timeout for foo after 3 attempts" in str(timeout)
    assert master.get_package_metadata.await_count == 3
    assert "not updating. Giving up" in caplog.text
