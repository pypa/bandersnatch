from .utils import USER_AGENT
import httplib
import logging
import requests
import xmlrpclib


logger = logging.getLogger(__name__)


class CustomTransport(xmlrpclib.Transport):
    """This transport adds a custom user agent string and timeout handling."""

    def __init__(self, ssl=False, timeout=10.0):
        xmlrpclib.Transport.__init__(self)
        self.timeout = timeout
        self.ssl = ssl

    def make_connection(self, host):
        # Partially copied from xmlrpclib.py because its inheritance model is
        # inconvenient.

        # return an existing connection if possible.  This allows
        # HTTP/1.1 keep-alive.
        if self._connection and host == self._connection[0]:
            return self._connection[1]

        # create an HTTP connection object from a host descriptor
        chost, self._extra_headers, x509 = self.get_host_info(host)
        self._extra_headers = [('User-Agent', USER_AGENT)]

        # store the host argument along with the connection object
        if not self.ssl:
            self._connection = host, httplib.HTTPConnection(
                chost, timeout=self.timeout)
        else:
            try:
                httplib.HTTPSConnection
            except AttributeError:
                raise NotImplementedError(
                    "your version of httplib doesn't support HTTPS")
            self._connection = host, httplib.HTTPSConnection(
                chost, None, **(x509 or {}))

        return self._connection[1]


class StalePage(Exception):
    """We got a page back from PyPI that doesn't meet our expected serial."""


class Master(object):

    def __init__(self, url, timeout=10.0):
        self.url = url
        self.timeout = timeout

    def get(self, path, required_serial, **kw):
        logger.debug('Getting {} (serial {})'.format(path, required_serial))
        if not path.startswith(self.url):
            path = self.url + path
        headers = {'User-Agent': USER_AGENT}
        r = requests.get(path, timeout=self.timeout,
                         headers=headers, **kw)
        r.raise_for_status()
        # The PYPI-LAST-SERIAL header allows us to identify cached entries,
        # e.g. via the public CDN or private, transparent mirrors and avoid us
        # injecting stale entries into the mirror without noticing.
        if required_serial is not None:
            # I am not making required_serial an optional argument because I
            # want you to think really hard before passing in None. This is a
            # really important check to achieve consistency and you should only
            # leave it out if you know what you're doing.
            got_serial = int(r.headers['X-PYPI-LAST-SERIAL'])
            if got_serial < required_serial:
                logger.debug(
                    "Expected PyPI serial {} for request {} but got {}".
                    format(required_serial, path, got_serial))
                raise StalePage(
                    "Expected PyPI serial {} for request {} but got {}".
                    format(required_serial, path, got_serial))
        return r

    def rpc(self):
        # This is a function as a wrapper to make it thread-safe.
        use_ssl = self.xmlrpc_url.startswith('https:')
        t = CustomTransport(ssl=use_ssl, timeout=self.timeout)
        return xmlrpclib.ServerProxy(self.xmlrpc_url, transport=t)

    @property
    def xmlrpc_url(self):
        return '{}/pypi/'.format(self.url)

    # Both list package data retrieval methods return a dictionary with package
    # names and the newest serial that they have received changes.
    def all_packages(self):
        return self.rpc().list_packages_with_serial()

    def changed_packages(self, last_serial):
        changelog = self.rpc().changelog_since_serial(last_serial)
        packages = {}
        for package, version, time, action, serial in changelog:
            if serial > packages.get(package, 0):
                packages[package] = serial
        return packages

    def package_releases(self, package):
        return self.rpc().package_releases(package, True)

    def release_urls(self, package, version):
        return self.rpc().release_urls(package, version)
