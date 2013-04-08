from .utils import USER_AGENT
import httplib
import requests
import xmlrpclib


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


class Master(object):

    def __init__(self, url, timeout=10.0):
        self.url = url
        self.timeout = timeout

    def get(self, path, **kw):
        if not path.startswith(self.url):
            path = self.url + path
        headers = {'User-Agent': USER_AGENT}
        if 'headers' in kw:
            headers.update(kw.pop('headers'))
        r = requests.get(path, timeout=self.timeout,
                         headers=headers, **kw)
        r.raise_for_status()
        return r

    def rpc(self):
        # This is a function as a wrapper to make it thread-safe.
        use_ssl = self.xmlrpc_url.startswith('https:')
        t = CustomTransport(ssl=use_ssl, timeout=self.timeout)
        return xmlrpclib.ServerProxy(self.xmlrpc_url, transport=t)

    @property
    def xmlrpc_url(self):
        return '{}/pypi/'.format(self.url)

    def list_packages(self):
        return self.rpc().list_packages()

    def changed_packages(self, serial):
        changelog = self.rpc().changelog_since_serial(serial)
        last_serial = serial
        if changelog:
            last_serial = changelog[-1][-1]
        return (change[0] for change in changelog), last_serial

    def package_releases(self, package):
        return self.rpc().package_releases(package, True)

    def release_urls(self, package, version):
        return self.rpc().release_urls(package, version)

    def get_current_serial(self):
        return self.rpc().changelog_last_serial()
