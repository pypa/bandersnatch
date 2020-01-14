import asyncio

import asynctest
import pytest

import bandersnatch
from bandersnatch.master import Master, StalePage

loop = asyncio.get_event_loop()


def test_disallow_http():
    with pytest.raises(ValueError):
        Master("http://pypi.example.com")


def test_rpc_url(master):
    assert master.xmlrpc_url == "https://pypi.example.com/pypi"


def test_all_packages(master):
    master.rpc = asynctest.CoroutineMock(return_value=[])
    all_packages = loop.run_until_complete(master.all_packages())
    assert len(all_packages) == 0


def test_changed_packages_no_changes(master):
    master.rpc = asynctest.CoroutineMock(return_value=None)
    changes = loop.run_until_complete(master.changed_packages(4))
    assert changes == {}


def test_changed_packages_with_changes(master):
    list_of_package_changes = [
        ("foobar", "1", 0, "added", 17),
        ("baz", "2", 1, "updated", 18),
        ("foobar", "1", 0, "changed", 20),
        # The server usually just hands out monotonous serials in the
        # changelog. This verifies that we don't fail even with garbage input.
        ("foobar", "1", 0, "changed", 19),
    ]
    master.rpc = asynctest.CoroutineMock(return_value=list_of_package_changes)
    changes = loop.run_until_complete(master.changed_packages(4))
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


def test_xmlrpc_user_agent(master):
    client = loop.run_until_complete(master._gen_xmlrpc_client())
    assert f"bandersnatch {bandersnatch.__version__}" in client.headers["User-Agent"]
