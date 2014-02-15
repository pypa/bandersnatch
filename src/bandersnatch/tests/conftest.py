import mock
import pytest


@pytest.fixture
def requests(request):
    patcher = mock.patch('requests.get')
    requests = patcher.start()

    def tearDown():
        patcher.stop()
    request.addfinalizer(tearDown)

    responses = []

    def prepare(content, serial):
        download = mock.Mock()
        download.iter_content.return_value = iter(content)
        download.content = content
        download.headers = {'X-PYPI-LAST-SERIAL': str(serial)}
        responses.append(download)
    requests.prepare = prepare
    requests.side_effect = lambda *args, **kw: responses.pop(0)
    return requests


@pytest.fixture(autouse=True)
def stop_std_logging(request, capfd):
    patcher = mock.patch('bandersnatch.log.setup_logging')
    patcher.start()

    def tearDown():
        patcher.stop()
    request.addfinalizer(tearDown)


@pytest.fixture
def master(requests):
    from bandersnatch.master import Master
    master = Master('https://pypi.example.com')
    master.rpc = mock.Mock()
    master.session = mock.Mock()
    master.session.get = requests
    return master


@pytest.fixture
def mirror(tmpdir, master, monkeypatch):
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import Mirror
    return Mirror(str(tmpdir), master)


@pytest.fixture
def master_mock():
    master = mock.Mock()
    master.url = 'https://pypi.example.com'
    return master


@pytest.fixture
def mirror_mock(request):
    patcher = mock.patch('bandersnatch.mirror.Mirror')
    mirror = patcher.start()

    def tearDown():
        patcher.stop()
    request.addfinalizer(tearDown)
    return mirror
