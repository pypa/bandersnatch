"""
Implements 2 aspects of network proxy support:

1. Detecting proxy configuration in the runtime environment
2. Configuring aiohttp for different proxy protocol families
"""

import logging
import urllib.request
from collections.abc import Mapping
from typing import Any

from aiohttp_socks import ProxyConnector

logger = logging.getLogger(__name__)

# The protocols we accept from 'getproxies()' in the an arbitrary but reasonable seeming precedence order.
# These roughly correspond to environment variables `(f"{p.upper()}_PROXY" for p in _supported_protocols)`.
_supported_protocols = (
    "socks5",
    "socks4",
    "socks",
    "https",
    "http",
    "all",
)


def proxy_address_from_env() -> str | None:
    """
    Find an HTTP or SOCKS proxy server URL in the environment using urllib's
    'getproxies' function. This checks both environment variables and OS-specific sources
    like the Windows registry and returns a mapping of protocol name to address. If there
    are URLs for multiple protocols we use an arbitrary precedence order based roughly on
    protocol sophistication and specificity:

    'socks5' > 'socks4' > 'https' > 'http' > 'all'

    Note that nothing actually constrains the value of an environment variable to have a
    URI scheme/protocol that matches the protocol indicated by the variable name - e.g.
    not only is `ALL_PROXY=socks4://...` possible but so is `HTTP_PROXY=socks4://...`. We
    use the protocol from the variable name for address selection but should generate
    connection configuration based on the scheme.
    """
    proxies_in_env = urllib.request.getproxies()
    for proto in _supported_protocols:
        if proto in proxies_in_env:
            address = proxies_in_env[proto]
            logger.debug("Found %s proxy address in environment: %s", proto, address)
            return address
    return None


def get_aiohttp_proxy_kwargs(proxy_url: str) -> Mapping[str, Any]:
    """
    Return initializer keyword arguments for `aiohttp.ClientSession` for either an HTTP
    or SOCKS proxy based on the scheme of the given URL.

    Proxy support uses aiohttp's built-in support for HTTP(S), and uses aiohttp_socks for
    SOCKS{4,5}. Initializing an aiohttp session is different for each. An HTTP proxy
    address can be passed to ClientSession's 'proxy' option:

        ClientSession(..., proxy=<PROXY_ADDRESS>, trust_env=True)

    'trust_env' enables aiohttp to read additional configuration from environment variables
    and net.rc. `aiohttp_socks` works by replacing the default transport (TcpConnector)
    with a custom one:

        socks_transport = aiohttp_socks.ProxyConnector.from_url(<PROXY_ADDRESS>)
        ClientSession(..., connector=socks_transport)

    This uses the protocol family of the URL to select one or the other and return the
    corresponding keyword arguments in a dictionary.
    """
    lowered = proxy_url.lower()
    if lowered.startswith("socks"):
        logger.debug("Using SOCKS ProxyConnector for %s", proxy_url)
        return {"connector": ProxyConnector.from_url(proxy_url)}

    if lowered.startswith("http"):
        logger.debug("Using HTTP proxy address %s", proxy_url)
        return {"proxy": proxy_url, "trust_env": True}

    return {}
