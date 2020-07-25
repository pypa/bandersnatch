from pathlib import Path
from tempfile import gettempdir

import asynctest
import pytest

import bandersnatch
from bandersnatch.master import Master, StalePage, XmlRpcError


def test_disallow_http() -> None:
    with pytest.raises(ValueError):
        Master("http://pypi.example.com")


def test_rpc_url(master: Master) -> None:
    assert master.xmlrpc_url == "https://pypi.example.com/pypi"


@pytest.mark.asyncio
async def test_all_packages(master: Master) -> None:
    expected = [["aiohttp", "", "", "", "69"]]
    master.rpc = asynctest.CoroutineMock(return_value=expected)  # type: ignore
    pacakges = await master.all_packages()
    assert expected == pacakges


@pytest.mark.asyncio
async def test_all_packages_raises(master: Master) -> None:
    master.rpc = asynctest.CoroutineMock(return_value=[])  # type: ignore
    with pytest.raises(XmlRpcError):
        await master.all_packages()


@pytest.mark.asyncio
async def test_changed_packages_no_changes(master: Master) -> None:
    master.rpc = asynctest.CoroutineMock(return_value=None)  # type: ignore
    changes = await master.changed_packages(4)
    assert changes == {}


@pytest.mark.asyncio
async def test_changed_packages_with_changes(master: Master) -> None:
    list_of_package_changes = [
        ("foobar", "1", 0, "added", 17),
        ("baz", "2", 1, "updated", 18),
        ("foobar", "1", 0, "changed", 20),
        # The server usually just hands out monotonous serials in the
        # changelog. This verifies that we don't fail even with garbage input.
        ("foobar", "1", 0, "changed", 19),
    ]
    master.rpc = asynctest.CoroutineMock(  # type: ignore
        return_value=list_of_package_changes
    )
    changes = await master.changed_packages(4)
    assert changes == {"baz": 18, "foobar": 20}


@pytest.mark.asyncio
async def test_master_raises_if_serial_too_small(master: Master) -> None:
    get_ag = master.get("/asdf", 10)
    with pytest.raises(StalePage):
        await get_ag.asend(None)
    assert master.session.request.called


@pytest.mark.asyncio
async def test_master_doesnt_raise_if_serial_equal(master: Master) -> None:
    get_ag = master.get("/asdf", 1)
    await get_ag.asend(None)


@pytest.mark.asyncio
async def test_master_url_fetch(master: Master) -> None:
    fetch_path = Path(gettempdir()) / "unittest_url_fetch"
    await master.url_fetch("https://unittest.org/asdf", fetch_path)
    assert master.session.get.called


@pytest.mark.asyncio
async def test_xmlrpc_user_agent(master: Master) -> None:
    client = await master._gen_xmlrpc_client()
    assert f"bandersnatch {bandersnatch.__version__}" in client.headers["User-Agent"]


@pytest.mark.asyncio
async def test_session_raise_for_status(master: Master) -> None:
    patcher = asynctest.patch("aiohttp.ClientSession", autospec=True)
    with patcher as create_session:
        async with master:
            pass
        assert len(create_session.call_args_list) == 1
        assert create_session.call_args_list[0][1]["raise_for_status"]
