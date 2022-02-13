"""
Storage management
"""
import asyncio
import configparser
import contextlib
import datetime
import hashlib
import logging
import pathlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import (
    IO,
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Type,
    Union,
)

import filelock
import pkg_resources
from packaging.utils import canonicalize_name

from .configuration import BandersnatchConfig

PATH_TYPES = Union[pathlib.Path, str]

# The API_REVISION is incremented if the plugin class is modified in a
# backwards incompatible way.  In order to prevent loading older
# broken plugins that may be installed and will break due to changes to
# the methods of the classes.
PLUGIN_API_REVISION = 1
STORAGE_PLUGIN_RESOURCE = f"bandersnatch_storage_plugins.v{PLUGIN_API_REVISION}.backend"
loaded_storage_plugins: Dict[str, List["Storage"]] = defaultdict(list)

logger = logging.getLogger("bandersnatch")


class Storage:
    """
    Base Storage class
    """

    name = "storage"
    PATH_BACKEND: Type[pathlib.Path] = pathlib.Path

    def __init__(
        self,
        *args: Any,
        config: Optional[configparser.ConfigParser] = None,
        **kwargs: Any,
    ) -> None:
        self.flock_path: PATH_TYPES = ".lock"
        if config is not None:
            if isinstance(config, BandersnatchConfig):
                config = config.config
            self.configuration = config
        else:
            self.configuration = BandersnatchConfig().config
        try:
            storage_backend = self.configuration["mirror"]["storage-backend"]
        except (KeyError, TypeError):
            storage_backend = "filesystem"
        if storage_backend != self.name:
            return
        # register relevant path backends etc
        self.initialize_plugin()
        try:
            self.mirror_base_path = self.PATH_BACKEND(
                self.configuration.get("mirror", "directory")
            )
        except (configparser.NoOptionError, configparser.NoSectionError):
            self.mirror_base_path = self.PATH_BACKEND(".")
        self.web_base_path = self.mirror_base_path / "web"
        self.json_base_path = self.web_base_path / "json"
        self.pypi_base_path = self.web_base_path / "pypi"
        self.simple_base_path = self.web_base_path / "simple"
        self.executor = ThreadPoolExecutor(
            max_workers=self.configuration.getint("mirror", "workers")
        )
        self.loop = asyncio.get_event_loop()

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name}, "
            f"mirror_base_path={self.mirror_base_path!s})"
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} object: {self.name} @ "
            f"{self.mirror_base_path!s}>"
        )

    def __hash__(self) -> int:
        return hash((self.name, str(self.directory), str(self.flock_path)))

    @property
    def directory(self) -> str:
        try:
            return self.configuration.get("mirror", "directory")
        except (configparser.NoOptionError, configparser.NoSectionError):
            return "/srv/pypi"

    @staticmethod
    def canonicalize_package(name: str) -> str:
        return str(canonicalize_name(name))

    def get_lock(self, path: str) -> filelock.BaseFileLock:
        """
        Retrieve the appropriate `FileLock` backend for this storage plugin

        :param str path: The path to use for locking
        :return: A `FileLock` backend for obtaining locks
        :rtype: filelock.BaseFileLock
        """
        raise NotImplementedError

    def get_json_paths(self, name: str) -> Sequence[PATH_TYPES]:
        canonicalized_name = self.canonicalize_package(name)
        paths = [
            self.json_base_path / canonicalized_name,
            self.pypi_base_path / canonicalized_name,
        ]
        if canonicalized_name != name:
            paths.append(self.json_base_path / name)
        return paths

    def get_flock_path(self) -> PATH_TYPES:
        raise NotImplementedError

    def initialize_plugin(self) -> None:
        """
        Code to initialize the plugin
        """
        # The intialize_plugin method is run once to initialize the plugin.  This should
        # contain all code to set up the plugin.
        # This method is not run in the fast path and should be used to do things like
        # indexing filter databases, etc that will speed the operation of the filter
        # and check_match methods that are called in the fast path.
        pass

    def hash_file(self, path: PATH_TYPES, function: str = "sha256") -> str:
        h = getattr(hashlib, function)()
        with self.open_file(path, text=False) as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return str(h.hexdigest())

    def iter_dir(self, path: PATH_TYPES) -> Generator[PATH_TYPES, None, None]:
        """Iterate over the path, returning the sub-paths"""
        if not issubclass(type(path), pathlib.Path):
            path = self.PATH_BACKEND(str(path))
        assert isinstance(path, pathlib.Path)
        yield from path.iterdir()

    @contextlib.contextmanager
    def rewrite(
        self, filepath: PATH_TYPES, mode: str = "w", **kw: Any
    ) -> Generator[IO, None, None]:
        """Rewrite an existing file atomically to avoid programs running in
        parallel to have race conditions while reading."""
        raise NotImplementedError

    @contextlib.contextmanager
    def update_safe(self, filename: PATH_TYPES, **kw: Any) -> Generator[IO, None, None]:
        """Rewrite a file atomically.

        Clients are allowed to delete the tmpfile to signal that they don't
        want to have it updated.

        """
        raise NotImplementedError

    def find(self, root: PATH_TYPES, dirs: bool = True) -> str:
        """A test helper simulating 'find'.

        Iterates over directories and filenames, given as relative paths to the
        root.

        """
        raise NotImplementedError

    def compare_files(self, file1: PATH_TYPES, file2: PATH_TYPES) -> bool:
        """
        Compare two files and determine whether they contain the same data. Return
        True if they match
        """
        raise NotImplementedError

    def write_file(self, path: PATH_TYPES, contents: Union[str, bytes]) -> None:
        """Write data to the provided path.  If **contents** is a string, the file will
        be opened and written in "r" + "utf-8" mode, if bytes are supplied it will be
        accessed using "rb" mode (i.e. binary write)."""
        raise NotImplementedError

    @contextlib.contextmanager
    def open_file(
        self, path: PATH_TYPES, text: bool = True
    ) -> Generator[IO, None, None]:
        """Yield a file context to iterate over. If text is true, open the file with
        'rb' mode specified."""
        raise NotImplementedError

    def read_file(
        self,
        path: PATH_TYPES,
        text: bool = True,
        encoding: str = "utf-8",
        errors: Optional[str] = None,
    ) -> Union[str, bytes]:
        """Yield a file context to iterate over. If text is true, open the file with
        'rb' mode specified."""
        raise NotImplementedError

    def delete(self, path: PATH_TYPES, dry_run: bool = False) -> int:
        """Delete the provided path."""
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        log_prefix = "[DRY RUN] " if dry_run else ""
        logger.info(f"{log_prefix}Deleting path: {path!s}")
        if not dry_run:
            if not self.exists(path):
                logger.debug(f"{path!s} does not exist. Skipping")
                return 0
            if self.is_file(path):
                return self.delete_file(path, dry_run=dry_run)
            else:
                return self.rmdir(path, dry_run=dry_run, force=True)
        return 0

    def delete_file(self, path: PATH_TYPES, dry_run: bool = False) -> int:
        """Delete the provided path, recursively if necessary."""
        raise NotImplementedError

    def copy_file(self, source: PATH_TYPES, dest: PATH_TYPES) -> None:
        """Copy a file from **source** to **dest**"""
        raise NotImplementedError

    def move_file(self, source: PATH_TYPES, dest: PATH_TYPES) -> None:
        """Move a file from **source** to **dest**"""
        raise NotImplementedError

    def mkdir(
        self, path: PATH_TYPES, exist_ok: bool = False, parents: bool = False
    ) -> None:
        """Create the provided directory"""
        raise NotImplementedError

    def rmdir(
        self,
        path: PATH_TYPES,
        recurse: bool = False,
        force: bool = False,
        ignore_errors: bool = False,
        dry_run: bool = False,
    ) -> int:
        """Remove the directory. If recurse is True, allow removing empty children.
        If force is true, remove contents destructively."""
        raise NotImplementedError

    def exists(self, path: PATH_TYPES) -> bool:
        """Check whether the provided path exists"""
        raise NotImplementedError

    def is_dir(self, path: PATH_TYPES) -> bool:
        """Check whether the provided path is a directory."""
        raise NotImplementedError

    def is_file(self, path: PATH_TYPES) -> bool:
        """Check whether the provided path is a file."""
        raise NotImplementedError

    def symlink(self, source: PATH_TYPES, dest: PATH_TYPES) -> None:
        """Create a symlink at **dest** that points back at **source**"""
        if not issubclass(type(dest), pathlib.Path):
            dest = self.PATH_BACKEND(dest)
        assert isinstance(dest, pathlib.Path)
        dest.symlink_to(source)

    def get_hash(self, path: PATH_TYPES, function: str = "sha256") -> str:
        """Get the sha256sum of a given **path**"""
        raise NotImplementedError

    def get_file_size(self, path: PATH_TYPES) -> int:
        """Get the size of a given **path** in bytes"""
        raise NotImplementedError

    def get_upload_time(self, path: PATH_TYPES) -> datetime.datetime:
        """Get the upload time of a given **path**"""
        raise NotImplementedError

    def set_upload_time(self, path: PATH_TYPES, time: datetime.datetime) -> None:
        """Set the upload time of a given **path**"""
        raise NotImplementedError


class StoragePlugin(Storage):
    """
    Plugin that provides a storage backend for bandersnatch
    """

    name = "storage_plugin"


def load_storage_plugins(
    entrypoint_group: str,
    enabled_plugin: Optional[str] = None,
    config: Optional[configparser.ConfigParser] = None,
    clear_cache: bool = False,
) -> Set[Storage]:
    """
    Load all storage plugins that are registered with pkg_resources

    Parameters
    ==========
    entrypoint_group: str
        The entrypoint group name to load plugins from
    enabled_plugin: str
        The optional enabled storage plugin to search for
    config: configparser.ConfigParser
        The optional configparser instance to pass in
    clear_cache: bool
        Whether to clear the plugin cache

    Returns
    =======
    List of Storage:
        A list of objects derived from the Storage class
    """
    global loaded_storage_plugins
    if config is None:
        config = BandersnatchConfig().config
    if not enabled_plugin:
        try:
            enabled_plugin = config["mirror"]["storage-backend"]
            logger.info(f"Loading storage plugin: {enabled_plugin}")
        except KeyError:
            enabled_plugin = "filesystem"
            logger.info(
                "Failed to find configured storage backend, using default: "
                f"{enabled_plugin}"
            )
            pass

    if clear_cache:
        loaded_storage_plugins = defaultdict(list)

    # If the plugins for the entrypoint_group have been loaded return them
    cached_plugins = loaded_storage_plugins.get(entrypoint_group)
    if cached_plugins:
        return set(cached_plugins)

    plugins = set()
    for entry_point in pkg_resources.iter_entry_points(group=entrypoint_group):
        if entry_point.name == enabled_plugin + "_plugin":
            try:
                plugin_class = entry_point.load()
                plugin_instance = plugin_class(config=config)
                plugins.add(plugin_instance)
            except ModuleNotFoundError as me:
                logger.error(f"Unable to load entry point {entry_point}: {me}")

    loaded_storage_plugins[entrypoint_group] = list(plugins)

    return plugins


def storage_backend_plugins(
    backend: Optional[str] = "filesystem",
    config: Optional[configparser.ConfigParser] = None,
    clear_cache: bool = False,
) -> Iterable[Storage]:
    """
    Load and return the release filtering plugin objects

    Parameters
    ==========
    backend: str
        The optional enabled storage plugin to search for
    config: configparser.ConfigParser
        The optional configparser instance to pass in
    clear_cache: bool
        Whether to clear the plugin cache

    Returns
    -------
    list of bandersnatch.storage.Storage:
        List of objects derived from the bandersnatch.storage.Storage class
    """
    return load_storage_plugins(
        STORAGE_PLUGIN_RESOURCE,
        enabled_plugin=backend,
        config=config,
        clear_cache=clear_cache,
    )
