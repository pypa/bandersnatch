from bandersnatch.master import Master
import xmlrpclib


def test_rpc_factory():
    master = Master('http://pypi.example.com')
    assert isinstance(master.rpc(), xmlrpclib.ServerProxy)


def test_rpc_url(master):
    assert master.xmlrpc_url == 'http://pypi.example.com/pypi/'


def test_list_packages(master):
    master.list_packages()


def test_changed_packages_no_changes(master):
    master.rpc().changelog_since_serial.return_value = []
    changes, last_serial = master.changed_packages(4)
    assert list(changes) == []
    assert last_serial == 4


def test_changed_packages_with_changes(master):
    master.rpc().changelog_since_serial.return_value = [
        ('foobar', 17), ('baz', 18)]
    changes, last_serial = master.changed_packages(4)
    assert list(changes) == ['foobar', 'baz']
    assert last_serial == 18


def test_package_releases(master):
    master.package_releases('foobar')


def test_release_urls(master):
    master.release_urls('foobar', '0.1')


def test_get_current_serial(master):
    master.get_current_serial()
