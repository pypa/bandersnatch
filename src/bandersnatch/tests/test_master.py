import concurrent.futures
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import bandersnatch
from bandersnatch.master import Master, StalePage, XmlRpcError


@pytest.mark.asyncio
async def test_disallow_http() -> None:
    with pytest.raises(ValueError):
        Master("http://pypi.example.com")


@pytest.mark.asyncio
async def test_rpc_url(master: Master) -> None:
    assert master.xmlrpc_url == "https://pypi.example.com/pypi"


@pytest.mark.asyncio
async def test_all_packages(master: Master) -> None:
    expected = [["aiohttp", "", "", "", "69"]]
    master.rpc = AsyncMock(return_value=expected)  # type: ignore
    packages = await master.all_packages()
    assert expected == packages


@pytest.mark.asyncio
async def test_all_packages_raises(master: Master) -> None:
    master.rpc = AsyncMock(return_value=[])  # type: ignore
    with pytest.raises(XmlRpcError):
        await master.all_packages()


@pytest.mark.asyncio
async def test_changed_packages_no_changes(master: Master) -> None:
    master.rpc = AsyncMock(return_value=None)  # type: ignore
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
    master.rpc = AsyncMock(return_value=list_of_package_changes)  # type: ignore
    changes = await master.changed_packages(4)
    assert changes == {"baz": 18, "foobar": 20}


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
async def test_xmlrpc_user_agent(master: Master) -> None:
    client = await master._gen_xmlrpc_client()
    assert f"bandersnatch {bandersnatch.__version__}" in client.headers["User-Agent"]


@pytest.mark.asyncio
async def test_session_raise_for_status(master: Master) -> None:
    with patch("aiohttp.ClientSession", autospec=True) as create_session:
        async with master:
            pass
        assert len(create_session.call_args_list) == 1
        assert create_session.call_args_list[0][1]["raise_for_status"]


# Tests for Simple API (PEP 691 v1)


@pytest.mark.asyncio
async def test_all_packages_simple_api() -> None:
    """Test fetching all packages using the Simple (PEP 691 v1) API."""
    master = Master("https://pypi.example.com", api_method="simple")

    # Mock fetch_simple_index to return Simple API response
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {
            "meta": {"api-version": "1.0"},
            "projects": [
                {"name": "aiohttp", "_last-serial": 12345},
                {"name": "requests", "_last-serial": 12346},
                {"name": "django", "_last-serial": 12347},
            ],
        }

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore

    packages = await master.all_packages()

    # Verify response parsing
    assert packages == {"aiohttp": 12345, "requests": 12346, "django": 12347}


@pytest.mark.asyncio
async def test_all_packages_simple_api_empty_response() -> None:
    """Test Simple API handling of empty package list."""
    master = Master("https://pypi.example.com", api_method="simple")

    # Mock fetch_simple_index to return empty response
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {"meta": {"api-version": "1.0"}, "projects": []}

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore

    # Should return empty dict, not raise exception
    packages = await master.all_packages()
    assert packages == {}


@pytest.mark.asyncio
async def test_all_packages_xmlrpc_api() -> None:
    """Test fetching all packages using XML-RPC API (default)."""
    master = Master("https://pypi.example.com", api_method="xmlrpc")

    expected = {"aiohttp": 69, "requests": 70}
    master.rpc = AsyncMock(return_value=expected)  # type: ignore

    packages = await master.all_packages()

    master.rpc.assert_called_once_with("list_packages_with_serial")
    assert packages == expected


@pytest.mark.asyncio
async def test_changed_packages_simple_api() -> None:
    """Test fetching changed packages using Simple (PEP 691 v1) API."""
    master = Master("https://pypi.example.com", api_method="simple")

    # Mock fetch_simple_index to return Simple API response with different serials
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {
            "meta": {"api-version": "1.0"},
            "projects": [
                {"name": "aiohttp", "_last-serial": 12345},
                {"name": "requests", "_last-serial": 12346},
                {"name": "django", "_last-serial": 12347},
            ],
        }

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore

    # Request changes since serial 10000
    changes = await master.changed_packages(10000)

    # Should return all packages with serial > 10000
    assert changes == {"aiohttp": 12345, "requests": 12346, "django": 12347}


@pytest.mark.asyncio
async def test_changed_packages_simple_api_no_changes() -> None:
    """Test Simple API when no changes occurred (current serial <= last serial)."""
    master = Master("https://pypi.example.com", api_method="simple")

    # Mock fetch_simple_index to return packages with lower serials
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {
            "meta": {"api-version": "1.0"},
            "projects": [
                {"name": "aiohttp", "_last-serial": 12340},
                {"name": "requests", "_last-serial": 12345},
            ],
        }

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore

    # Request changes since serial 12345 (same as or higher than current)
    changes = await master.changed_packages(12345)

    # Should return empty dict when no packages have serial > 12345
    assert changes == {}


@pytest.mark.asyncio
async def test_changed_packages_xmlrpc_api() -> None:
    """Test fetching changed packages using XML-RPC API (default)."""
    master = Master("https://pypi.example.com", api_method="xmlrpc")

    list_of_changes = [
        ("aiohttp", "1.0", 0, "added", 17),
        ("requests", "2.0", 1, "updated", 18),
    ]
    master.rpc = AsyncMock(return_value=list_of_changes)  # type: ignore

    changes = await master.changed_packages(10)

    master.rpc.assert_called_once_with("changelog_since_serial", 10)
    assert changes == {"aiohttp": 17, "requests": 18}


@pytest.mark.asyncio
async def test_master_defaults_to_xmlrpc() -> None:
    """Test that Master defaults to xmlrpc when api_method is not specified."""
    master = Master("https://pypi.example.com")
    assert master.api_method == "xmlrpc"


@pytest.mark.asyncio
async def test_master_accepts_simple_api_method() -> None:
    """Test that Master accepts 'simple' as api_method."""
    master = Master("https://pypi.example.com", api_method="simple")
    assert master.api_method == "simple"
