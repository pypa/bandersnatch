import asyncio
import configparser
import datetime
import logging
import os
import time
from pathlib import Path
from threading import RLock
from typing import Awaitable, Dict, List, Set
from unittest.mock import Mock

from filelock import FileLock, Timeout
from packaging.utils import canonicalize_name

from .filter import filter_project_plugins, filter_release_plugins
from .master import Master
from .package import Package
from .utils import rewrite, update_safe

LOG_PLUGINS = True
logger = logging.getLogger(__name__)


class Mirror:

    synced_serial = 0  # The last serial we have consistently synced to.
    target_serial = None  # What is the serial we are trying to reach?
    errors = False
    packages_to_sync = None
    need_index_sync = True
    json_save = False  # Wether or not to mirror PyPI JSON metadata to disk

    # Stop soon after meeting an error. Continue without updating the
    # mirror's serial if false.
    stop_on_error = False

    digest_name = "sha256"

    # We are required to leave a 'last changed' timestamp. I'd rather err
    # on the side of giving a timestamp that is too old so we keep track
    # of it when starting to sync.
    now = None

    # Allow configuring a root_uri to make generated index pages absolute.
    # This is generally not necessary, but was added for the official internal
    # PyPI mirror, which requires serving packages from
    # https://files.pythonhosted.org
    root_uri = ""

    diff_file = None
    diff_append_epoch = False
    diff_full_path = None

    def __init__(
        self,
        homedir,
        master,
        stop_on_error=False,
        workers=3,
        hash_index=False,
        json_save=False,
        digest_name=None,
        root_uri=None,
        keep_index_versions=0,
        diff_file=None,
        diff_append_epoch=False,
        diff_full_path=None,
        flock_timeout=1,
        diff_file_list=None,
        *,
        cleanup=False,
    ):
        self.loop = asyncio.get_event_loop()
        self.homedir = Path(homedir)
        self.master = master
        self.stop_on_error = stop_on_error
        self.json_save = json_save
        self.hash_index = hash_index
        self.root_uri = root_uri
        self.diff_file = diff_file
        self.diff_append_epoch = diff_append_epoch
        self.diff_full_path = diff_full_path
        self.keep_index_versions = keep_index_versions
        self.digest_name = digest_name if digest_name else "sha256"
        self.workers = workers
        self.diff_file_list = diff_file_list or []
        if self.workers > 10:
            raise ValueError("Downloading with more than 10 workers is not allowed.")
        self._bootstrap(flock_timeout)
        self._finish_lock = RLock()

        # Cleanup old legacy non PEP 503 Directories created for the Simple API
        self.cleanup = cleanup

        # Lets record and report back the changes we do each run
        # Format: dict['pkg_name'] = [set(removed), Set[added]
        # Class Instance variable so each package can add their changes
        self.altered_packages = {}

    @property
    def webdir(self) -> Path:
        return self.homedir / "web"

    @property
    def todolist(self) -> Path:
        return self.homedir / "todo"

    async def synchronize(self):
        logger.info(f"Syncing with {self.master.url}.")
        self.now = datetime.datetime.utcnow()
        # Lets ensure we get a new dict each run
        # - others importing may not reset this like our main.py
        self.altered_packages = {}

        await self.determine_packages_to_sync()
        await self.sync_packages()
        self.sync_index_page()
        self.wrapup_successful_sync()

        return self.altered_packages

    def _cleanup(self):
        """Does a couple of cleanup tasks to ensure consistent data for later
        processing."""
        if self.todolist.exists():
            try:
                with open(self.todolist, encoding="utf-8") as f:
                    saved_todo = iter(f)
                    int(next(saved_todo).strip())
                    for line in saved_todo:
                        _, serial = line.strip().split()
                        int(serial)
            except (StopIteration, ValueError):
                # The todo list was inconsistent. This may happen if we get
                # killed e.g. by the timeout wrapper. Just remove it - we'll
                # just have to do whatever happened since the last successful
                # sync.
                logger.info("Removing inconsistent todo list.")
                self.todolist.unlink()

    def _filter_packages(self):
        """
        Run the package filtering plugins and remove any packages from the
        packages_to_sync that match any filters.
        - Logging of action will be done within the check_match methods
        """
        global LOG_PLUGINS

        filter_plugins = filter_project_plugins()
        if not filter_plugins:
            if LOG_PLUGINS:
                logger.info("No project filters are enabled. Skipping filtering")
                LOG_PLUGINS = False
            return

        # Make a copy of self.packages_to_sync keys
        # as we may delete packages during iteration
        packages = list(self.packages_to_sync.keys())
        for package_name in packages:
            if not all(
                plugin.filter({"info": {"name": package_name}})
                for plugin in filter_plugins
                if plugin
            ):
                if package_name not in self.packages_to_sync:
                    logger.debug(f"{package_name} not found in packages to sync")
                else:
                    del self.packages_to_sync[package_name]

    async def determine_packages_to_sync(self):
        """
        Update the self.packages_to_sync to contain packages that need to be
        synced.
        """
        # In case we don't find any changes we will stay on the currently
        # synced serial.
        self.target_serial = self.synced_serial
        self.packages_to_sync = {}
        logger.info(f"Current mirror serial: {self.synced_serial}")

        if self.todolist.exists():
            # We started a sync previously and left a todo list as well as the
            # targetted serial. We'll try to keep going through the todo list
            # and then mark the targetted serial as done.
            logger.info("Resuming interrupted sync from local todo list.")
            saved_todo = iter(open(self.todolist, encoding="utf-8"))
            self.target_serial = int(next(saved_todo).strip())
            for line in saved_todo:
                package, serial = line.strip().split()
                self.packages_to_sync[package] = int(serial)
        elif not self.synced_serial:
            logger.info("Syncing all packages.")
            # First get the current serial, then start to sync. This makes us
            # more defensive in case something changes on the server between
            # those two calls.
            all_packages = await self.master.all_packages()
            self.packages_to_sync.update(all_packages)
            self.target_serial = max(
                [self.synced_serial] + list(self.packages_to_sync.values())
            )
        else:
            logger.info("Syncing based on changelog.")
            changed_packages = await self.master.changed_packages(self.synced_serial)
            self.packages_to_sync.update(changed_packages)
            self.target_serial = max(
                [self.synced_serial] + list(self.packages_to_sync.values())
            )
            # We can avoid downloading the main index page if we don't have
            # anything todo at all during a changelog-based sync.
            self.need_index_sync = bool(self.packages_to_sync)

        self._filter_packages()
        logger.info(f"Trying to reach serial: {self.target_serial}")
        pkg_count = len(self.packages_to_sync)
        logger.info(f"{pkg_count} packages to sync.")

    async def package_syncer(self, idx: int) -> None:
        logger.debug(f"Package syncer {idx} started for duty")
        while True:
            try:
                package = self.package_queue.get_nowait()
            except asyncio.QueueEmpty:
                logger.debug(f"Package syncer {idx} emptied queue")
                break

            await package.sync(self.stop_on_error)

    async def sync_packages(self):
        self.package_queue: asyncio.Queue = asyncio.Queue()
        # Sorting the packages alphabetically makes it more predicatable:
        # easier to debug and easier to follow in the logs.
        for name in sorted(self.packages_to_sync):
            serial = self.packages_to_sync[name]
            await self.package_queue.put(
                Package(name, serial, self, cleanup=self.cleanup)
            )

        sync_coros: List[Awaitable] = [
            self.package_syncer(idx) for idx in range(self.workers)
        ]
        try:
            await asyncio.gather(*sync_coros)
        except KeyboardInterrupt:
            # Setting self.errors to True to ensure we don't save Serial
            # and thus save to disk that we've had a successful sync
            self.errors = True
            logger.info(
                "Cancelling, all downloads are forcibly stopped, data may be "
                + "corrupted. Serial will not be saved to disk. "
                + "Next sync will start from previous serial"
            )

    def record_finished_package(self, name):
        with self._finish_lock:
            del self.packages_to_sync[name]
            with update_safe(self.todolist, mode="w+", encoding="utf-8") as f:
                # First line is the target serial we're working on.
                f.write(f"{self.target_serial}\n")
                # Consecutive lines are the packages we still have to sync
                todo = [
                    f"{name_} {serial}"
                    for name_, serial in self.packages_to_sync.items()
                ]
                f.write("\n".join(todo))

    def get_simple_dirs(self, simple_dir: Path) -> List[Path]:
        """Return a list of simple index directories that should be searched
        for package indexes when compiling the main index page."""
        if self.hash_index:
            # We are using index page directory hashing, so the directory
            # format is /simple/f/foo/.  We want to return a list of dirs
            # like "simple/f".
            subdirs = [simple_dir / x for x in simple_dir.iterdir() if x.is_dir()]
        else:
            # This is the traditional layout of /simple/foo/.  We should
            # return a single directory, "simple".
            subdirs = [simple_dir]
        return subdirs

    def find_package_indexes_in_dir(self, simple_dir):
        """Given a directory that contains simple packages indexes, return
        a sorted list of normalized package names.  This presumes every
        directory within is a simple package index directory."""
        packages = sorted(
            {
                # Filter out all of the "non" normalized names here
                canonicalize_name(x)
                for x in os.listdir(simple_dir)
            }
        )
        # Package indexes must be in directories, so ignore anything else.
        packages = [x for x in packages if os.path.isdir(os.path.join(simple_dir, x))]
        return packages

    def sync_index_page(self):
        if not self.need_index_sync:
            return
        logger.info("Generating global index page.")
        simple_dir = self.webdir / "simple"
        with rewrite(str(simple_dir / "index.html")) as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html>\n")
            f.write("  <head>\n")
            f.write("    <title>Simple Index</title>\n")
            f.write("  </head>\n")
            f.write("  <body>\n")
            # This will either be the simple dir, or if we are using index
            # directory hashing, a list of subdirs to process.
            for subdir in self.get_simple_dirs(simple_dir):
                for pkg in self.find_package_indexes_in_dir(subdir):
                    # We're really trusty that this is all encoded in UTF-8. :/
                    f.write(f'    <a href="{pkg}/">{pkg}</a><br/>\n')
            f.write("  </body>\n</html>")
        self.diff_file_list.append(str(simple_dir / "index.html"))

    def wrapup_successful_sync(self):
        if self.errors:
            return
        self.synced_serial = self.target_serial
        if self.todolist.exists():
            self.todolist.unlink()
        logger.info(f"New mirror serial: {self.synced_serial}")
        last_modified = Path(self.homedir) / "web" / "last-modified"
        with rewrite(last_modified) as f:
            f.write(self.now.strftime("%Y%m%dT%H:%M:%S\n"))
        self._save()

    def _bootstrap(self, flock_timeout=1):
        paths = [
            Path(""),
            Path("web/simple"),
            Path("web/packages"),
            Path("web/local-stats/days"),
        ]
        if self.json_save:
            logger.debug("Adding json directories to bootstrap")
            paths.extend([Path("web/json"), Path("web/pypi")])
        for path in paths:
            path = self.homedir / path
            if not path.exists():
                logger.info(f"Setting up mirror directory: {path}")
                path.mkdir(parents=True)

        flock_path = self.homedir / ".lock"
        flock = FileLock(str(flock_path))
        try:
            with flock.acquire(timeout=flock_timeout):
                self._cleanup()
                self._load()
        except Timeout:
            raise RuntimeError(
                f"Could not acquire lock on {flock_path}. "
                + "Another instance could be running?"
            )

    @property
    def statusfile(self) -> Path:
        return Path(self.homedir) / "status"

    @property
    def generationfile(self) -> Path:
        return Path(self.homedir) / "generation"

    def _reset_mirror_status(self) -> None:
        for path in [self.statusfile, self.todolist]:
            if path.exists():
                path.unlink()

    def _load(self):
        # Simple generation mechanism to support transparent software
        # updates.
        CURRENT_GENERATION = 5  # noqa
        try:
            with self.generationfile.open("r", encoding="ascii") as f:
                generation = int(f.read().strip())
        except ValueError:
            logger.info("Generation file inconsistent. Reinitialising status files.")
            self._reset_mirror_status()
            generation = CURRENT_GENERATION
        except OSError:
            logger.info("Generation file missing. Reinitialising status files.")
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
        if generation != CURRENT_GENERATION:
            raise RuntimeError(f"Unknown generation {generation} found")
        with self.generationfile.open("w", encoding="ascii") as f:
            f.write(str(CURRENT_GENERATION))
        # Now, actually proceed towards using the status files.
        if not self.statusfile.exists():
            logger.info(f"Status file {self.statusfile} missing. Starting over.")
            return
        with self.statusfile.open("r", encoding="ascii") as f:
            self.synced_serial = int(f.read().strip())

    def _save(self):
        with self.statusfile.open("w", encoding="ascii") as f:
            f.write(str(self.synced_serial))


# TODO: Breakup complex method
async def mirror(config: configparser.ConfigParser) -> int:  # noqa: C901
    # Load the filter plugins so the loading doesn't happen in the fast path
    filter_project_plugins()
    filter_release_plugins()

    # `json` boolean is a new optional option in 2.1.2 - want to support it
    # not existing in old configs and display an error saying that this will
    # error in the not to distance release
    try:
        json_save = config.getboolean("mirror", "json")
    except configparser.NoOptionError:
        logger.error(
            "Please update your config to include a json "
            + "boolean in the [mirror] section. Setting to False"
        )
        json_save = False

    try:
        root_uri = config.get("mirror", "root_uri")
    except configparser.NoOptionError:
        root_uri = ""

    try:
        diff_file = config.get("mirror", "diff-file")
    except configparser.NoOptionError:
        diff_file = ""

    try:
        diff_append_epoch = config.getboolean("mirror", "diff-append-epoch")
    except configparser.NoOptionError:
        diff_append_epoch = False

    if diff_file:
        os.makedirs(os.path.dirname(diff_file), exist_ok=True)
        if diff_append_epoch:
            diff_full_path = f"{diff_file}-{int(time.time())}"
        else:
            diff_full_path = diff_file
    else:
        diff_full_path = ""

    if diff_full_path:
        if os.path.isfile(diff_full_path):
            os.unlink(diff_full_path)

    try:
        digest_name = config.get("mirror", "digest_name")
    except configparser.NoOptionError:
        digest_name = "sha256"
    if digest_name not in ("md5", "sha256"):
        raise ValueError(
            f"Supplied digest_name {digest_name} is not supported! Please "
            + "update digest_name to one of ('sha256', 'md5') in the [mirror] "
            + "section."
        )

    try:
        cleanup = config.getboolean("mirror", "cleanup")
    except configparser.NoOptionError:
        logger.debug(
            "bandersnatch is not cleaning up non PEP 503 normalized Simple "
            + "API directories"
        )
        cleanup = False

    # Always reference those classes here with the fully qualified name to
    # allow them being patched by mock libraries!
    async with Master(
        config.get("mirror", "master"), config.getfloat("mirror", "timeout")
    ) as master:
        mirror = Mirror(
            config.get("mirror", "directory"),
            master,
            stop_on_error=config.getboolean("mirror", "stop-on-error"),
            workers=config.getint("mirror", "workers"),
            hash_index=config.getboolean("mirror", "hash-index"),
            json_save=json_save,
            root_uri=root_uri,
            digest_name=digest_name,
            keep_index_versions=config.getint(
                "mirror", "keep_index_versions", fallback=0
            ),
            diff_file=diff_file,
            diff_append_epoch=diff_append_epoch,
            diff_full_path=diff_full_path,
            cleanup=cleanup,
        )

        # TODO: Remove this terrible hack and async mock the code correctly
        # This works around "TypeError: object
        # MagicMock can't be used in 'await' expression"
        changed_packages: Dict[str, Set[str]] = {}
        if not isinstance(mirror, Mock):  # type: ignore
            changed_packages = await mirror.synchronize()
        logger.info(f"{len(changed_packages)} packages had changes")
        for package_name, changes in changed_packages.items():
            for change in changes:
                mirror.diff_file_list.append(os.path.join(str(mirror.homedir), change))
            logger.debug(f"{package_name} added: {changes}")

        if mirror.diff_full_path:
            logger.info(f"Writing diff file to {mirror.diff_full_path}")
            with open(mirror.diff_full_path, "w", encoding="utf-8") as f:
                for filename in mirror.diff_file_list:
                    f.write(f"{os.path.abspath(filename)}{os.linesep}")

    return 0
