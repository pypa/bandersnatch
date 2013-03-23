import mock
import pytest


@pytest.fixture
def requests(request):
    patcher = mock.patch('requests.get')
    requests = patcher.start()
    def tearDown():
        patcher.stop()
    request.addfinalizer(tearDown)
    return requests


@pytest.fixture(autouse=True)
def logging(request):
    from bandersnatch.main import setup_logging
    import logging
    handler = setup_logging()
    def tearDown():
        logger = logging.getLogger('bandersnatch')
        logger.removeHandler(handler)
    request.addfinalizer(tearDown)


@pytest.fixture
def master():
    from bandersnatch.master import Master
    master = Master('http://pypi.example.com')
    master.rpc = mock.Mock()
    return master


@pytest.fixture
def mirror(tmpdir, master, monkeypatch):
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import Mirror
    return Mirror(str(tmpdir), master)


@pytest.fixture
def master_mock():
    master = mock.Mock()
    master.url = 'http://pypi.example.com'
    return master


@pytest.fixture
def mirror_mock(request):
    patcher = mock.patch('bandersnatch.mirror.Mirror')
    mirror = patcher.start()
    def tearDown():
        patcher.stop()
    request.addfinalizer(tearDown)
    return mirror
