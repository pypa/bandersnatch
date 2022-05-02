import asyncio
import configparser
import datetime
import hashlib
import html
import logging
import os
import sys
import time
from json import dump
from pathlib import Path, WindowsPath
from threading import RLock
from typing import Any, Awaitable, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import unquote, urlparse

from filelock import Timeout
from packaging.utils import canonicalize_name

from . import utils
from .configuration import validate_config_values
from .errors import PackageNotFound
from .filter import LoadedFilters
from .master import Master
from .package import Package
from .storage import storage_backend_plugins

LOG_PLUGINS = True
logger = logging.getLogger(__name__)


class Mirror:
    synced_serial: Optional[int] = 0  # The last serial we have consistently synced to.
    target_serial: Optional[int] = None  # What is the serial we are trying to reach?
    packages_to_sync: Dict[str, Union[int, str]] = {}

    # We are required to leave a 'last changed' timestamp. I'd rather err
    # on the side of giving a timestamp that is too old so we keep track
    # of it when starting to sync.
    now = None

    # PEP620 Simple API Version
    pypi_repository_version = "1.0"

    def __init__(self, master: Master, workers: int = 3):
        self.master = master
        self.filters = LoadedFilters(load_all=True)
        self.workers = workers
        if self.workers > 10:
            raise ValueError("Downloading with more than 10 workers is not allowed")

        # Lets record and report back the changes we do each run
        # Format: dict['pkg_name'] = [set(removed), Set[added]
        # Class Instance variable so each package can add their changes
        self.altered_packages: Dict[str, Set[str]] = {}

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
        else:
            # Synchronize specific packages. This method doesn't update the statusfile
            # Pass serial number 0 to bypass the stale serial check in Package class
            SERIAL_DONT_CARE = 0
            self.packages_to_sync = {
                utils.bandersnatch_safe_name(name): SERIAL_DONT_CARE
                for name in specific_packages
            }

        if not self.filters.filter_metadata_plugins():
            logger.info("No metadata filters are enabled. Skipping metadata filtering")
        if not self.filters.filter_release_plugins():
            logger.info("No release filters are enabled. Skipping release filtering")
        if not self.filters.filter_release_file_plugins():
            logger.info(
                "No release file filters are enabled. Skipping release file filtering"
            )

        await self.sync_packages()
        self.finalize_sync()
        return self.altered_packages

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
        raise NotImplementedError()

    async def package_syncer(self, idx: int) -> None:
        logger.debug(f"Package syncer {idx} started for duty")
        while True:
            try:
                package = self.package_queue.get_nowait()
                await package.update_metadata(self.master, attempts=3)
                await self.process_package(package)
            except asyncio.QueueEmpty:
                logger.debug(f"Package syncer {idx} emptied queue")
                break
            except PackageNotFound:
                continue
            except Exception as e:
                self.on_error(e, package=package)

    async def process_package(self, package: Package) -> None:
        raise NotImplementedError()

    async def sync_packages(self) -> None:
        try:
            self.package_queue: asyncio.Queue = asyncio.Queue()
            # Sorting the packages alphabetically makes it more predictable:
            # easier to debug and easier to follow in the logs.
            for name in sorted(self.packages_to_sync):
                serial = int(self.packages_to_sync[name])
                await self.package_queue.put(Package(name, serial=serial))

            sync_coros: List[Awaitable] = [
                self.package_syncer(idx) for idx in range(self.workers)
            ]
            try:
                await asyncio.gather(*sync_coros)
            except KeyboardInterrupt as e:
                self.on_error(e)
        except (ValueError, TypeError) as e:
            # This is for when self.packages_to_sync isn't of type Dict[str, int]
            # Which occurs during testing or if BandersnatchMirror's todolist is
            # corrupted in determine_packages_to_sync()
            # TODO Remove this check by following packages_to_sync's typing
            self.on_error(e)

    def finalize_sync(self) -> None:
        raise NotImplementedError()

    def on_error(self, exception: BaseException, **kwargs: Dict) -> None:
        raise NotImplementedError()


class BandersnatchMirror(Mirror):
    need_index_sync = True
    errors = False

    need_wrapup = False

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
        release_files_save: bool = True,
        compare_method: Optional[str] = None,
        download_mirror: Optional[str] = None,
        download_mirror_no_fallback: Optional[bool] = False,
    ) -> None:
        super().__init__(master=master, workers=workers)
        self.cleanup = cleanup

        if storage_backend:
            self.storage_backend = next(iter(storage_backend_plugins(storage_backend)))
        else:
            self.storage_backend = next(iter(storage_backend_plugins()))
        self.stop_on_error = stop_on_error
        self.loop = asyncio.get_event_loop()
        if isinstance(homedir, WindowsPath):
            self.homedir = self.storage_backend.PATH_BACKEND(homedir.as_posix())
        else:
            self.homedir = self.storage_backend.PATH_BACKEND(str(homedir))
        self.lockfile_path = self.homedir / ".lock"
        self.master = master

        # Stop soon after meeting an error. Continue without updating the
        # mirror's serial if false.
        self.stop_on_error = stop_on_error
        # Whether or not to mirror PyPI JSON metadata to disk
        self.json_save = json_save
        # Whether or not to mirror PyPI release files to disk
        self.release_files_save = release_files_save
        self.hash_index = hash_index
        # Allow configuring a root_uri to make generated index pages absolute.
        # This is generally not necessary, but was added for the official internal
        # PyPI mirror, which requires serving packages from
        # https://files.pythonhosted.org
        self.root_uri: Optional[str] = root_uri or ""
        self.diff_file = diff_file
        self.diff_append_epoch = diff_append_epoch
        self.diff_full_path = diff_full_path
        self.keep_index_versions = keep_index_versions
        self.digest_name = digest_name if digest_name else "sha256"
        self.compare_method = compare_method if compare_method else "hash"
        self.download_mirror = download_mirror
        self.download_mirror_no_fallback = download_mirror_no_fallback
        self.workers = workers
        self.diff_file_list = diff_file_list or []
        if self.workers > 10:
            raise ValueError("Downloading with more than 10 workers is not allowed.")
        self._bootstrap(flock_timeout)
        self._finish_lock = RLock()

    @property
    def webdir(self) -> Path:
        return self.homedir / "web"

    @property
    def todolist(self) -> Path:
        return self.homedir / "todo"

    def find_target_serial(self) -> int:
        return max(
            [self.synced_serial] + [int(v) for v in self.packages_to_sync.values()]
        )

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
        self.need_wrapup = True

        if self.storage_backend.exists(self.todolist):
            # We started a sync previously and left a todo list as well as the
            # targetted serial. We'll try to keep going through the todo list
            # and then mark the targetted serial as done
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
            self.target_serial = self.find_target_serial()
        else:
            logger.info("Syncing based on changelog.")
            changed_packages = await self.master.changed_packages(self.synced_serial)
            self.packages_to_sync.update(changed_packages)
            self.target_serial = self.find_target_serial()
            # We can avoid writing the main index page if we don't have
            # anything todo at all during a changelog-based sync.
            self.need_index_sync = bool(self.packages_to_sync)

        self._filter_packages()
        logger.info(f"Trying to reach serial: {self.target_serial}")
        pkg_count = len(self.packages_to_sync)
        logger.info(f"{pkg_count} packages to sync.")

    async def process_package(self, package: Package) -> None:
        loop = asyncio.get_running_loop()
        # Don't save anything if our metadata filters all fail.
        if not package.filter_metadata(self.filters.filter_metadata_plugins()):
            return None

        # save the metadata before filtering releases
        # (dalley): why? the original author does not remember, and it doesn't seem
        # to make a lot of sense.
        # https://github.com/pypa/bandersnatch/commit/2a8cf8441b97f28eb817042a65a042d680fa527e#r39676370
        if self.json_save:
            json_saved = await loop.run_in_executor(
                self.storage_backend.executor,
                self.save_json_metadata,
                package.metadata,
                package.name,
            )
            assert json_saved

        package.filter_all_releases_files(self.filters.filter_release_file_plugins())
        package.filter_all_releases(self.filters.filter_release_plugins())

        if self.release_files_save:
            await self.sync_release_files(package)

        await loop.run_in_executor(
            self.storage_backend.executor, self.sync_simple_page, package
        )
        # XMLRPC PyPI Endpoint stores raw_name so we need to provide it
        await loop.run_in_executor(
            self.storage_backend.executor,
            self.record_finished_package,
            package.raw_name,
        )

        # Cleanup old legacy non PEP 503 Directories created for the Simple API
        await self.cleanup_non_pep_503_paths(package)

    def finalize_sync(self) -> None:
        self.sync_index_page()
        if self.need_wrapup:
            self.wrapup_successful_sync()
        return None

    def on_error(self, exception: BaseException, **kwargs: Dict) -> None:
        self.errors = True
        if isinstance(exception, KeyboardInterrupt):
            # Setting self.errors to True to ensure we don't save Serial
            # and thus save to disk that we've had a successful sync
            logger.info(
                "Cancelling, all downloads are forcibly stopped, data may be "
                + "corrupted. Serial will not be saved to disk. "
                + "Next sync will start from previous serial"
            )
        elif isinstance(exception, TypeError) or isinstance(exception, ValueError):
            # This occurs for testing or when todolist is corrupt
            pass
        else:
            package: Any = kwargs.get("package", None)
            if package:
                logger.exception(
                    f"Error syncing package: {package.name}@{package.serial}"
                )
            if self.stop_on_error:
                logger.error("Exiting early after error.")
                sys.exit(1)

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
            if str(deprecated_dir) != str(self.simple_directory(package)):
                if not deprecated_dir.exists():
                    logger.debug(f"{deprecated_dir} does not exist. Not cleaning up")
                    continue

                logger.info(
                    f"Attempting to cleanup non PEP 503 simple dir: {deprecated_dir}"
                )
                try:
                    for file in deprecated_dir.glob("*"):
                        file.unlink(missing_ok=True)
                    deprecated_dir.rmdir()
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
        simple_path = self.storage_backend.PATH_BACKEND(str(simple_dir))
        return sorted(
            {
                canonicalize_name(str(x.parent.relative_to(simple_path)))
                for x in simple_path.glob("**/index.html")
                if str(x.parent.relative_to(simple_path)) != "."
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
            f.write(
                '    <meta name="pypi:repository-version" content='
                f'"{self.pypi_repository_version}">\n'
            )
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

        with self.storage_backend.update_safe(
            last_modified, mode="w", encoding="utf-8"
        ) as f:
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
        return self.storage_backend.PATH_BACKEND(str(self.homedir)) / "status"

    @property
    def generationfile(self) -> Path:
        return self.storage_backend.PATH_BACKEND(str(self.homedir)) / "generation"

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
        with self.storage_backend.update_safe(
            self.generationfile, mode="w", encoding="ascii"
        ) as f:
            f.write(str(CURRENT_GENERATION))
        # Now, actually proceed towards using the status files.
        if not self.statusfile.exists():
            logger.info(f"Status file {self.statusfile} missing. Starting over.")
            return
        self.synced_serial: int = int(
            self.statusfile.read_text(encoding="ascii").strip()
        )

    def _save(self) -> None:
        with self.storage_backend.update_safe(
            self.statusfile, mode="w+", encoding="ascii"
        ) as f:
            f.write(str(self.synced_serial))

    """
    BandersnatchMirror now includes all the original aspects of Mirror
    The next functions and properities are moved from Package
    """

    def json_file(self, package_name: str) -> Path:
        return Path(self.webdir / "json" / package_name)

    def json_pypi_symlink(self, package_name: str) -> Path:
        return Path(self.webdir / "pypi" / package_name / "json")

    def simple_directory(self, package: Package) -> Path:
        if self.hash_index:
            return self.webdir / "simple" / package.name[0] / package.name
        return self.webdir / "simple" / package.name

    def save_json_metadata(self, package_info: Dict, name: str) -> bool:
        """
        Take the JSON metadata we just fetched and save to disk
        """
        try:
            # TODO: Fix this so it works with swift
            with self.storage_backend.rewrite(self.json_file(name)) as jf:
                dump(package_info, jf, indent=4, sort_keys=True)
            self.diff_file_list.append(self.json_file(name))
        except Exception as e:
            logger.error(
                f"Unable to write json to {self.json_file(name)}: {str(e)} ({type(e)})"
            )
            return False

        symlink_dir = self.json_pypi_symlink(name).parent
        symlink_dir.mkdir(exist_ok=True)
        # Lets always ensure symlink is pointing to correct self.json_file
        # In 4.0 we move to normalized name only so want to overwrite older symlinks
        if self.json_pypi_symlink(name).exists():
            self.json_pypi_symlink(name).unlink()
        self.json_pypi_symlink(name).symlink_to(
            os.path.relpath(self.json_file(name), self.json_pypi_symlink(name).parent)
        )

        return True

    def populate_download_urls(
        self, release_file: Dict[str, str]
    ) -> Tuple[str, List[str]]:
        """
        Populate download URLs for a certain file, possible combinations are:

        - download_mirror is not set:
          return "url" attribute from release_file
        - download_mirror is set, no_fallback is false:
          prepend "download_mirror + path" before "url"
        - download_mirror is set, no_fallback is true:
          return only "download_mirror + path"

        Theoritically we are able to support multiple download mirrors by prepending
        more urls in the list.

        """
        release_url = release_file["url"]
        release_path = urlparse(release_url).path

        if self.download_mirror and not self.download_mirror_no_fallback:
            download_urls = [
                self.download_mirror + release_path,
                release_url,
            ]
        elif self.download_mirror and self.download_mirror_no_fallback:
            download_urls = [
                self.download_mirror + release_path,
            ]
        else:
            download_urls = [release_url]

        return (release_path, download_urls)

    async def sync_release_files(self, package: Package) -> None:
        """Purge + download files returning files removed + added"""
        downloaded_files = set()
        deferred_exception = None
        for release_file in package.release_files:
            release_path, download_urls = self.populate_download_urls(release_file)
            for cnt, url in enumerate(download_urls):
                try:
                    downloaded_file = await self.download_file(
                        url,
                        release_file["size"],
                        datetime.datetime.fromisoformat(
                            release_file["upload_time_iso_8601"].replace("Z", "+00:00")
                        ),
                        release_file["digests"]["sha256"],
                        urlpath=release_path,
                    )
                    if downloaded_file:
                        downloaded_files.add(
                            str(downloaded_file.relative_to(self.homedir))
                        )
                        break
                except Exception as e:
                    # Avoid flooding log messages with exception traceback
                    if not len(download_urls) == (cnt + 1):
                        logger.info(
                            "Continuing to next candidate URL after error downloading: "
                            f"{url}"
                        )
                    # Log an ERROR entry with traceback for the last URL entry in list,
                    # suggesting the final attemp of retriving the file has failed
                    else:
                        logger.exception(
                            "Continuing to next file after error downloading: " f"{url}"
                        )
                    # keep previous exception, also ignore non-default urls
                    if not deferred_exception and len(download_urls) == (cnt + 1):
                        deferred_exception = e
        if deferred_exception:
            raise deferred_exception  # raise the exception after trying all files

        self.altered_packages[package.name] = downloaded_files

    def gen_html_file_tags(self, release: Dict) -> str:
        file_tags = ""

        # data-requires-python: requires_python
        if "requires_python" in release and release["requires_python"] is not None:
            file_tags += (
                f' data-requires-python="{html.escape(release["requires_python"])}"'
            )

        # data-yanked: yanked_reason
        if "yanked" in release and release["yanked"]:
            if "yanked_reason" in release and release["yanked_reason"]:
                file_tags += f' data-yanked="{html.escape(release["yanked_reason"])}"'
            else:
                file_tags += ' data-yanked=""'

        return file_tags

    def generate_simple_page(self, package: Package) -> str:
        # Generate the header of our simple page.
        simple_page_content = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "  <head>\n"
            '    <meta name="pypi:repository-version" content="{0}">\n'
            "    <title>Links for {1}</title>\n"
            "  </head>\n"
            "  <body>\n"
            "    <h1>Links for {1}</h1>\n"
        ).format(self.pypi_repository_version, package.raw_name)

        release_files = package.release_files
        logger.debug(f"There are {len(release_files)} releases for {package.name}")
        # Lets sort based on the filename rather than the whole URL
        # Typing is hard here as we allow Any/Dict[Any, Any] for JSON
        release_files.sort(key=lambda x: x["filename"])  # type: ignore

        digest_name = self.digest_name

        simple_page_content += "\n".join(
            [
                '    <a href="{}#{}={}"{}>{}</a><br/>'.format(
                    self._file_url_to_local_url(r["url"]),
                    digest_name,
                    r["digests"][digest_name],
                    self.gen_html_file_tags(r),
                    r["filename"],
                )
                for r in release_files
            ]
        )

        simple_page_content += (
            f"\n  </body>\n</html>\n<!--SERIAL {package.last_serial}-->"
        )

        return simple_page_content

    def sync_simple_page(self, package: Package) -> None:
        logger.info(
            f"Storing index page: {package.name} - in {self.simple_directory(package)}"
        )
        simple_page_content = self.generate_simple_page(package)
        if not self.simple_directory(package).exists():
            self.simple_directory(package).mkdir(parents=True)

        if self.keep_index_versions > 0:
            self._save_simple_page_version(simple_page_content, package)
        else:
            simple_page = self.simple_directory(package) / "index.html"
            with self.storage_backend.rewrite(simple_page, "w", encoding="utf-8") as f:
                f.write(simple_page_content)
            self.diff_file_list.append(simple_page)

    def _save_simple_page_version(
        self, simple_page_content: str, package: Package
    ) -> None:
        versions_path = self._prepare_versions_path(package)
        timestamp = utils.make_time_stamp()
        version_file_name = f"index_{package.serial}_{timestamp}.html"
        full_version_path = versions_path / version_file_name
        # TODO: Change based on storage backend
        with self.storage_backend.rewrite(
            full_version_path, "w", encoding="utf-8"
        ) as f:
            f.write(simple_page_content)
        self.diff_file_list.append(full_version_path)

        symlink_path = self.simple_directory(package) / "index.html"
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()

        symlink_path.symlink_to(full_version_path)

    def _prepare_versions_path(self, package: Package) -> Path:
        versions_path = (
            self.storage_backend.PATH_BACKEND(str(self.simple_directory(package)))
            / "versions"
        )
        if not versions_path.exists():
            versions_path.mkdir()
        else:
            version_files = list(sorted(versions_path.iterdir()))
            version_files_to_remove = len(version_files) - self.keep_index_versions + 1
            for i in range(version_files_to_remove):
                version_files[i].unlink()

        return versions_path

    def _file_url_to_local_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.path.startswith("/packages"):
            raise RuntimeError(f"Got invalid download URL: {url}")
        prefix = self.root_uri if self.root_uri else "../.."
        return prefix + parsed.path

    # TODO: This can also return SwiftPath instances now...
    def _file_url_to_local_path(self, url: str) -> Path:
        path = urlparse(url).path
        path = unquote(path)
        if not path.startswith("/packages"):
            raise RuntimeError(f"Got invalid download URL: {url}")
        path = path[1:]
        return self.webdir / path

    # TODO: This can also return SwiftPath instances now...
    async def download_file(
        self,
        url: str,
        file_size: str,
        upload_time: datetime.datetime,
        sha256sum: str,
        chunk_size: int = 64 * 1024,
        urlpath: str = "",
    ) -> Optional[Path]:
        if urlparse != "":
            path = self._file_url_to_local_path(urlpath)
        else:
            path = self._file_url_to_local_path(url)
        loop = asyncio.get_running_loop()

        # Avoid downloading again if we have the file and it matches the hash.
        if await loop.run_in_executor(self.storage_backend.executor, path.exists):
            existing_file_size = await loop.run_in_executor(
                self.storage_backend.executor, self.storage_backend.get_file_size, path
            )
            if existing_file_size != int(file_size):
                logger.info(
                    f"File size mismatch with local file {path}: expected {file_size} "
                    + f"got {existing_file_size}, will re-download."
                )
                await loop.run_in_executor(self.storage_backend.executor, path.unlink)
            elif self.compare_method == "stat":
                existing_upload_time = await loop.run_in_executor(
                    self.storage_backend.executor,
                    self.storage_backend.get_upload_time,
                    path,
                )
                if existing_upload_time == upload_time:
                    return None
                else:
                    existing_hash = await loop.run_in_executor(
                        self.storage_backend.executor,
                        self.storage_backend.get_hash,
                        str(path),
                    )
                    if existing_hash != sha256sum:
                        logger.info(
                            "File upload time and checksum mismatch with local "
                            + f"file {path}: expected "
                            + f"{sha256sum} got {existing_hash}, will re-download."
                        )
                        await loop.run_in_executor(
                            self.storage_backend.executor, path.unlink
                        )
                    else:
                        logger.info(f"Updating file upload time of local file {path}.")
                        await loop.run_in_executor(
                            self.storage_backend.executor,
                            self.storage_backend.set_upload_time,
                            path,
                            upload_time,
                        )
                        return None
            else:
                existing_hash = await loop.run_in_executor(
                    self.storage_backend.executor,
                    self.storage_backend.get_hash,
                    str(path),
                )
                if existing_hash == sha256sum:
                    return None
                else:
                    logger.info(
                        f"File checksum mismatch with local file {path}: expected "
                        + f"{sha256sum} got {existing_hash}, will re-download."
                    )
                    await loop.run_in_executor(
                        self.storage_backend.executor, path.unlink
                    )

        logger.info(f"Downloading: {url}")

        dirname = path.parent
        if not dirname.exists():
            dirname.mkdir(parents=True)

        # Even more special handling for the serial of package files here:
        # We do not need to track a serial for package files
        # as PyPI generally only allows a file to be uploaded once
        # and then maybe deleted. Re-uploading (and thus changing the hash)
        # is only allowed in extremely rare cases with intervention from the
        # PyPI admins.
        r_generator = self.master.get(url, required_serial=None)
        response = await r_generator.asend(None)

        checksum = hashlib.sha256()

        with self.storage_backend.rewrite(path, "wb") as f:
            while True:
                chunk = await response.content.read(chunk_size)
                if not chunk:
                    break
                checksum.update(chunk)
                f.write(chunk)

            existing_hash = checksum.hexdigest()
            if existing_hash != sha256sum:
                # Bad case: the file we got does not match the expected
                # checksum. Even if this should be the rare case of a
                # re-upload this will fix itself in a later run.
                raise ValueError(
                    f"Inconsistent file. {url} has hash {existing_hash} "
                    + f"instead of {sha256sum}."
                )

        # set upload time to avoid downloading again in next sync
        self.storage_backend.set_upload_time(path, upload_time)
        return path


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
        if await storage_plugin.loop.run_in_executor(
            storage_plugin.executor, diff_full_path.is_file
        ):
            diff_full_path.unlink()
        elif await storage_plugin.loop.run_in_executor(
            storage_plugin.executor, diff_full_path.is_dir
        ):
            diff_full_path = diff_full_path / "mirrored-files"

    mirror_url = config.get("mirror", "master")
    timeout = config.getfloat("mirror", "timeout")
    global_timeout = config.getfloat("mirror", "global-timeout", fallback=None)
    proxy = config.get("mirror", "proxy", fallback=None)
    storage_backend = config_values.storage_backend_name
    homedir = Path(config.get("mirror", "directory"))

    # Always reference those classes here with the fully qualified name to
    # allow them being patched by mock libraries!
    async with Master(mirror_url, timeout, global_timeout, proxy) as master:
        mirror = BandersnatchMirror(
            homedir,
            master,
            storage_backend=storage_backend,
            stop_on_error=config.getboolean("mirror", "stop-on-error"),
            workers=config.getint("mirror", "workers"),
            hash_index=config.getboolean("mirror", "hash-index"),
            json_save=config_values.json_save,
            root_uri=config_values.root_uri,
            digest_name=config_values.digest_name,
            compare_method=config_values.compare_method,
            keep_index_versions=config.getint(
                "mirror", "keep_index_versions", fallback=0
            ),
            diff_file=diff_file,
            diff_append_epoch=config_values.diff_append_epoch,
            diff_full_path=diff_full_path if diff_full_path else None,
            cleanup=config_values.cleanup,
            release_files_save=config_values.release_files_save,
            download_mirror=config_values.download_mirror,
            download_mirror_no_fallback=config_values.download_mirror_no_fallback,
        )
        changed_packages = await mirror.synchronize(specific_packages)

    logger.info(f"{len(changed_packages)} packages had changes")
    for package_name, changes in changed_packages.items():
        package_changes = []
        for change in changes:
            package_changes.append(mirror.homedir / change)
        mirror.diff_file_list.extend(package_changes)
        loggable_changes = [str(chg) for chg in package_changes]
        logger.debug(f"{package_name} added: {loggable_changes}")

    if mirror.diff_full_path:
        logger.info(f"Writing diff file to {mirror.diff_full_path}")
        diff_text = f"{os.linesep}".join(
            [str(chg.absolute()) for chg in mirror.diff_file_list]
        )
        diff_file = mirror.storage_backend.PATH_BACKEND(mirror.diff_full_path)
        await storage_plugin.loop.run_in_executor(
            storage_plugin.executor, diff_file.write_text, diff_text
        )

    return 0
