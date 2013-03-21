from bandersnatch.master import Master
import pytest
import mock

@pytest.fixture
def master():
    master = Master('http://pypi.example.com')
    master.rpc = mock.Mock()
    return master

def test_rpc_url(master):
    assert master.xmlrpc_url == 'http://pypi.example.com/pypi/'

def test_list_packages(master):
    master.list_packages()
    assert master.rpc().list_packages.called

def test_changed_packages_no_changes(master):
    master.rpc().changelog_since_serial.return_value = []
    changes, last_serial = master.changed_packages(4)
    assert list(changes) == []
    assert last_serial == 4

def test_changed_packages_with_changes(master):
    master.rpc().changelog_since_serial.return_value = [
            ('foobar', 17),
            ('baz', 18)]
    changes, last_serial = master.changed_packages(4)
    assert list(changes) == ['foobar', 'baz']
    assert last_serial == 18
