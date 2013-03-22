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
def logging():
    from bandersnatch.mirror import setup_logging
    setup_logging()


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
