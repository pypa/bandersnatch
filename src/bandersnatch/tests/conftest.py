# flake8: noqa

import unittest.mock as mock
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import pytest
from _pytest.capture import CaptureFixture
from _pytest.fixtures import FixtureRequest
from _pytest.monkeypatch import MonkeyPatch
from asynctest import asynctest

if TYPE_CHECKING:
    from bandersnatch.mirror import BandersnatchMirror
    from bandersnatch.master import Master
    from bandersnatch.package import Package


@pytest.fixture(autouse=True)
def stop_std_logging(request: FixtureRequest, capfd: CaptureFixture) -> None:
    patcher = mock.patch("bandersnatch.log.setup_logging")
    patcher.start()

    def tearDown() -> None:
        patcher.stop()

    request.addfinalizer(tearDown)


async def _nosleep(*args: Any) -> None:
    pass


@pytest.fixture(autouse=True)
def never_sleep(request: FixtureRequest) -> None:
    patcher = mock.patch("asyncio.sleep", _nosleep)
    patcher.start()

    def tearDown() -> None:
        patcher.stop()

    request.addfinalizer(tearDown)


@pytest.fixture
def package(package_json: dict) -> "Package":
    from bandersnatch.package import Package

    pkg = Package(package_json["info"]["name"], serial=11)
    pkg._metadata = package_json
    return pkg


@pytest.fixture
def package_json() -> Dict[str, Any]:
    return {
        "info": {"name": "Foo", "version": "0.1"},
        "last_serial": 654_321,
        "releases": {
            "0.1": [
                {
                    "url": "https://pypi.example.com/packages/any/f/foo/foo.zip",
                    "filename": "foo.zip",
                    "digests": {
                        "md5": "6bd3ddc295176f4dca196b5eb2c4d858",
                        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    },
                    "md5_digest": "b6bcb391b040c4468262706faf9d3cce",
                },
                {
                    "url": "https://pypi.example.com/packages/2.7/f/foo/foo.whl",
                    "filename": "foo.whl",
                    "digests": {
                        "md5": "6bd3ddc295176f4dca196b5eb2c4d858",
                        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    },
                    "md5_digest": "6bd3ddc295176f4dca196b5eb2c4d858",
                },
            ]
        },
    }


@pytest.fixture
def master(package_json: Dict[str, Any]) -> "Master":
    from bandersnatch.master import Master

    class FakeReader:
        async def read(self, *args: Any) -> bytes:
            return b""

    class FakeAiohttpClient:
        headers = {"X-PYPI-LAST-SERIAL": "1"}

        async def __aenter__(self) -> "FakeAiohttpClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        @property
        def content(self) -> "FakeReader":
            return FakeReader()

        async def json(self, *args: Any) -> Dict[str, Any]:
            return package_json

    master = Master("https://pypi.example.com")
    master.rpc = mock.Mock()  # type: ignore
    master.session = asynctest.MagicMock()
    master.session.get = asynctest.MagicMock(return_value=FakeAiohttpClient())
    master.session.request = asynctest.MagicMock(return_value=FakeAiohttpClient())
    return master


@pytest.fixture
def mirror(
    tmpdir: Path, master: "Master", monkeypatch: MonkeyPatch
) -> "BandersnatchMirror":
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import BandersnatchMirror

    return BandersnatchMirror(tmpdir, master)


@pytest.fixture
def mirror_hash_index(
    tmpdir: Path, master: "Master", monkeypatch: MonkeyPatch
) -> "BandersnatchMirror":
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import BandersnatchMirror

    return BandersnatchMirror(tmpdir, master, hash_index=True)


@pytest.fixture
def mirror_mock(request: FixtureRequest) -> mock.MagicMock:
    patcher = mock.patch("bandersnatch.mirror.BandersnatchMirror")
    mirror: mock.MagicMock = patcher.start()

    def tearDown() -> None:
        patcher.stop()

    request.addfinalizer(tearDown)
    return mirror


@pytest.fixture
def logging_mock(request: FixtureRequest) -> mock.MagicMock:
    patcher = mock.patch("logging.config.fileConfig")
    logger: mock.MagicMock = patcher.start()

    def tearDown() -> None:
        patcher.stop()

    request.addfinalizer(tearDown)
    return logger
