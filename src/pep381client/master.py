from threading import local
import xmlrpclib


class Master(object):

    def __init__(self, url='https://pypi.python.org'):
        self.url = url

    @property
    def rpc(self):
        return xmlrpclib.ServerProxy(self.xmlrpc_url)

    @property
    def xmlrpc_url(self):
        return '{}/pypi/'.format(self.url)

    def list_packages(self):
        return self.rpc.list_packages()

    def changed_packages(self, since):
        return (change[0] for change in self.rpc.changelog(since))

    def package_releases(self, package):
        return self.rpc.package_releases(package, True)

    def release_urls(self, package, version):
        return self.rpc.release_urls(package, version)
