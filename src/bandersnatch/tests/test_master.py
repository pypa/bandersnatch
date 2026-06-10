import concurrent.futures
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from unittest.mock import patch

import pytest

from bandersnatch.master import Master, StalePage


@pytest.mark.asyncio
async def test_disallow_http() -> None:
    with pytest.raises(ValueError):
        Master("http://pypi.example.com")


@pytest.mark.asyncio
async def test_all_packages(master: Master) -> None:
    # Mock fetch_simple_index for simple API
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {
            "meta": {"api-version": "1.0"},
            "projects": [{"name": "aiohttp", "_last-serial": 69}],
        }

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore
    packages = await master.all_packages()
    assert packages == {"aiohttp": 69}


@pytest.mark.asyncio
async def test_all_packages_raises(master: Master) -> None:
    # Simple API returns empty dict when no packages, doesn't raise
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {"meta": {"api-version": "1.0"}, "projects": []}

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore
    packages = await master.all_packages()
    assert packages == {}


@pytest.mark.asyncio
async def test_changed_packages_no_changes(master: Master) -> None:
    # Mock fetch_simple_index to return packages with serials <= 4
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {
            "meta": {"api-version": "1.0"},
            "projects": [
                {"name": "aiohttp", "_last-serial": 3},
                {"name": "requests", "_last-serial": 4},
            ],
        }

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore
    changes = await master.changed_packages(4)
    assert changes == {}


@pytest.mark.asyncio
async def test_changed_packages_with_changes(master: Master) -> None:
    # Mock fetch_simple_index to return packages with serials > 4
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {
            "meta": {"api-version": "1.0"},
            "projects": [
                {"name": "foobar", "_last-serial": 20},
                {"name": "baz", "_last-serial": 18},
                {"name": "old-package", "_last-serial": 3},
            ],
        }

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore
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
    master = Master("https://pypi.example.com")

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
    master = Master("https://pypi.example.com")

    # Mock fetch_simple_index to return empty response
    async def mock_fetch_simple_index() -> dict[str, Any]:
        return {"meta": {"api-version": "1.0"}, "projects": []}

    master.fetch_simple_index = mock_fetch_simple_index  # type: ignore

    # Should return empty dict, not raise exception
    packages = await master.all_packages()
    assert packages == {}


@pytest.mark.asyncio
async def test_changed_packages_simple_api() -> None:
    """Test fetching changed packages using Simple (PEP 691 v1) API."""
    master = Master("https://pypi.example.com")

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
    master = Master("https://pypi.example.com")

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
async def test_master_uses_simple_api() -> None:
    """Test that Master uses the Simple API for package lookups."""
    master = Master("https://pypi.example.com")
    assert master.simple_url == "https://pypi.example.com/simple"
