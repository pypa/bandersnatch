import pytest
import xmlrpc2

from bandersnatch.master import Master, StalePage


def test_rpc_factory():
    master = Master("https://pypi.example.com")
    assert isinstance(master.rpc(), xmlrpc2.client.Client)


def test_disallow_http():
    with pytest.raises(ValueError):
        Master("http://pypi.example.com")


def test_rpc_url(master):
    assert master.xmlrpc_url == "https://pypi.example.com/pypi"


def test_all_packages(master):
    master.all_packages()


def test_changed_packages_no_changes(master):
    master.rpc().changelog_since_serial.return_value = {}
    changes = master.changed_packages(4)
    assert changes == {}


def test_changed_packages_with_changes(master):
    master.rpc().changelog_since_serial.return_value = [
        ("foobar", "1", 0, "added", 17),
        ("baz", "2", 1, "updated", 18),
        ("foobar", "1", 0, "changed", 20),
        # The server usually just hands out monotonous serials in the
        # changelog. This verifies that we don't fail even with garbage input.
        ("foobar", "1", 0, "changed", 19),
    ]
    changes = master.changed_packages(4)
    assert changes == {"baz": 18, "foobar": 20}


def test_master_raises_if_serial_too_small(master, requests):
    requests.prepare("foo", 1)
    with pytest.raises(StalePage):
        master.get("/asdf", 10)


def test_master_doesnt_raise_if_serial_equal(master, requests):
    requests.prepare("foo", 1)
    master.get("/asdf", 1)


def test_master_doesnt_raise_if_serial_bigger(master, requests):
    requests.prepare("foo", 10)
    master.get("/asdf", 1)
