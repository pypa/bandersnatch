from __future__ import with_statement
import cPickle, os, xmlrpclib, time, urllib2
from xml.etree import ElementTree

# Helpers

_proxy = None
def xmlrpc():
    global _proxy
    if _proxy is None:
        _proxy = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
    return _proxy

def now():
    return int(time.time())

# Main class

class Synchronization:
    "Picklable status of a mirror"
    base = "http://pypi.python.org"

    @property
    def simple(self):
        return self.base+"/simple"
    @property packages(self):
        return self.base+"/packages"

    def __init__(self):
        self.homedir = None

        # time stamps: seconds since 1970
        self.last_completed = 0 # when did the last run complete
        self.last_started = 0   # when did the current run start

        self.complete_projects = set()
        self.projects_to_do = set()
        self.files_per_project = {}

    def store(self):
        with open(self.homedir+"/status", "wb") as f:
            cPickle.dump(self, f, cPickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(homedir):
        return cPickle.load(open(homedir+"/status", "rb"))

    #################### Synchronization logic ##############################

    @staticmethod
    def initialize(targetdir):
        'Create a new empty mirror. This operation should not be interrupted.'
        assert not os.path.exists(targetdir)
        os.makedirs(targetdir)
        for d in ('/web/simple', '/web/packages', '/web/serversig'):
            os.makedirs(targetdir+d)
        status = Synchronization()
        status.homedir = targetdir
        status.last_started = now()
        status.projects_to_do = set(xmlrpc().list_packages())
        status.store()
        return status

    def synchronize(self):
        'Run synchronization. Can be interrupted and restarted at any time.'
        if self.last_started == 0:
            # no synchronization in progress. Fetch changelog
            self.last_started = now()
            changes = xmlrpc.changelog(self.last_completed-1)
            if not changes:
                return
            for change in changes:
                self.projects_to_do.add(change[0])
            self.save()
        for project in self.projects_to_do:
            data = self.copy_simple_page(project)
            files = self.get_package_files(data)
            for file in files:
                self.maybe_copy_file(file)
            self.complete_projects.add(project)
            self.projects_to_do.remove(project)
            self.save()

    def copy_simple_package(self, project):
        with urllib2.urlopen(self.simple + project) as f:
            data = f.read()
        with open(self.homedir + "/web/simple/" + project, "wb"):
            f.write(data)
        return data

    def get_package_files(self, data):
        x = ElementTree.fromstring(data)
        res = []
        for a in x.findall(".//a"):
            url = a.attrib['href']
            if not url.startswith(self.packages):
                continue
            url = url.split('#')[0]
            url = url[len(self.packages):]
            res.append(url)

    def maybe_copy_file(self, path):
        # TODO
        # use If-None-Match
        # download file, cache etag
