# flake8: noqa
import asyncio
import unittest.mock as mock
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from pytest_mock import MockerFixture

import bandersnatch.storage

if TYPE_CHECKING:
    from s3path import S3Path

    from bandersnatch.master import Master
    from bandersnatch.mirror import BandersnatchMirror
    from bandersnatch.package import Package


@pytest.fixture(scope="function", autouse=True)
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """
    Create an event loop for each test.

    This is needed for Python 3.14+ where asyncio.get_event_loop() no longer
    automatically creates an event loop. Many bandersnatch classes (Master, Mirror,
    StoragePlugin) call asyncio.get_event_loop() in their __init__ methods, so we
    need to ensure an event loop exists even for non-async tests.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    try:
        # Cancel all running tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Run the loop until all tasks are cancelled
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def stop_std_logging(mocker: MockerFixture) -> None:
    mocker.patch("bandersnatch.log.setup_logging")


async def _nosleep(*args: Any) -> None:
    pass


@pytest.fixture(autouse=True)
def never_sleep(mocker: MockerFixture) -> None:
    mocker.patch("asyncio.sleep", _nosleep)


# Recreate storage plugins between test modules to prevent later tests
# from re-using storage plugins initialized by earlier ones.
def _reset_storage_plugins() -> None:
    bandersnatch.storage.loaded_storage_plugins = defaultdict(list)


reset_storage_plugins = pytest.fixture(_reset_storage_plugins)
reset_storage_plugins_per_module = pytest.fixture(
    _reset_storage_plugins, scope="module", autouse=True
)


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
                        "sha256": (
                            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                        ),
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
                        "sha256": (
                            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                        ),
                    },
                    "md5_digest": "6bd3ddc295176f4dca196b5eb2c4d858",
                    "size": 12345,
                    "upload_time_iso_8601": "2000-03-03T01:23:45.123456Z",
                    "yanked": False,
                },
            ]
        },
    }


# The master fixture is an async fixture that returns a Master instance for testing.
@pytest_asyncio.fixture
async def master(package_json: dict[str, Any]) -> "Master":
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
    master.session = mock.MagicMock()
    master.session.get.side_effect = session_side_effect
    master.session.request.side_effect = session_side_effect
    return master


@pytest.fixture
def mirror(
    tmpdir: Path, master: "Master", monkeypatch: pytest.MonkeyPatch
) -> "BandersnatchMirror":
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import BandersnatchMirror

    return BandersnatchMirror(tmpdir, master)


@pytest.fixture
def mirror_hash_index(
    tmpdir: Path, master: "Master", monkeypatch: pytest.MonkeyPatch
) -> "BandersnatchMirror":
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import BandersnatchMirror

    return BandersnatchMirror(tmpdir, master, hash_index=True)


@pytest.fixture
def mirror_mock(mocker: MockerFixture) -> mock.MagicMock:
    mirror: mock.MagicMock = mocker.patch("bandersnatch.mirror.BandersnatchMirror")

    # Mock the synchronize method too to avoid TypeError exceptions since methods are
    # by default replaced by MagicMock instances when AsyncMock is necessary.
    instance = mirror.return_value
    instance.synchronize = mock.AsyncMock(return_value={})

    return mirror


@pytest.fixture
def logging_mock(mocker: MockerFixture) -> Any:
    return mocker.patch("logging.config.fileConfig")


@pytest.fixture()
def reset_configuration_cache() -> Iterator[None]:
    try:
        from s3path import accessor
    except ImportError:
        yield
        return

    try:
        accessor.configuration_map.get_configuration.cache_clear()
        yield
    finally:
        accessor.configuration_map.get_configuration.cache_clear()


@pytest.fixture()
def s3_mock(
    reset_configuration_cache: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator["S3Path"]:
    # makes sure other tests are not skipped if s3 deps are missing
    boto3 = pytest.importorskip("boto3", reason="s3path/boto3 not installed")
    s3path_mod = pytest.importorskip("s3path", reason="s3path not installed")
    mock_aws = pytest.importorskip("moto", reason="moto not installed").mock_aws

    PureS3Path = s3path_mod.PureS3Path
    S3Path = s3path_mod.S3Path
    register_configuration_parameter = s3path_mod.register_configuration_parameter

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    with mock_aws():
        resource = boto3.resource("s3", region_name="us-east-1")
        resource.create_bucket(Bucket="test-bucket")
        register_configuration_parameter(
            PureS3Path("/"),
            resource=resource,
        )
        new_bucket = S3Path("/test-bucket")
        yield new_bucket
