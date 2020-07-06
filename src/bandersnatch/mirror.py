import asyncio
import configparser
import datetime
import logging
import os
import time
from pathlib import Path
from shutil import rmtree
from threading import RLock
from typing import Awaitable, Dict, List, Optional, Set, Union
from unittest.mock import Mock

from filelock import Timeout
from packaging.utils import canonicalize_name

from . import utils
from .configuration import validate_config_values
from .filter import LoadedFilters
from .master import Master
from .package import Package
from .storage import storage_backend_plugins

LOG_PLUGINS = True
logger = logging.getLogger(__name__)


class Mirror:

    synced_serial = 0  # The last serial we have consistently synced to.
    target_serial = None  # What is the serial we are trying to reach?
    errors = False
    packages_to_sync: Dict[str, Union[int, str]] = {}
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
    root_uri: Optional[str] = ""

    diff_file = None
    diff_append_epoch = False
    diff_full_path = None

    def __init__(
        self,
        homedir: Path,
        master: Master,
        storage_backend: Optional[str] = None,
        stop_on_error: bool = False,
        workers: int = 3,
        hash_index: bool = False,
        json_save: bool = False,
        digest_name: Optional[str] = None,
        root_uri: Optional[str] = None,
        keep_index_versions: int = 0,
        diff_file: Optional[Union[Path, str]] = None,
        diff_append_epoch: bool = False,
        diff_full_path: Optional[Union[Path, str]] = None,
        flock_timeout: int = 1,
        diff_file_list: Optional[List] = None,
        *,
        cleanup: bool = False,
    ):
        if storage_backend:
            self.storage_backend = next(iter(storage_backend_plugins(storage_backend)))
        else:
            self.storage_backend = next(iter(storage_backend_plugins()))
        self.loop = asyncio.get_event_loop()
        self.homedir = self.storage_backend.PATH_BACKEND(homedir)
        self.lockfile_path = self.homedir / ".lock"
        self.master = master
        self.filters = LoadedFilters(load_all=True)
        self.stop_on_error = stop_on_error
        self.json_save = json_save
        self.hash_index = hash_index
        self.root_uri = root_uri or ""
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
        self.altered_packages: Dict[str, Set[str]] = {}

    @property
    def webdir(self) -> Path:
        return self.homedir / "web"

    @property
    def todolist(self) -> Path:
        return self.homedir / "todo"

    async def synchronize(
        self, specific_packages: Optional[List[str]] = None
    ) -> Dict[str, Set[str]]:
        logger.info(f"Syncing with {self.master.url}.")
        self.now = datetime.datetime.utcnow()
        # Lets ensure we get a new dict each run
        # - others importing may not reset this like our main.py
        self.altered_packages = {}

        if specific_packages is None:
            # Changelog-based synchronization
            await self.determine_packages_to_sync()
            await self.sync_packages()
            self.sync_index_page()
            self.wrapup_successful_sync()
        else:
            # Synchronize specific packages. This method doesn't update the
            # self.statusfile

            # Pass serial number 0 to bypass the stale serial check in Package class
            SERIAL_DONT_CARE = 0
            self.packages_to_sync = {
                utils.bandersnatch_safe_name(name): SERIAL_DONT_CARE
                for name in specific_packages
            }
            await self.sync_packages()
            self.sync_index_page()

        return self.altered_packages

    def _validate_todo(self) -> None:
        """Does a couple of cleanup tasks to ensure consistent data for later
        processing."""
        if self.storage_backend.exists(self.todolist):
            try:
                with self.storage_backend.open_file(self.todolist, text=True) as fh:
                    saved_todo = iter(fh)
                    int(next(saved_todo).strip())
                    for line in saved_todo:
                        _, serial = line.strip().split(maxsplit=1)
                        int(serial)
            except (StopIteration, ValueError, TypeError):
                # The todo list was inconsistent. This may happen if we get
                # killed e.g. by the timeout wrapper. Just remove it - we'll
                # just have to do whatever happened since the last successful
                # sync.
                logger.error("Removing inconsistent todo list.")
                self.storage_backend.delete_file(self.todolist)

    def _filter_packages(self) -> None:
        """
        Run the package filtering plugins and remove any packages from the
        packages_to_sync that match any filters.
        - Logging of action will be done within the check_match methods
        """
        global LOG_PLUGINS

        filter_plugins = self.filters.filter_project_plugins()
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

    async def determine_packages_to_sync(self) -> None:
        """
        Update the self.packages_to_sync to contain packages that need to be
        synced.
        """
        # In case we don't find any changes we will stay on the currently
        # synced serial.
        self.target_serial = self.synced_serial
        self.packages_to_sync = {}
        logger.info(f"Current mirror serial: {self.synced_serial}")

        if self.storage_backend.exists(self.todolist):
            # We started a sync previously and left a todo list as well as the
            # targetted serial. We'll try to keep going through the todo list
            # and then mark the targetted serial as done.
            logger.info("Resuming interrupted sync from local todo list.")
            with self.storage_backend.open_file(self.todolist, text=True) as fh:
                saved_todo = iter(fh)
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
                [self.synced_serial] + [int(v) for v in self.packages_to_sync.values()]
            )
        else:
            logger.info("Syncing based on changelog.")
            changed_packages = await self.master.changed_packages(self.synced_serial)
            self.packages_to_sync.update(changed_packages)
            self.target_serial = max(
                [self.synced_serial] + [int(v) for v in self.packages_to_sync.values()]
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

            await package.sync(self.filters)

            # Cleanup non normalized name directory
            await self.cleanup_non_pep_503_paths(package)

    async def sync_packages(self) -> None:
        self.package_queue: asyncio.Queue = asyncio.Queue()
        # Sorting the packages alphabetically makes it more predicatable:
        # easier to debug and easier to follow in the logs.
        for name in sorted(self.packages_to_sync):
            serial = self.packages_to_sync[name]
            await self.package_queue.put(Package(name, serial, self))

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

    def record_finished_package(self, name: str) -> None:
        with self._finish_lock:
            del self.packages_to_sync[name]
            with self.storage_backend.update_safe(
                self.todolist, mode="w+", encoding="utf-8"
            ) as f:
                # First line is the target serial we're working on.
                f.write(f"{self.target_serial}\n")
                # Consecutive lines are the packages we still have to sync
                todo = [
                    f"{name_} {serial}"
                    for name_, serial in self.packages_to_sync.items()
                ]
                f.write("\n".join(todo))

    async def cleanup_non_pep_503_paths(self, package: Package) -> None:
        """
        Before 4.0 we use to store backwards compatible named dirs for older pip
        This function checks for them and cleans them up
        """

        def raw_simple_directory() -> Path:
            if self.hash_index:
                return self.webdir / "simple" / package.raw_name[0] / package.raw_name
            return self.webdir / "simple" / package.raw_name

        def normalized_legacy_simple_directory() -> Path:
            normalized_name_legacy = utils.bandersnatch_safe_name(package.raw_name)
            if self.hash_index:
                return (
                    self.webdir
                    / "simple"
                    / normalized_name_legacy[0]
                    / normalized_name_legacy
                )
            return self.webdir / "simple" / normalized_name_legacy

        if not self.cleanup:
            return

        logger.debug(f"Running Non PEP503 path cleanup for {package.raw_name}")
        for deprecated_dir in (
            raw_simple_directory(),
            normalized_legacy_simple_directory(),
        ):
            # Had to compare path strs as Windows did not match path objects ...
            if str(deprecated_dir) != str(package.simple_directory):
                if not deprecated_dir.exists():
                    logger.debug(f"{deprecated_dir} does not exist. Not cleaning up")
                    continue

                logger.info(
                    f"Attempting to cleanup non PEP 503 simple dir: {deprecated_dir}"
                )
                try:
                    rmtree(deprecated_dir)
                except Exception:
                    logger.exception(
                        f"Unable to cleanup non PEP 503 dir {deprecated_dir}"
                    )

    # TODO: This can return SwiftPath types now
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

    def find_package_indexes_in_dir(self, simple_dir: Path) -> List[str]:
        """Given a directory that contains simple packages indexes, return
        a sorted list of normalized package names.  This presumes every
        directory within is a simple package index directory."""
        simple_path = self.storage_backend.PATH_BACKEND(simple_dir)
        return sorted(
            {
                # Filter out all of the "non" normalized names here
                canonicalize_name(x.name)
                for x in simple_path.iterdir()
                # Package indexes must be in directories, so ignore anything else.
                # This allows us to rely on the storage plugin to check if this is
                # a directory
                if x.is_dir()
            }
        )

    def sync_index_page(self) -> None:
        if not self.need_index_sync:
            return
        logger.info("Generating global index page.")
        simple_dir = self.webdir / "simple"
        with self.storage_backend.rewrite(str(simple_dir / "index.html")) as f:
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
        self.diff_file_list.append(simple_dir / "index.html")

    def wrapup_successful_sync(self) -> None:
        if self.errors:
            return
        self.synced_serial = int(self.target_serial) if self.target_serial else 0
        if self.todolist.exists():
            self.todolist.unlink()
        logger.info(f"New mirror serial: {self.synced_serial}")
        last_modified = self.homedir / "web" / "last-modified"
        if not self.now:
            logger.error(
                "strftime did not return a valid time - Not updating last modified"
            )
            return

        with self.storage_backend.rewrite(str(last_modified)) as f:
            f.write(self.now.strftime("%Y%m%dT%H:%M:%S\n"))
        self._save()

    def _bootstrap(self, flock_timeout: float = 1.0) -> None:
        paths = [
            self.storage_backend.PATH_BACKEND(""),
            self.storage_backend.PATH_BACKEND("web/simple"),
            self.storage_backend.PATH_BACKEND("web/packages"),
            self.storage_backend.PATH_BACKEND("web/local-stats/days"),
        ]
        if self.json_save:
            logger.debug("Adding json directories to bootstrap")
            paths.extend(
                [
                    self.storage_backend.PATH_BACKEND("web/json"),
                    self.storage_backend.PATH_BACKEND("web/pypi"),
                ]
            )
        for path in paths:
            path = self.homedir / path
            if not path.exists():
                logger.info(f"Setting up mirror directory: {path}")
                path.mkdir(parents=True)

        flock = self.storage_backend.get_lock(str(self.lockfile_path))
        try:
            logger.debug(f"Acquiring FLock with timeout: {flock_timeout!s}")
            with flock.acquire(timeout=flock_timeout):
                self._validate_todo()
                self._load()
        except Timeout:
            logger.error("Flock timed out!")
            raise RuntimeError(
                f"Could not acquire lock on {self.lockfile_path}. "
                + "Another instance could be running?"
            )

    @property
    def statusfile(self) -> Path:
        return self.storage_backend.PATH_BACKEND(self.homedir) / "status"

    @property
    def generationfile(self) -> Path:
        return self.storage_backend.PATH_BACKEND(self.homedir) / "generation"

    def _reset_mirror_status(self) -> None:
        for path in [self.statusfile, self.todolist]:
            if path.exists():
                path.unlink()

    def _load(self) -> None:
        # Simple generation mechanism to support transparent software
        # updates.
        CURRENT_GENERATION = 5  # noqa
        try:
            generation = int(self.generationfile.read_text(encoding="ascii").strip())
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
        self.generationfile.write_text(str(CURRENT_GENERATION), encoding="ascii")
        # Now, actually proceed towards using the status files.
        if not self.statusfile.exists():
            logger.info(f"Status file {self.statusfile} missing. Starting over.")
            return
        self.synced_serial = int(self.statusfile.read_text(encoding="ascii").strip())

    def _save(self) -> None:
        self.statusfile.write_text(str(self.synced_serial), encoding="ascii")


async def mirror(
    config: configparser.ConfigParser, specific_packages: Optional[List[str]] = None
) -> int:

    config_values = validate_config_values(config)

    storage_plugin = next(
        iter(
            storage_backend_plugins(
                config_values.storage_backend_name, config=config, clear_cache=True
            )
        )
    )

    diff_file = storage_plugin.PATH_BACKEND(config_values.diff_file_path)
    diff_full_path: Union[Path, str]
    if diff_file:
        diff_file.parent.mkdir(exist_ok=True, parents=True)
        if config_values.diff_append_epoch:
            diff_full_path = diff_file.with_name(f"{diff_file.name}-{int(time.time())}")
        else:
            diff_full_path = diff_file
    else:
        diff_full_path = ""

    if diff_full_path:
        if isinstance(diff_full_path, str):
            diff_full_path = storage_plugin.PATH_BACKEND(diff_full_path)
        if diff_full_path.is_file():
            diff_full_path.unlink()
        elif diff_full_path.is_dir():
            diff_full_path = diff_full_path / "mirrored-files"

    mirror_url = config.get("mirror", "master")
    timeout = config.getfloat("mirror", "timeout")
    global_timeout = config.getfloat("mirror", "global-timeout", fallback=None)

    # Always reference those classes here with the fully qualified name to
    # allow them being patched by mock libraries!
    async with Master(mirror_url, timeout, global_timeout) as master:
        mirror = Mirror(
            Path(config.get("mirror", "directory")),
            master,
            storage_backend=config_values.storage_backend_name,
            stop_on_error=config.getboolean("mirror", "stop-on-error"),
            workers=config.getint("mirror", "workers"),
            hash_index=config.getboolean("mirror", "hash-index"),
            json_save=config_values.json_save,
            root_uri=config_values.root_uri,
            digest_name=config_values.digest_name,
            keep_index_versions=config.getint(
                "mirror", "keep_index_versions", fallback=0
            ),
            diff_file=diff_file,
            diff_append_epoch=config_values.diff_append_epoch,
            diff_full_path=diff_full_path if diff_full_path else None,
            cleanup=config_values.cleanup,
        )

        # TODO: Remove this terrible hack and async mock the code correctly
        # This works around "TypeError: object
        # MagicMock can't be used in 'await' expression"
        changed_packages: Dict[str, Set[str]] = {}
        if not isinstance(mirror, Mock):  # type: ignore
            changed_packages = await mirror.synchronize(specific_packages)
        logger.info(f"{len(changed_packages)} packages had changes")
        for package_name, changes in changed_packages.items():
            for change in changes:
                mirror.diff_file_list.append(mirror.homedir / change)
            loggable_changes = [str(chg) for chg in mirror.diff_file_list]
            logger.debug(f"{package_name} added: {loggable_changes}")

        if mirror.diff_full_path:
            logger.info(f"Writing diff file to {mirror.diff_full_path}")
            diff_text = f"{os.linesep}".join(
                [str(chg.absolute()) for chg in mirror.diff_file_list]
            )
            diff_file = mirror.storage_backend.PATH_BACKEND(mirror.diff_full_path)
            diff_file.write_text(diff_text)

    return 0
