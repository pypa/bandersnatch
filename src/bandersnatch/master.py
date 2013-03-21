import xmlrpclib


class Master(object):

    def __init__(self, url):
        self.url = url

    def rpc(self):
        # This is a function as a wrapper to make it thread-safe.
        return xmlrpclib.ServerProxy(self.xmlrpc_url)

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
