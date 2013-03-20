from .master import Master
from .package import Package
import datetime
import logging
import multiprocessing.pool
import optparse
import fcntl
import os
import pkg_resources
import requests
import shutil
import socket
import sys


logger = logging.getLogger(__name__)


class Mirror:

    homedir = None

    synced_serial = 0       # The last serial we have consistently synced to.
    target_serial = None    # What is the serial we are trying to reach?
    errors = None

    # We are required to leave a 'last changed' timestamp. I'd rather err on
    # the side of giving a timestamp that is too old so we keep track of it
    # when starting to sync.
    now = None

    def __init__(self, homedir, master):
        self.homedir = homedir
        self.master = master
        self.packages_to_sync = set()
        self._bootstrap()

    @property
    def webdir(self):
        return os.path.join(self.homedir, 'web')

    def synchronize(self):
        self.now = datetime.datetime.utcnow()


        self.determine_packages_to_sync()


        self.sync_packages()
        self.sync_index_page()
        self.wrapup_successful_sync()

    def determine_packages_to_sync(self):
        # In case we don't find any changes we will stay on the currently
        # synced serial.
        self.target_serial = self.synced_serial
        logger.info('Current mirror serial: {}'.format(self.synced_serial))
        if not self.synced_serial:
            logger.info('Syncing all packages.')
            # First get the current serial, then start to sync. This makes us
            # more defensive in case something changes on the server between
            # those two calls.
            self.target_serial = self.master.get_current_serial()
            todo = self.master.list_packages()
        else:
            logger.info('Syncing based on changelog.')
            todo, self.target_serial = self.master.changed_packages(self.synced_serial)
        logger.info('Current master serial: {}'.format(self.target_serial))
        self.packages_to_sync.update(todo)

    def sync_packages(self):
        logger.info('{} packages to sync.'.format(len(self.packages_to_sync)))
        packages = [Package(name, self) for name in self.packages_to_sync]
        # XXX make configurable
        pool = multiprocessing.pool.ThreadPool(10)
        pool.map(lambda package: package.sync(), packages)

    def sync_index_page(self):
        if not self.packages_to_sync:
            return
        logger.info('Syncing global index page.')
        r = requests.get(self.master.url+'/simple')
        r.raise_for_status()
        index_page = os.path.join(self.webdir, 'simple', 'index.html')
        with open(index_page, "wb") as f:
            f.write(r.content)

    def wrapup_successful_sync(self):
        if self.errors:
            return
        self.synced_serial = self.target_serial
        logger.info('New mirror serial: {}'.format(self.synced_serial))
        with open(os.path.join(self.homedir, "web", "last-modified"), "wb") as f:
            f.write(self.now.strftime("%Y%m%dT%H:%M:%S\n"))
        self._save()

    def _bootstrap(self):
        if not os.path.exists(self.homedir):
            logger.info('Setting up empty mirror tree.')
            for d in ('',
                      'web/simple',
                      'web/packages',
                      'web/serversig',
                      'web/local-stats/days'):
                os.makedirs(os.path.join(self.homedir, d))

        try:
            self.lockfile = open(os.path.join(self.homedir, '.lock'), 'wb')
            fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise RuntimeError('Could not acquire lock on {}. '
                'Another instance seems to be running.'.format(
                    self.lockfile.name))

        self._load()

    @property
    def statusfile(self):
        return os.path.join(self.homedir, "status")

    def _load(self):
        if not os.path.exists(self.statusfile):
            logger.info('Status file missing. Starting over.')
            return
        with open(self.statusfile, "rb") as f:
            self.synced_serial = int(f.read().strip())

    def _save(self):
        with open(self.statusfile, "wb") as f:
            f.write(str(self.synced_serial))


def main():
    opts = optparse.OptionParser(usage="Usage: bsn-mirror <targetdir>")
    options, args = opts.parse_args()

    if len(args) != 1:
        opts.error("You have to specify a target directory")

    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    logger = logging.getLogger('bandersnatch')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    targetdir = args[0]
    # XXX make configurable
    master = Master('https://testpypi.python.org')
    state = Mirror(targetdir, master)
    state.synchronize()
