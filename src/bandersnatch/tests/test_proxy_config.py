import os
from unittest.mock import patch

import pytest
from aiohttp_socks import ProxyConnector

from bandersnatch.config.proxy import get_aiohttp_proxy_kwargs, proxy_address_from_env
from bandersnatch.master import Master


@pytest.mark.parametrize(
    ("mock_env", "expected_result"),
    [
        # No environment variables => no configuration
        ({}, None),
        # Unsupported protocol => no configuration
        ({"WSS_PROXY": "wss://192.0.2.100"}, None),
        # Detect proto "http"
        ({"HTTP_PROXY": "http://192.0.2.111"}, "http://192.0.2.111"),
        # Detect proto "socks4"
        ({"SOCKS4_PROXY": "socks4://192.0.2.112:1080"}, "socks4://192.0.2.112:1080"),
        # Detect ALL_PROXY
        ({"ALL_PROXY": "socks5://192.0.2.114:1080"}, "socks5://192.0.2.114:1080"),
        # prefer https to http, if both are set
        (
            {"HTTP_PROXY": "http://192.0.2.111", "HTTPS_PROXY": "https://192.0.2.112"},
            "https://192.0.2.112",
        ),
        # prefer socks to http and socks5 to socks4
        (
            {
                "HTTPS_PROXY": "https://192.0.2.112",
                "SOCKS4_PROXY": "socks4://192.0.2.113:1080",
                "SOCKS5_PROXY": "socks5://192.0.2.114:1080",
            },
            "socks5://192.0.2.114:1080",
        ),
    ],
)
def test_proxy_address_from_env(
    mock_env: dict[str, str], expected_result: str | None
) -> None:
    with patch.dict(os.environ, mock_env, clear=True):
        actual_result = proxy_address_from_env()
        assert actual_result == expected_result


@pytest.mark.parametrize("arg", ["", "    ", "bleh", "wss://192.0.2.113"])
def test_get_aiohttp_proxy_kwargs__unsupported_arguments(
    arg: str,
) -> None:
    assert get_aiohttp_proxy_kwargs(arg) == {}


@pytest.mark.parametrize(
    "arg", ["http://192.0.2.111", "https://192.0.2.112", "HTTPS://192.0.2.112"]
)
def test_get_aiohttp_proxy_kwargs__http_urls(arg: str) -> None:
    assert get_aiohttp_proxy_kwargs(arg) == {"proxy": arg, "trust_env": True}


# (1) Although 'get_aiohttp_proxy_kwargs' is synchronous, creating an 'aiohttp_socks.ProxyConnector'
# requires an event loop b/c its initializer calls 'asyncio.get_running_loop()'.
# (2) We can't verify ProxyConnector objects with __eq__ (it isn't overriden and checks reference equality)
# and it doesn't expose any public attributes containing the host address it was instantiated with AFAICT,
# so all of the following tests have some weird contortions for SOCKS cases.
# (3) But we also don't want to completely mock away ProxyConnector.from_url b/c - I discovered - that
# bypasses some significant runtime constraints on the URLs it accepts:
# - it requires the URI have a port, even though socks4/5 have a default port
# - it doesn't support socks{4,5}h as URI schemes
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arg",
    [
        "socks4://198.51.100.111:1080",
        "socks5://198.51.100.112:1080",
        "SOCKS5://198.51.100.112:1080",
    ],
)
async def test_get_aiohttp_proxy_kwargs__socks_urls(arg: str) -> None:
    with patch.object(ProxyConnector, "from_url", wraps=ProxyConnector.from_url):
        result = get_aiohttp_proxy_kwargs(arg)
        assert "connector" in result
        assert isinstance(result["connector"], ProxyConnector)
        # mypy in vs code marks this as an 'attr-defined' error, but if you add '# type: ignore'
        # then mypy in pre-commit marks this as an 'unused-ignore' error
        ProxyConnector.from_url.assert_called_with(arg)


# The following tests of Master.__init__ inspect the 'proxy_kwargs' attribute,
# which should really be a private implementation detail, but it makes
# verification much easier.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arg", "expected_shape"),
    [
        (None, {}),
        ("", {}),
        ("http://192.0.2.111", {"proxy": str}),
        ("socks4://198.51.100.111:1080", {"connector": ProxyConnector}),
    ],
)
async def test_master_init__with_proxy_kwarg(
    arg: str, expected_shape: dict[str, type]
) -> None:
    # clear os.environ so that urllib.request.getproxies doesn't pick up
    # possible proxy configuration on the test runner
    with patch.dict(os.environ, {}, clear=True):
        mas = Master("https://unit.test/simple/", proxy=arg)
        sut = mas.proxy_kwargs
        if expected_shape == {}:
            assert sut == {}
        else:
            for key, typ in expected_shape.items():
                assert key in sut
                assert isinstance(sut[key], typ)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mock_env", "expected_shape"),
    [
        ({}, {}),
        ({"WSS_PROXY": "wss://foo.bar.baz"}, {}),
        ({"http_proxy": "http://192.0.2.111"}, {"proxy": str}),
        (
            {"SOCKS_PROXY": "socks4://198.51.100.111:1080"},
            {"connector": ProxyConnector},
        ),
        ({"ALL_PROXY": "socks5://198.51.100.112:1080"}, {"connector": ProxyConnector}),
        (
            {
                "http_proxy": "http://192.0.2.111",
                "all_proxy": "socks5://198.51.100.112:1080",
            },
            {"proxy": str},
        ),
        ({"socks4_proxy": "http://lolnotsocks.test:8080"}, {"proxy": str}),
    ],
)
async def test_master_init__with_proxy_env(
    mock_env: dict[str, str], expected_shape: dict[str, type]
) -> None:
    with patch.dict(os.environ, mock_env, clear=True):
        mas = Master("https://unit.test/simple/", proxy=None)
        sut = mas.proxy_kwargs
        if expected_shape == {}:
            assert sut == {}
        else:
            assert sut != {}
            for key, typ in expected_shape.items():
                assert key in sut
                assert isinstance(sut[key], typ)
