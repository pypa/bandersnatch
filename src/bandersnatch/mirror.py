from .package import Package
from .utils import rewrite, USER_AGENT
import Queue
import datetime
import fcntl
import logging
import os
import sys
import threading

from packaging.utils import canonicalize_name


logger = logging.getLogger(__name__)


class Worker(threading.Thread):

    def __init__(self, queue):
        super(Worker, self).__init__()
        self.queue = queue

    def run(self):
        while True:
            try:
                package = self.queue.get_nowait()
            except Queue.Empty:
                break
            package.sync()


class Mirror(object):

    homedir = None

    synced_serial = 0       # The last serial we have consistently synced to.
    target_serial = None    # What is the serial we are trying to reach?
    errors = None
    packages_to_sync = None
    need_index_sync = True

    # Stop soon after meeting an error. Continue without updating the
    # mirror's serial if false.
    stop_on_error = False

    delete_packages = True

    # We are required to leave a 'last changed' timestamp. I'd rather err
    # on the side of giving a timestamp that is too old so we keep track
    # of it when starting to sync.
    now = None

    def __init__(self, homedir, master, stop_on_error=False, workers=3,
                 delete_packages=True, hash_index=False):
        logger.info('{0}'.format(USER_AGENT))
        self.homedir = homedir
        self.master = master
        self.stop_on_error = stop_on_error
        self.delete_packages = delete_packages
        self.hash_index = hash_index
        self.workers = workers
        if self.workers > 10:
            raise ValueError(
                'Downloading with more than 10 workers is not allowed.')
        self._bootstrap()
        self._finish_lock = threading.RLock()

    @property
    def webdir(self):
        return os.path.join(self.homedir, 'web')

    @property
    def todolist(self):
        return os.path.join(self.homedir, 'todo')

    def synchronize(self):
        logger.info('Syncing with {0}.'.format(self.master.url))
        self.now = datetime.datetime.utcnow()

        self.determine_packages_to_sync()
        self.sync_packages()
        self.sync_index_page()
        self.wrapup_successful_sync()

    def _cleanup(self):
        """Does a couple of cleanup tasks to ensure consistent data for later
        processing."""
        if os.path.exists(self.todolist):
            try:
                saved_todo = iter(open(self.todolist))
                int(saved_todo.next().strip())
            except (StopIteration, ValueError):
                # The todo list was inconsistent. This may happen if we get
                # killed e.g. by the timeout wrapper. Just remove it - we'll
                # just have to do whatever happened since the last successful
                # sync.
                logger.info(u'Removing inconsistent todo list.')
                os.unlink(self.todolist)

    def determine_packages_to_sync(self):
        # In case we don't find any changes we will stay on the currently
        # synced serial.
        self.target_serial = self.synced_serial
        self.packages_to_sync = {}
        logger.info(u'Current mirror serial: {0}'.format(self.synced_serial))

        if os.path.exists(self.todolist):
            # We started a sync previously and left a todo list as well as the
            # targetted serial. We'll try to keep going through the todo list
            # and then mark the targetted serial as done.
            logger.info(u'Resuming interrupted sync from local todo list.')
            saved_todo = iter(open(self.todolist))
            self.target_serial = int(saved_todo.next().strip())
            for line in saved_todo:
                package, serial = line.strip().split()
                self.packages_to_sync[package.decode('utf-8')] = int(serial)
        elif not self.synced_serial:
            logger.info(u'Syncing all packages.')
            # First get the current serial, then start to sync. This makes us
            # more defensive in case something changes on the server between
            # those two calls.
            self.packages_to_sync.update(self.master.all_packages())
            self.target_serial = max(
                [self.synced_serial] + list(self.packages_to_sync.values()))
        else:
            logger.info(u'Syncing based on changelog.')
            self.packages_to_sync.update(
                self.master.changed_packages(self.synced_serial))
            self.target_serial = max(
                [self.synced_serial] + list(self.packages_to_sync.values()))
            # We can avoid downloading the main index page if we don't have
            # anything todo at all during a changelog-based sync.
            self.need_index_sync = bool(self.packages_to_sync)

        logger.info(u'Trying to reach serial: {0}'.format(self.target_serial))
        pkg_count = len(self.packages_to_sync)
        logger.info(u'{0} packages to sync.'.format(pkg_count))

    def sync_packages(self):
        self.queue = Queue.Queue()
        # Sorting the packages alphabetically makes it more predicatable:
        # easier to debug and easier to follow in the logs.
        for name in sorted(self.packages_to_sync):
            serial = self.packages_to_sync[name]
            self.queue.put(Package(name, serial, self))

        # This is more complicated than obviously needed to keep Ctrl-C
        # working.  Otherwise I'd use multiprocessing.pool.
        workers = [Worker(self.queue) for i in range(self.workers)]
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

    def retry_later(self, package):
        self.queue.put(package)

    def record_finished_package(self, name):
        with self._finish_lock:
            del self.packages_to_sync[name]
            with open(self.todolist, 'wb') as f:
                todo = list(self.packages_to_sync.items())
                todo = ['{0} {1}'.format(name_.encode('utf-8'), str(serial))
                        for name_, serial in todo]
                f.write('{0}\n'.format(self.target_serial))
                f.write('\n'.join(todo))

    def get_simple_dirs(self, simple_dir):
        """Return a list of simple index directories that should be searched
        for package indexes when compiling the main index page."""
        if self.hash_index:
            # We are using index page directory hashing, so the directory
            # format is /simple/f/foo/.  We want to return a list of dirs
            # like "simple/f".
            subdirs = [os.path.join(simple_dir, x)
                       for x in os.listdir(simple_dir)]
            subdirs = [x for x in subdirs if os.path.isdir(x)]
        else:
            # This is the traditional layout of /simple/foo/.  We should
            # return a single directory, "simple".
            subdirs = [simple_dir]
        return subdirs

    def find_package_indexes_in_dir(self, simple_dir):
        """Given a directory that contains simple packages indexes, return
        a sorted list of normalized package names.  This presumes every
        directory within is a simple package index directory."""
        packages = sorted(set(
            # Filter out all of the "non" normalized names here
            canonicalize_name(x)
            for x in os.listdir(simple_dir)))
        # Package indexes must be in directories, so ignore anything else.
        packages = [x for x in packages
                    if os.path.isdir(os.path.join(simple_dir, x))]
        return packages

    def sync_index_page(self):
        if not self.need_index_sync:
            return
        logger.info(u'Generating global index page.')
        simple_dir = os.path.join(self.webdir, 'simple')
        with rewrite(os.path.join(simple_dir, 'index.html')) as f:
            f.write('<html><head><title>Simple Index</title></head><body>\n')
            # This will either be the simple dir, or if we are using index
            # directory hashing, a list of subdirs to process.
            for subdir in self.get_simple_dirs(simple_dir):
                for pkg in self.find_package_indexes_in_dir(subdir):
                    # We're really trusty that this is all encoded in UTF-8. :/
                    f.write('<a href="{0}/">{1}</a><br/>\n'.format(pkg, pkg))
            f.write('</body></html>')

    def wrapup_successful_sync(self):
        if self.errors:
            return
        self.synced_serial = self.target_serial
        if os.path.exists(self.todolist):
            os.unlink(self.todolist)
        logger.info(u'New mirror serial: {0}'.format(self.synced_serial))
        last_modified = os.path.join(self.homedir, "web", "last-modified")
        with rewrite(last_modified) as f:
            f.write(self.now.strftime("%Y%m%dT%H:%M:%S\n"))
        self._save()

    def _bootstrap(self):
        for path in ('',
                     'web/simple',
                     'web/packages',
                     'web/local-stats/days'):
            path = os.path.join(self.homedir, path)
            if not os.path.exists(path):
                logger.info(u'Setting up mirror directory: {0}'.format(path))
                os.makedirs(path)

        self.lockfile = open(os.path.join(self.homedir, '.lock'), 'wb')
        try:
            fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise RuntimeError(
                'Could not acquire lock on {0}. '
                'Another instance seems to be running.'.format(
                    self.lockfile.name))

        self._cleanup()
        self._load()

    @property
    def statusfile(self):
        return os.path.join(self.homedir, "status")

    @property
    def generationfile(self):
        return os.path.join(self.homedir, "generation")

    def _reset_mirror_status(self):
        for path in [self.statusfile, self.todolist]:
            if os.path.exists(path):
                os.unlink(path)

    def _load(self):
        # Simple generation mechanism to support transparent software
        # updates.
        CURRENT_GENERATION = 5  # noqa
        try:
            generation = int(open(self.generationfile, 'r').read().strip())
        except IOError:
            logger.info(u'Generation file missing. '
                        u'Reinitialising status files.')
            # This is basically the 'install' generation: anything previous to
            # release 1.0.2.
            self._reset_mirror_status()
            generation = CURRENT_GENERATION
        if generation in [2, 3, 4]:
            # In generation 2 -> 3 we changed the way we generate simple
            # page package directory names. Simply run a full update.
            # Generation 3->4 is intended to counter a data bug on PyPI.
            # https://bitbucket.org/pypa/bandersnatch/issue/56/setuptools-went-missing
            # Generation 4->5 is intended to ensure that we have PEP 503
            # compatible /simple/ URLs generated for everything.
            self._reset_mirror_status()
            generation = 5
        assert generation == CURRENT_GENERATION
        open(self.generationfile, 'w').write(str(CURRENT_GENERATION))
        # Now, actually proceed towards using the status files.
        if not os.path.exists(self.statusfile):
            logger.info(u'Status file missing. Starting over.')
            return
        with open(self.statusfile, "rb") as f:
            self.synced_serial = int(f.read().strip())

    def _save(self):
        with open(self.statusfile, "wb") as f:
            f.write(str(self.synced_serial))
