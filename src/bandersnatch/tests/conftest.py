import unittest.mock as mock
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
        if isinstance(content, Exception):
            responses.append(content)
            return
        download = mock.Mock()
        download.iter_content.return_value = iter([content])
        download.content = content
        download.json.return_value = content
        download.headers = {'X-PYPI-LAST-SERIAL': str(serial)}
        responses.append(download)
    requests.prepare = prepare

    def side_effect(*args, **kw):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    requests.side_effect = side_effect
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
def mirror_hash_index(tmpdir, master, monkeypatch):
    monkeypatch.chdir(tmpdir)
    from bandersnatch.mirror import Mirror
    return Mirror(str(tmpdir), master, hash_index=True)


@pytest.fixture
def mirror_mock(request):
    patcher = mock.patch('bandersnatch.mirror.Mirror')
    mirror = patcher.start()

    def tearDown():
        patcher.stop()
    request.addfinalizer(tearDown)
    return mirror


@pytest.fixture
def logging_mock(request):
    patcher = mock.patch('logging.config.fileConfig')
    logger = patcher.start()

    def tearDown():
        patcher.stop()
    request.addfinalizer(tearDown)
    return logger
