import mock
import pytest


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
def mirror(tmpdir, master):
    from bandersnatch.mirror import Mirror
    return Mirror(str(tmpdir), master)
