from .master import Master
from .package import Package
import cPickle
import datetime
import logging
import optparse
import os
import pkg_resources
import shutil
import socket
import sys

# library config
pypi = 'testpypi.python.org'
BASE = 'http://'+pypi
SIMPLE = BASE + '/simple/'
version = pkg_resources.require("pep381client")[0].version
UA = 'pep381client/'+version

logger = logging.getLogger(__name__)


class Mirror:

    homedir = None
    last_finished = None # when did the last run complete
    last_started = None  # when did the current run start
    errors = None

    def __init__(self, homedir, master):
        self.homedir = homedir
        self.master = master
        self.packages_to_sync = set()
        self._bootstrap()

    @property
    def webdir(self):
        return os.path.join(self.homedir, 'web')

    def synchronize(self):
        self.determine_working_snapshot_time()

        logging.info('Last successful sync: {}'.format(self.last_finished))
        logging.info('Current sync reference: {}'.format(self.last_started))

        self.determine_packages_to_sync()

        logging.info('{} packages to sync.'.format(len(self.packages_to_sync)))

        self.sync_packages()
        self.sync_index_page()
        self.wrapup_successful_sync()

    def determine_working_snapshot_time(self):
        if self.last_started:
            logging.info('Resuming sync started on {}.'.self.last_started)
            return
        if self.last_finished:
            # We continue syncing using a changelog with 10 seconds overlap for
            # good measure in case PyPI had some transactions in between.
            # Not sure this is really needed. XXX
            self.last_started = self.last_finished - datetime.timedelta(seconds=10)
        self.last_started = datetime.datetime.utcnow()

    def determine_packages_to_sync(self):
        if not self.last_finished:
            logging.info('Syncing all packages.')
            todo = self.master.list_packages()
        else:
            logging.info('Syncing based on changelog.')
            request_since = int(self.last_started.strftime('%s'))
            todo = self.master.changed_packages(request_since)
        self.packages_to_sync.update(todo)

    def sync_packages(self):
        for name in self.packages_to_sync:
            package = Package(name, self)
            try:
                package.sync()
            except Exception:
                logger.exception('Error syncing package {}'.format(name))
                self.errors = True

    def sync_index_page(self):
        # XXX
        return
        r = requests.get(SIMPLE)
        project_simple_dir = os.path.join(self.webdir, 'simple', project)
        html = r.content
        with open(os.path.join(project_simple_dir, 'index.html'), "wb") as f:
            f.write(html)
        # XXX add serversignature downloading here

    def wrapup_successful_sync(self):
        if self.errors:
            return
        self.last_finished = self.last_started
        self.last_started = None
        with open(os.path.join(self.homedir, "web", "last-modified"), "wb") as f:
            f.write(self.last_finished.strftime("%Y%m%dT%H:%M:%S\n"))
        self._save()

    def _bootstrap(self):
        if not os.path.exists(self.homedir):
            logging.info('Setting up empty mirror tree.')
            for d in ('',
                      'web/simple',
                      'web/packages',
                      'web/serversig',
                      'web/local-stats/days'):
                os.makedirs(os.path.join(self.homedir, d))

        # XXX fctl lock something
        self._load()

    @property
    def statusfile(self):
        return os.path.join(self.homedir, "status")

    def _load(self):
        if not os.path.exists(self.statusfile):
            logging.info('Status file missing. Starting over.')
            return
        with open(self.statusfile, "rb") as f:
            self.last_finished, self.last_started = cPickle.load(f)

    def _save(self):
        with open(self.statusfile, "wb") as f:
            cPickle.dump(
                (self.last_finished, self.last_started),
                f, cPickle.HIGHEST_PROTOCOL)

def main():
    opts = optparse.OptionParser(usage="Usage: pep381run <targetdir>")
    options, args = opts.parse_args()

    if len(args) != 1:
        opts.error("You have to specify a target directory")

    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(message)s')

    targetdir = args[0]
    master = Master('http://testpypi.python.org')
    state = Mirror(targetdir, master)
    state.synchronize()
