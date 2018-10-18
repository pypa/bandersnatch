import logging

import requests
import xmlrpc2

from .utils import USER_AGENT

logger = logging.getLogger(__name__)


class CustomTransport(xmlrpc2.client.HTTPSTransport):
    """This transport adds a custom user agent string and timeout handling."""

    def __init__(self, timeout=10.0):
        xmlrpc2.client.HTTPSTransport.__init__(self)
        self.timeout = timeout
        self.session.headers.update(
            {"User-Agent": USER_AGENT, "Content-Type": "text/xml"}
        )
        self.session.proxies = requests.compat.getproxies()

    def request(self, uri, body):
        resp = self.session.post(uri, body, timeout=self.timeout)
        resp.raise_for_status()
        return resp.content


class StalePage(Exception):
    """We got a page back from PyPI that doesn't meet our expected serial."""


class Master:
    def __init__(self, url, timeout=10.0):
        self.url = url
        if self.url.startswith("http://"):
            logger.error(f"Master URL {url} is not https scheme")
            raise ValueError(f"Master URL {url} is not https scheme")
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

    def rpc(self):
        transports = [CustomTransport(timeout=self.timeout)]
        return xmlrpc2.client.Client(uri=self.xmlrpc_url, transports=transports)

    @property
    def xmlrpc_url(self):
        return f"{self.url}/pypi"

    # Both list package data retrieval methods return a dictionary with package
    # names and the newest serial that they have received changes.
    def all_packages(self):
        return self.rpc().list_packages_with_serial()

    def changed_packages(self, last_serial):
        changelog = self.rpc().changelog_since_serial(last_serial)
        packages = {}
        for package, _version, _time, _action, serial in changelog:
            if serial > packages.get(package, 0):
                packages[package] = serial
        return packages
