import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional

import aiohttp
from aiohttp_xmlrpc.client import ServerProxy

import bandersnatch

from .utils import USER_AGENT

logger = logging.getLogger(__name__)
PYPI_SERIAL_HEADER = "X-PYPI-LAST-SERIAL"


class StalePage(Exception):
    """We got a page back from PyPI that doesn't meet our expected serial."""


class XmlRpcError(aiohttp.ClientError):
    """Issue getting package listing from PyPI Repository"""


class Master:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.loop = asyncio.get_event_loop()
        self.timeout = timeout
        self.url = url
        if self.url.startswith("http://"):
            err = f"Master URL {url} is not https scheme"
            logger.error(err)
            raise ValueError(err)

    async def __aenter__(self) -> "Master":
        logger.debug("Initializing Master's aiohttp ClientSession")
        custom_headers = {"User-Agent": USER_AGENT}
        skip_headers = {"User-Agent"}
        aiohttp_timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            headers=custom_headers,
            skip_auto_headers=skip_headers,
            timeout=aiohttp_timeout,
            trust_env=True,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        logger.debug("Closing Master's aiohttp ClientSession")
        await self.session.close()

    async def check_for_stale_cache(
        self, path: str, required_serial: Optional[int], got_serial: Optional[int]
    ) -> None:
        # The PYPI-LAST-SERIAL header allows us to identify cached entries,
        # e.g. via the public CDN or private, transparent mirrors and avoid us
        # injecting stale entries into the mirror without noticing.
        if required_serial is not None:
            # I am not making required_serial an optional argument because I
            # want you to think really hard before passing in None. This is a
            # really important check to achieve consistency and you should only
            # leave it out if you know what you're doing.
            if not got_serial or got_serial < required_serial:
                logger.debug(
                    f"Expected PyPI serial {required_serial} for request {path} "
                    + f"but got {got_serial}"
                )

                # HACK: The following attempts to purge the cache of the page we
                # just tried to fetch. This works around PyPI's caches sometimes
                # returning a stale serial for a package. Ideally, this should
                # be fixed on the PyPI side, at which point the following code
                # should be removed.
                # Timeout: uses self.sessions's timeout value
                logger.debug(f"Issuing a PURGE for {path} to clear the cache")
                try:
                    async with self.session.request("PURGE", path):
                        pass
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    logger.warning(
                        "Got an error when attempting to clear the cache", exc_info=True
                    )

                raise StalePage(
                    f"Expected PyPI serial {required_serial} for request {path} "
                    + f"but got {got_serial}. "
                    + "HTTP PURGE has been issued to the request url"
                )

    async def get(
        self, path: str, required_serial: Optional[int], **kw: Any
    ) -> AsyncGenerator[aiohttp.ClientResponse, None]:
        logger.debug(f"Getting {path} (serial {required_serial})")
        if not path.startswith(("https://", "http://")):
            path = self.url + path

        timeout = self.timeout
        if "timeout" in kw:
            timeout = aiohttp.ClientTimeout(total=kw["timeout"])
            del kw["timeout"]

        async with self.session.get(path, timeout=timeout, **kw) as r:
            got_serial = (
                int(r.headers[PYPI_SERIAL_HEADER])
                if PYPI_SERIAL_HEADER in r.headers
                else None
            )
            await self.check_for_stale_cache(path, required_serial, got_serial)
            yield r

    @property
    def xmlrpc_url(self) -> str:
        return f"{self.url}/pypi"

    # TODO: Potentially make USER_AGENT more accessible from aiohttp-xmlrpc
    async def _gen_custom_headers(self) -> Dict[str, str]:
        # Create dummy client so we can copy the USER_AGENT + prepend bandersnatch info
        dummy_client = ServerProxy(self.xmlrpc_url, loop=self.loop)
        custom_headers = {
            "User-Agent": (
                f"bandersnatch {bandersnatch.__version__} {dummy_client.USER_AGENT}"
            )
        }
        # Need to close to avoid leavig open connection
        await dummy_client.client.close()
        return custom_headers

    async def _gen_xmlrpc_client(self) -> ServerProxy:
        custom_headers = await self._gen_custom_headers()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        client = ServerProxy(
            self.xmlrpc_url, loop=self.loop, headers=custom_headers, timeout=timeout
        )
        return client

    # TODO: Add an async context manager to aiohttp-xmlrpc to replace this function
    async def rpc(self, method_name: str, serial: int = 0) -> Any:
        try:
            client = await self._gen_xmlrpc_client()
            method = getattr(client, method_name)
            if serial:
                return await method(serial)
            return await method()
        except asyncio.TimeoutError as te:
            logger.error(f"Call to {method_name} @ {self.xmlrpc_url} timed out: {te}")
        finally:
            # TODO: Fix aiohttp-xml so we do not need to call ClientSession's close
            await client.client.close()

    async def all_packages(self) -> Optional[Dict[str, int]]:
        all_packages_with_serial = await self.rpc("list_packages_with_serial")
        if not all_packages_with_serial:
            raise XmlRpcError("Unable to get full list of packages")
        return all_packages_with_serial

    async def changed_packages(self, last_serial: int) -> Dict[str, int]:
        changelog = await self.rpc("changelog_since_serial", last_serial)
        if changelog is None:
            changelog = []

        packages: Dict[str, int] = {}
        for package, _version, _time, _action, serial in changelog:
            if serial > packages.get(package, 0):
                packages[package] = serial
        return packages
