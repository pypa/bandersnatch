# flake8: noqa

import unittest.mock as mock

import pytest
from asynctest import asynctest


@pytest.fixture(autouse=True)
def stop_std_logging(request, capfd):
    patcher = mock.patch("bandersnatch.log.setup_logging")
    patcher.start()

    def tearDown():
        patcher.stop()

    request.addfinalizer(tearDown)


async def _nosleep(*args):
    pass


@pytest.fixture(autouse=True)
def never_sleep(request):
    patcher = mock.patch("asyncio.sleep", _nosleep)
    patcher.start()

    def tearDown():
        patcher.stop()

    request.addfinalizer(tearDown)


@pytest.fixture
def master():
    from bandersnatch.master import Master

    class FakeReader:
        async def read(self, *args):
            return b""

    class FakeAiohttpClient:
        headers = {"X-PYPI-LAST-SERIAL": "1"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def content(self, *args):
            return FakeReader()

        async def json(self, *args):
            return {
                "info": {"name": "foo", "version": "0.1"},
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
                        },
                    ]
                },
            }

    master = Master("https://pypi.example.com")
    master.rpc = mock.Mock()
    master.session = asynctest.MagicMock()
    master.session.get = asynctest.MagicMock(return_value=FakeAiohttpClient())
    master.session.request = asynctest.MagicMock(return_value=FakeAiohttpClient())
    return master


@pytest.fixture
def mirror(tmpdir, master, monkeypatch):
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import Mirror

    return Mirror(str(tmpdir), master)


@pytest.fixture
def mirror_hash_index(tmpdir, master, monkeypatch):
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import Mirror

    return Mirror(str(tmpdir), master, hash_index=True)


@pytest.fixture
def mirror_mock(request):
    patcher = mock.patch("bandersnatch.mirror.Mirror")
    mirror = patcher.start()

    def tearDown():
        patcher.stop()

    request.addfinalizer(tearDown)
    return mirror


@pytest.fixture
def logging_mock(request):
    patcher = mock.patch("logging.config.fileConfig")
    logger = patcher.start()

    def tearDown():
        patcher.stop()

    request.addfinalizer(tearDown)
    return logger
