from .master import Master
from .package import Package
import ConfigParser
import Queue
import argparse
import datetime
import fcntl
import logging
import os
import requests
import shutil
import sys
import threading


logger = logging.getLogger(__name__)


class Worker(threading.Thread):

    def __init__(self, queue):
        super(Worker, self).__init__()
        self.queue = queue

    def run(self):
        while not self.queue.empty():
            package = self.queue.get()
            package.sync()


class Mirror(object):

    homedir = None

    synced_serial = 0       # The last serial we have consistently synced to.
    target_serial = None    # What is the serial we are trying to reach?
    errors = None
    # Stop soon after meeting an error. Continue without updating the
    # mirror's serial if false.
    stop_on_error = False

    # We are required to leave a 'last changed' timestamp. I'd rather err
    # on the side of giving a timestamp that is too old so we keep track
    # of it when starting to sync.
    now = None


    def __init__(self, homedir, master, stop_on_error=False, workers=3):
        self.homedir = homedir
        self.master = master
        self.stop_on_error = stop_on_error
        self.workers = workers
        if self.workers > 50:
            raise ValueError('Downloading with more than 50 workers is not allowed.')

        self.packages_to_sync = set()
        self._bootstrap()
        self._finish_lock = threading.RLock()
        self._need_index_sync = False

    @property
    def webdir(self):
        return os.path.join(self.homedir, 'web')

    @property
    def todolist(self):
        return os.path.join(self.homedir, 'todo')

    def synchronize(self):
        logger.info('Syncing with {}.'.format(self.master.url))
        self.now = datetime.datetime.utcnow()

        self.determine_packages_to_sync()
        self.sync_packages()
        self.sync_index_page()
        self.wrapup_successful_sync()

    def determine_packages_to_sync(self):
        # In case we don't find any changes we will stay on the currently
        # synced serial.
        self.target_serial = self.synced_serial
        logger.info(u'Current mirror serial: {}'.format(self.synced_serial))

        if os.path.exists(self.todolist):
            todo = open(self.todolist).readlines()
            self.target_serial = todo.pop(0).strip()
            todo = [x.decode('utf-8').strip() for x in todo]
            logger.info(u'Resuming aborted sync.')
        elif not self.synced_serial:
            logger.info(u'Syncing all packages.')
            # First get the current serial, then start to sync. This makes us
            # more defensive in case something changes on the server between
            # those two calls.
            self.target_serial = self.master.get_current_serial()
            todo = self.master.list_packages()
        else:
            logger.info(u'Syncing based on changelog.')
            todo, self.target_serial = self.master.changed_packages(
                self.synced_serial)

        logger.info(u'Current master serial: {}'.format(self.target_serial))
        self.packages_to_sync.update(todo)
        self._need_index_sync = bool(self.packages_to_sync)

    def sync_packages(self):
        queue = Queue.Queue()
        logger.info(u'{} packages to sync.'.format(len(self.packages_to_sync)))
        # Sorting the packages alphabetically makes it more predicatable:
        # easier to debug and easier to follow in the logs.
        for name in sorted(self.packages_to_sync):
            queue.put(Package(name, self))

        # This is a rather complicated setup just to keep Ctrl-C working.
        # Otherwise I'd use multiprocessing.pool
        workers = [Worker(queue) for i in range(20)]
        for worker in workers:
            worker.daemon = True
            worker.start()
        while workers:
            for worker in workers:
                worker.join(0.5)
                if self.stop_on_error and self.errors:
                    logger.error(u'Exiting early after error.')
                    sys.exit(1)
                if not worker.isAlive():
                    workers.remove(worker)

    def record_finished_package(self, name):
        with self._finish_lock:
            self.packages_to_sync.remove(name)
            with open(self.todolist, 'wb') as f:
                todo = [str(self.target_serial)]
                todo.extend(self.packages_to_sync)
                todo = [x.encode('utf-8') for x in todo]
                f.write('\n'.join(todo))

    def sync_index_page(self):
        if not self._need_index_sync:
            return
        logger.info(u'Syncing global index page.')
        r = requests.get(self.master.url+'/simple')
        r.raise_for_status()
        index_page = os.path.join(self.webdir, 'simple', 'index.html')
        with open(index_page, "wb") as f:
            f.write(r.content)

    def wrapup_successful_sync(self):
        if self.errors:
            return
        self.synced_serial = self.target_serial
        if os.path.exists(self.todolist):
            os.unlink(self.todolist)
        logger.info(u'New mirror serial: {}'.format(self.synced_serial))
        last_modified = os.path.join(self.homedir, "web", "last-modified")
        with open(last_modified, "wb") as f:
            f.write(self.now.strftime("%Y%m%dT%H:%M:%S\n"))
        self._save()

    def _bootstrap(self):
        for path in ('',
                     'web/simple',
                     'web/packages',
                     'web/serversig',
                     'web/local-stats/days'):
            path = os.path.join(self.homedir, path)
            if not os.path.exists(path):
                logger.info(u'Setting up mirror directory: {}'.format(path))
                os.makedirs(path)

        try:
            self.lockfile = open(os.path.join(self.homedir, '.lock'), 'wb')
            fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise RuntimeError(
                'Could not acquire lock on {}. '
                'Another instance seems to be running.'.format(
                    self.lockfile.name))

        self._load()

    @property
    def statusfile(self):
        return os.path.join(self.homedir, "status")

    def _load(self):
        if not os.path.exists(self.statusfile):
            logger.info(u'Status file missing. Starting over.')
            return
        with open(self.statusfile, "rb") as f:
            self.synced_serial = int(f.read().strip())

    def _save(self):
        with open(self.statusfile, "wb") as f:
            f.write(str(self.synced_serial))


def main():
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    logger = logging.getLogger('bandersnatch')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    parser = argparse.ArgumentParser(description='Sync PyPI mirror with master server.')
    parser.add_argument('-c', '--config', default='/etc/bandersnatch.conf',
                        help='use configuration file (default: %(default)s)')
    args = parser.parse_args()

    default_config = os.path.join(os.path.dirname(__file__), 'default.conf')
    if not os.path.exists(args.config):
        logger.warning('Config file \'{}\' missing, creating default config.'
            .format(args.config))
        logger.warning('Please review the config file, then run \'bsn-mirror\' again.')
        try:
            shutil.copy(default_config, args.config)
        except IOError, e:
            logger.error('Could not create config file: {}'.format(str(e)))
        sys.exit(1)

    config = ConfigParser.ConfigParser()
    config.read([default_config, args.config])

    master = Master(config.get('mirror', 'master'))
    mirror = Mirror(
        config.get('mirror', 'directory'), master,
        stop_on_error=config.getboolean('mirror', 'stop-on-error'),
        workers=config.getint('mirror', 'workers'))
    mirror.synchronize()
