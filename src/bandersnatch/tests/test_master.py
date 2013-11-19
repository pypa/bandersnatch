from bandersnatch.master import Master, StalePage
import pytest
import sys
import xmlrpclib


def test_rpc_factory():
    master = Master('http://pypi.example.com')
    assert isinstance(master.rpc(), xmlrpclib.ServerProxy)


def test_rpc_url(master):
    assert master.xmlrpc_url == 'http://pypi.example.com/pypi/'


def test_all_packages(master):
    master.all_packages()


def test_changed_packages_no_changes(master):
    master.rpc().changelog_since_serial.return_value = {}
    changes = master.changed_packages(4)
    assert changes == {}


def test_changed_packages_with_changes(master):
    master.rpc().changelog_since_serial.return_value = [
        ('foobar', '1', 0, 'added', 17),
        ('baz', '2', 1, 'updated', 18),
        ('foobar', '1', 0, 'changed', 20),
        # The server usually just hands our monotonous serials in the
        # changelog. This verifies that we don't fail even with garbage input.
        ('foobar', '1', 0, 'changed', 19)]
    changes = master.changed_packages(4)
    assert changes == {'baz': 18, 'foobar': 20}


def test_package_releases(master):
    master.package_releases('foobar')


def test_release_urls(master):
    master.release_urls('foobar', '0.1')


def test_transport_reuses_connection():
    from bandersnatch.master import CustomTransport
    t = CustomTransport()
    t._connection = ('localhost', 'existing-connection')
    assert t.make_connection('localhost') == 'existing-connection'


def test_transport_creates_new_http_connection(httplib):
    from bandersnatch.master import CustomTransport
    t = CustomTransport()
    t.make_connection('localhost')
    if sys.version_info < (2, 7):
        assert (t.make_connection('localhost') is
                httplib['httplib.HTTP']())
    else:
        assert (t.make_connection('localhost') is
                httplib['httplib.HTTPConnection']())


def test_transport_creates_new_https_connection(httplib):
    from bandersnatch.master import CustomTransport
    t = CustomTransport(ssl=True)
    t.make_connection('localhost')
    if sys.version_info < (2, 7):
        assert (t.make_connection('localhost') is
                httplib['httplib.HTTPS']())
    else:
        assert (t.make_connection('localhost') is
                httplib['httplib.HTTPSConnection']())


def test_transport_raises_on_missing_https_implementation(no_https):
    from bandersnatch.master import CustomTransport
    t = CustomTransport(ssl=True)
    with pytest.raises(NotImplementedError):
        t.make_connection('localhost')


def test_master_raises_if_serial_too_small(master, requests):
    requests.prepare('foo', 1)
    with pytest.raises(StalePage):
        master.get('/asdf', 10)


def test_master_doesnt_raise_if_serial_equal(master, requests):
    requests.prepare('foo', 1)
    master.get('/asdf', 1)


def test_master_doesnt_raise_if_serial_bigger(master, requests):
    requests.prepare('foo', 10)
    master.get('/asdf', 1)
