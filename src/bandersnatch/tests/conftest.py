# flake8: noqa
import os
import unittest.mock as mock
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import boto3
import pytest
from _pytest.capture import CaptureFixture
from _pytest.fixtures import FixtureRequest
from _pytest.monkeypatch import MonkeyPatch
from s3path import PureS3Path, S3Path, _s3_accessor, register_configuration_parameter

if TYPE_CHECKING:
    from bandersnatch.master import Master
    from bandersnatch.mirror import BandersnatchMirror
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
def package_json() -> dict[str, Any]:
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
                    "size": 0,
                    "upload_time_iso_8601": "2000-02-02T01:23:45.123456Z",
                    "python_requires": ">=3.6",
                    "yanked": False,
                },
                {
                    "url": "https://pypi.example.com/packages/2.7/f/foo/foo.whl",
                    "filename": "foo.whl",
                    "digests": {
                        "md5": "6bd3ddc295176f4dca196b5eb2c4d858",
                        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    },
                    "md5_digest": "6bd3ddc295176f4dca196b5eb2c4d858",
                    "size": 12345,
                    "upload_time_iso_8601": "2000-03-03T01:23:45.123456Z",
                    "yanked": False,
                },
            ]
        },
    }


@pytest.fixture
def master(package_json: dict[str, Any]) -> "Master":
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

        async def json(self, *args: Any) -> dict[str, Any]:
            return package_json

    def session_side_effect(*args: Any, **kwargs: Any) -> Any:
        if args[0].startswith("https://not-working.example.com"):
            raise AssertionError("Requested for expected not-working URL")
        else:
            return FakeAiohttpClient()

    master = Master("https://pypi.example.com")
    master.rpc = mock.Mock()  # type: ignore
    master.session = mock.MagicMock()
    master.session.get.side_effect = session_side_effect
    master.session.request.side_effect = session_side_effect
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

    # Mock the synchronize method too to avoid TypeError exceptions since methods are
    # by default replaced by MagicMock instances when AsyncMock is necessary.
    instance = mirror.return_value
    instance.synchronize = mock.AsyncMock(return_value={})

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


@pytest.fixture()
def reset_configuration_cache() -> Iterator[None]:
    try:
        _s3_accessor.configuration_map.get_configuration.cache_clear()
        yield
    finally:
        _s3_accessor.configuration_map.get_configuration.cache_clear()


@pytest.fixture()
def s3_mock(reset_configuration_cache: None) -> S3Path:
    if os.environ.get("os") != "ubuntu-latest" and os.environ.get("CI"):
        pytest.skip("Skip s3 test on non-posix server in github action")
    register_configuration_parameter(
        PureS3Path("/"),
        resource=boto3.resource(
            "s3",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            endpoint_url="http://localhost:9000",
        ),
    )
    new_bucket = S3Path("/test-bucket")
    new_bucket.mkdir(exist_ok=True)
    yield new_bucket
    resource, _ = new_bucket._accessor.configuration_map.get_configuration(new_bucket)
    bucket = resource.Bucket(new_bucket.bucket)
    for key in bucket.objects.all():
        key.delete()
    bucket.delete()
