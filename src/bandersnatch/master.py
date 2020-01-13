import asyncio
import logging
from typing import Any, Dict, Optional

import requests
from aiohttp_xmlrpc.client import ServerProxy

import bandersnatch

from .utils import USER_AGENT

logger = logging.getLogger(__name__)


class StalePage(Exception):
    """We got a page back from PyPI that doesn't meet our expected serial."""


class Master:
    def __init__(self, url, timeout=10.0) -> None:
        self.url = url
        if self.url.startswith("http://"):
            err = f"Master URL {url} is not https scheme"
            logger.error(err)
            raise ValueError(err)

        self.loop = asyncio.get_event_loop()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get(self, path, required_serial, **kw):
        logger.debug(f"Getting {path} (serial {required_serial})")
        if not path.startswith(("https://", "http://")):
            path = self.url + path
        r = self.session.get(path, timeout=self.timeout, **kw)
        r.raise_for_status()
        # The PYPI-LAST-SERIAL header allows us to identify cached entries,
        # e.g. via the public CDN or private, transparent mirrors and avoid us
        # injecting stale entries into the mirror without noticing.
        if required_serial is not None:
            # I am not making required_serial an optional argument because I
            # want you to think really hard before passing in None. This is a
            # really important check to achieve consistency and you should only
            # leave it out if you know what you're doing.
            got_serial = int(r.headers["X-PYPI-LAST-SERIAL"])
            if got_serial < required_serial:
                logger.debug(
                    "Expected PyPI serial {} for request {} but got {}".format(
                        required_serial, path, got_serial
                    )
                )
                # HACK: The following attempts to purge the cache of the page we
                # just tried to fetch. This works around PyPI's caches sometimes
                # returning a stale serial for a package. Ideally, this should
                # be fixed on the PyPI side, at which point the following code
                # should be removed.
                logger.debug(f"Issuing a PURGE for {path} to clear the cache")
                try:
                    self.session.request("PURGE", path, timeout=self.timeout)
                except requests.exceptions.HTTPError:
                    logger.warning(
                        "Got an error when attempting to clear the cache", exc_info=True
                    )

                raise StalePage(
                    "Expected PyPI serial {} for request {} but got {}. "
                    + "HTTP PURGE has been issued to the request url".format(
                        required_serial, path, got_serial
                    )
                )
        return r

    @property
    def xmlrpc_url(self) -> str:
        return f"{self.url}/pypi"

    async def _gen_xmlrpc_client(self) -> ServerProxy:
        dummy_client = ServerProxy(self.xmlrpc_url, loop=self.loop)
        custom_headers = {
            "User-Agent": (
                f"bandersnatch {bandersnatch.__version__} {dummy_client.USER_AGENT}"
            )
        }
        timeouts = {"conn_timeout": self.timeout, "read_timeout": self.timeout * 2}
        client = ServerProxy(
            self.xmlrpc_url, loop=self.loop, headers=custom_headers, **timeouts
        )
        return client

    # TODO: Add an async decorator to aiohttp-xmlrpc to replace this function
    async def rpc(self, method_name: str, kwargs: Optional[Dict] = None) -> Any:
        if kwargs is None:
            kwargs = {}

        try:
            client = await self._gen_xmlrpc_client()
            method = getattr(client, method_name)
            return await method(**kwargs)
        except asyncio.TimeoutError as te:
            logger.error(f"Call to {method_name} @ {self.xmlrpc_url} timed out: {te}")
        finally:
            if client:
                await client.close()

    async def all_packages(self) -> Optional[Dict[str, int]]:
        return await self.rpc("list_packages_with_serial")

    async def changed_packages(self, last_serial: int) -> Optional[Dict[str, int]]:
        changelog = await self.rpc(
            "changelog_since_serial", {"last_serial": last_serial}
        )
        if changelog is None:
            changelog = []

        packages: Dict[str, int] = {}
        for package, _version, _time, _action, serial in changelog:
            if serial > packages.get(package, 0):
                packages[package] = serial
        return packages
