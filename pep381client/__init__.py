from __future__ import with_statement
import cPickle, os, xmlrpclib, time, urllib2, httplib
from xml.etree import ElementTree

# library config
pypi = 'pypi.python.org'
BASE = 'http://'+pypi
SIMPLE = BASE + '/simple/'
PACKAGES = BASE + '/packages'
UA = 'pep381client/1.0'

# Helpers

_proxy = None
def xmlrpc():
    global _proxy
    if _proxy is None:
        _proxy = xmlrpclib.ServerProxy(BASE+'/pypi')
        _proxy.useragent = UA
    return _proxy

_conn = None
def http():
    global _conn
    if _conn is None:
        _conn = httplib.HTTPConnection(pypi)
        _conn.connect()
    # check that connection is still open
    try:
        _conn.sock.getpeername()
    except socket.error:
        _conn = httplib.HTTPConnection(pypi)
        _conn.connect()
    return _conn

def now():
    return int(time.time())

# Main class

class Synchronization:
    "Picklable status of a mirror"

    def __init__(self):
        self.homedir = None

        # time stamps: seconds since 1970
        self.last_completed = 0 # when did the last run complete
        self.last_started = 0   # when did the current run start

        self.complete_projects = set()
        self.projects_to_do = set()
        self.files_per_project = {}
        self.etags = {} # path:etag

        self.skip_file_contents = False

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
            self.store()
        # sort projects to allow for repeatable runs
        for project in sorted(self.projects_to_do):
            print "Synchronizing", project
            data = self.copy_simple_page(project)
            files = set(self.get_package_files(data))
            for file in files:
                print "Copying", file
                self.maybe_copy_file(file)
            if project in self.files_per_project:
                for file in self.files_per_project[project]-files:
                    self.remove_file(file)
            self.files_per_project[project] = files
            self.complete_projects.add(project)
            self.projects_to_do.remove(project)
            self.store()

    def copy_simple_page(self, project):
        h = http()
        h.putrequest('GET', '/simple/'+urllib2.quote(project))
        h.putheader('User-Agent', UA)
        h.endheaders()
        r = h.getresponse()
        if r.status == 404:
            return None
        if r.status != 200:
            raise ValueError, "Status %d on %s" % (r.status, project)
        data = r.read()
        with open(self.homedir + "/web/simple/" + project, "wb") as f:
            f.write(data)
        return data

    def get_package_files(self, data):
        x = ElementTree.fromstring(data)
        res = []
        for a in x.findall(".//a"):
            url = a.attrib['href']
            if not url.startswith(PACKAGES):
                continue
            url = url.split('#')[0]
            url = url[len(BASE):]
            res.append(url)
        return res

    def maybe_copy_file(self, path):
        h = http()
        if self.skip_file_contents:
            h.putrequest("HEAD", path)
        else:
            h.putrequest("GET", path)
        h.putheader('User-Agent', UA)
        if path in self.etags:
            h.putheader("If-none-match", self.etags[path])
        h.endheaders()
        r = h.getresponse()
        if r.status == 304:
            # not modified, discard data
            r.read()
            return
        lpath = self.homedir + "/web" + path
        if r.status == 200:
            if path in self.etags:
                del self.etags[path]
            data = r.read()
            dirname = os.path.dirname(lpath)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(lpath, "wb") as f:
                f.write(data)
            # XXX may set last-modified timestamp on file
            if "etag" in r.msg:
                self.etags[path] = r.msg["etag"]
            self.store()
            return
        if r.status == 404:
            self.remove_file(path)

    def remove_file(self, path):
        if path in self.etags:
            del self.etags[path]
        lpath = self.homedir + "/web" + path
        if os.path.exists(lpath):
            os.unlink(lpath)
