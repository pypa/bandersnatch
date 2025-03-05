import concurrent.futures
from pathlib import Path
from tempfile import gettempdir
from unittest.mock import AsyncMock, patch

import pytest

import bandersnatch
from bandersnatch.master import Master, StalePage


@pytest.mark.asyncio
async def test_disallow_http() -> None:
    with pytest.raises(ValueError):
        Master("http://pypi.example.com")


@pytest.mark.asyncio
async def test_self_simple_url(master: Master) -> None:
    assert master.simple_url == "https://pypi.example.com/simple/"


@pytest.mark.asyncio
async def test_all_packages(master: Master) -> None:
    simple_index = {
        "meta": {"_last-serial": 22, "api-version": "1.1"},
        "projects": [
            {"_last-serial": 20, "name": "foobar"},
            {"_last-serial": 18, "name": "baz"},
        ],
    }

    master.fetch_simple_index = AsyncMock(return_value=simple_index)  # type: ignore
    packages = await master.all_packages()
    assert packages == {"foobar": 20, "baz": 18}


@pytest.mark.asyncio
async def test_changed_packages_no_changes(master: Master) -> None:
    master.fetch_simple_index = AsyncMock(return_value=None)  # type: ignore
    changes = await master.changed_packages(4)
    assert changes == {}


@pytest.mark.asyncio
async def test_changed_packages_with_changes(master: Master) -> None:
    simple_index = {
        "meta": {"_last-serial": 22, "api-version": "1.1"},
        "projects": [
            {"_last-serial": 20, "name": "foobar"},
            {"_last-serial": 18, "name": "baz"},
        ],
    }
    master.fetch_simple_index = AsyncMock(return_value=simple_index)  # type: ignore
    changes = await master.changed_packages(4)
    assert changes == {"foobar": 20, "baz": 18}


@pytest.mark.asyncio
async def test_master_raises_if_serial_too_small(master: Master) -> None:
    get_ag = master.get("/asdf", 10)
    with pytest.raises(StalePage):
        await get_ag.asend(None)


@pytest.mark.asyncio
async def test_master_doesnt_raise_if_serial_equal(master: Master) -> None:
    get_ag = master.get("/asdf", 1)
    await get_ag.asend(None)


@pytest.mark.asyncio
async def test_master_url_fetch(master: Master) -> None:
    fetch_path = Path(gettempdir()) / "unittest_url_fetch"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as thread_pool:
        await master.url_fetch("https://unittest.org/asdf", fetch_path, thread_pool)
    assert master.session.get.called


@pytest.mark.asyncio
async def test__simple_index_user_agent(master: Master) -> None:
    headers = master._custom_headers
    assert f"bandersnatch {bandersnatch.__version__}" in headers["User-Agent"]


@pytest.mark.asyncio
async def test_session_raise_for_status(master: Master) -> None:
    with patch("aiohttp.ClientSession", autospec=True) as create_session:
        async with master:
            pass
        assert len(create_session.call_args_list) == 1
        assert create_session.call_args_list[0][1]["raise_for_status"]
