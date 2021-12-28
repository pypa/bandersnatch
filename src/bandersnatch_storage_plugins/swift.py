import atexit
import base64
import configparser
import contextlib
import datetime
import hashlib
import io
import logging
import os
import pathlib
import re
import shutil
import sys
import tempfile
from typing import (
    IO,
    Any,
    Dict,
    Generator,
    List,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

import filelock
import keystoneauth1
import keystoneauth1.exceptions.catalog
import keystoneauth1.identity
import swiftclient.client
import swiftclient.exceptions

from bandersnatch.storage import PATH_TYPES, StoragePlugin

logger = logging.getLogger("bandersnatch")


# See https://stackoverflow.com/a/8571649 for explanation
BASE64_RE = re.compile(b"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")


class SwiftFileLock(filelock.BaseFileLock):
    """
    Simply watches the existence of the lock file.
    """

    def __init__(
        self,
        lock_file: str,
        timeout: int = -1,
        backend: Optional["SwiftStorage"] = None,
    ) -> None:
        # The path to the lock file.
        self.backend: Optional["SwiftStorage"] = backend
        self._lock_file_fd: Optional["SwiftPath"]
        super().__init__(lock_file, timeout=timeout)

    @property
    def path_backend(self) -> Type["SwiftPath"]:
        if self.backend is not None:
            return self.backend.PATH_BACKEND
        raise RuntimeError("Failed to retrieve swift backend")

    def _acquire(self) -> None:
        try:
            logger.info("Attempting to acquire lock")
            fd: "SwiftPath" = self.path_backend(self.lock_file)
            fd.write_bytes(b"")
        except OSError as exc:
            logger.error("Failed to acquire lock...")
            logger.exception("Exception: ", exc)
            pass
        else:
            logger.info(f"Acquired lock: {self.lock_file}")
            self._lock_file_fd = fd
        return None

    def _release(self) -> None:
        self._lock_file_fd = None
        try:
            logger.info(f"Removing lock: {self.lock_file}")
            self.path_backend(self.lock_file).unlink()
        except OSError as exc:
            logger.error("Failed to remove lockfile")
            logger.exception("Exception: ", exc)
            pass
        else:
            logger.info("Successfully cleaned up lock")
        return None

    @property
    def is_locked(self) -> bool:
        return self.path_backend(self.lock_file).exists()


# TODO: Refactor this out into reusable base class?
class _SwiftAccessor:
    BACKEND: "SwiftStorage"

    @classmethod
    def register_backend(cls, backend: "SwiftStorage") -> None:
        cls.BACKEND = backend
        return

    @staticmethod
    def stat(target: str) -> NoReturn:
        raise NotImplementedError("stat() not available on this system")

    @staticmethod
    def lstat(target: str) -> NoReturn:
        raise NotImplementedError("lstat() not available on this system")

    @staticmethod
    def open(*args: Any, **kwargs: Any) -> IO:
        context: contextlib.ExitStack = contextlib.ExitStack()
        fh: IO = context.enter_context(
            _SwiftAccessor.BACKEND.open_file(*args, **kwargs)
        )
        atexit.register(context.close)
        return fh

    @staticmethod
    def listdir(target: str) -> List[str]:
        results: List[str] = []
        if not target.endswith("/"):
            target = f"{target}/"
        with _SwiftAccessor.BACKEND.connection() as conn:
            paths = conn.get_container(
                _SwiftAccessor.BACKEND.default_container, prefix=target, delimiter="/"
            )
            for p in paths:
                if "subdir" in p:
                    result = p["subdir"]
                    if not str(result).endswith("/"):
                        result = type(result)(f"{p['subdir']!s}/")
                else:
                    result = p["name"]
                results.append(result)
        return results

    @staticmethod
    def scandir(target: str) -> NoReturn:
        raise NotImplementedError("scandir() is not available on this platform")

    @staticmethod
    def chmod(target: str) -> NoReturn:
        raise NotImplementedError("chmod() is not available on this platform")

    def lchmod(self, pathobj: str, mode: int) -> NoReturn:
        raise NotImplementedError("lchmod() not available on this system")

    @staticmethod
    def mkdir(*args: Any, **kwargs: Any) -> None:
        return _SwiftAccessor.BACKEND.mkdir(*args, **kwargs)

    @staticmethod
    def unlink(*args: Any, **kwargs: Any) -> None:
        missing_ok = kwargs.pop("missing_ok", False)
        try:
            _SwiftAccessor.BACKEND.delete_file(*args, **kwargs)
        except OSError as exc:
            if not missing_ok:
                logger.exception("Failed to delete non-existent file...", exc)
            pass
        return None

    @staticmethod
    def link(*args: Any, **kwargs: Any) -> None:
        return _SwiftAccessor.BACKEND.copy_file(*args, **kwargs)

    @staticmethod
    def rmdir(*args: Any, **kwargs: Any) -> None:
        try:
            _SwiftAccessor.BACKEND.rmdir(*args, **kwargs)
        except OSError:
            pass
        return None

    @staticmethod
    def rename(*args: Any, **kwargs: Any) -> None:
        return _SwiftAccessor.BACKEND.copy_file(*args, **kwargs)

    @staticmethod
    def replace(*args: Any, **kwargs: Any) -> None:
        return _SwiftAccessor.BACKEND.copy_file(*args, **kwargs)

    @staticmethod
    def symlink(
        a: PATH_TYPES,
        b: PATH_TYPES,
        target_is_directory: bool = False,
        src_container: Optional[str] = None,
        src_account: Optional[str] = None,
    ) -> None:
        return _SwiftAccessor.BACKEND.symlink(
            a, b, src_container=src_container, src_account=src_account
        )

    @staticmethod
    def utime(target: str) -> None:
        return _SwiftAccessor.BACKEND.update_timestamp(target)

    # Helper for resolve()
    def readlink(self, path: str) -> str:
        return str(path)


_swift_accessor: Type[_SwiftAccessor]


class SwiftPath(pathlib.Path):
    _flavour = getattr(pathlib, "_posix_flavour")  # noqa
    BACKEND: "SwiftStorage"

    __slots__ = (
        "_drv",
        "_root",
        "_parts",
        "_str",
        "_hash",
        "_pparts",
        "_cached_cparts",
        "_accessor",
        "_closed",
    )

    def __new__(cls, *args: Any) -> "SwiftPath":
        self = cls._from_parts(args, init=False)
        self._init()
        return self

    def _init(self) -> None:
        self._accessor = _SwiftAccessor

    def __str__(self) -> str:
        """Return the string representation of the path, suitable for
        passing to system calls."""
        try:
            return self._str  # type: ignore
        except AttributeError:
            self._str = (
                self._format_parsed_parts(  # type: ignore
                    self._drv,  # type: ignore
                    self._root,  # type: ignore
                    self._parts,  # type: ignore
                )
                or "."
            )
            return self._str

    def __fspath__(self) -> str:
        return str(self)

    def __bytes__(self) -> bytes:
        """Return the bytes representation of the path.  This is only
        recommended to use under Unix."""
        return os.fsencode(str(self))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_posix()!r})"

    def _make_child_relpath(self, part: str) -> "SwiftPath":
        # This is an optimization used for dir walking.  `part` must be
        # a single part relative to this path.
        parts = self._parts + [os.path.relpath(part, start=str(self))]  # type: ignore
        return self._from_parsed_parts(self._drv, self._root, parts)  # type: ignore

    @classmethod
    def _parse_args(cls, args: Sequence[str]) -> Tuple[Optional[str], str, List[str]]:
        # This is useful when you don't want to create an instance, just
        # canonicalize some constructor arguments.
        parts: List[str] = []
        for a in args:
            a = os.fspath(a)
            if isinstance(a, str):
                # Force-cast str subclasses to str (issue #21127)
                parts.append(str(a))
            else:
                raise TypeError(
                    "argument should be a str object or an os.PathLike "
                    f"object returning str, not {type(a)}"
                )
        # Modification to prevent us from starting swift paths with "/"
        if parts[0].startswith("/"):
            parts[0] = parts[0].lstrip("/")
        return cls._flavour.parse_parts(parts)  # type: ignore

    @classmethod
    def _from_parts(cls, args: Sequence[str], init: bool = True) -> "SwiftPath":
        # We need to call _parse_args on the instance, so as to get the
        # right flavour.
        self = object.__new__(cls)
        drv, root, parts = self._parse_args(args)
        self._drv = drv  # type: ignore
        self._root = root  # type: ignore
        self._parts = parts  # type: ignore
        if init:
            self._init()
        return self

    @classmethod
    def _from_parsed_parts(
        cls, drv: Optional[str], root: str, parts: List[str], init: bool = True
    ) -> "SwiftPath":
        self = object.__new__(cls)
        self._drv = drv  # type: ignore
        self._root = root  # type: ignore
        self._parts = parts  # type: ignore
        if init:
            self._init()
        return self

    @classmethod
    def register_backend(cls, backend: "SwiftStorage") -> None:
        cls.BACKEND = backend
        return

    @property
    def backend(self) -> "SwiftStorage":
        assert self.BACKEND is not None
        return self.BACKEND

    def absolute(self) -> "SwiftPath":
        return self

    def touch(self) -> None:  # type: ignore[override]
        self.write_bytes(b"")

    def is_dir(self) -> bool:
        target_path = str(self)
        if (
            target_path
            and target_path != "."
            and not target_path.endswith(self._flavour.sep)
        ):
            target_path = f"{target_path}{self._flavour.sep}"
        files: List[str] = []
        with self.backend.connection() as conn:
            try:
                files = conn.get_container(
                    self.backend.default_container, prefix=target_path
                )
            except swiftclient.exceptions.ClientException:
                return False
            return bool(files)

    def is_file(self) -> bool:
        return self.backend.is_file(str(self))

    def is_symlink(self) -> bool:
        return self.backend.is_symlink(str(self))

    def exists(self) -> bool:
        return self.backend.exists(str(self))

    def mkdir(
        self, mode: int = 511, parents: bool = False, exist_ok: bool = False
    ) -> None:
        return self.backend.mkdir(str(self), exist_ok=exist_ok, parents=parents)

    def read_text(
        self, encoding: Optional[str] = None, errors: Optional[str] = None
    ) -> str:
        kwargs = {}
        if encoding is not None:
            kwargs["encoding"] = encoding
        if errors is not None:
            kwargs["errors"] = errors
        result = self.backend.read_file(str(self), text=True, **kwargs)
        assert isinstance(result, str)
        return result

    def write_text(
        self,
        contents: Optional[str],
        encoding: Optional[str] = "utf-8",
        errors: Optional[str] = None,
    ) -> int:
        if contents is None:
            contents = ""
        self.backend.write_file(
            str(self), contents=contents, encoding=encoding, errors=errors
        )
        return 0

    def symlink_to(
        self,
        src: PATH_TYPES,
        target_is_directory: bool = False,
        src_container: Optional[str] = None,
        src_account: Optional[str] = None,
    ) -> None:
        """
        Make this path a symlink pointing to the given path.
        Note the order of arguments (self, target) is the reverse of os.symlink's.
        """
        self._accessor.symlink(
            src,
            str(self),
            target_is_directory=target_is_directory,
            src_account=src_account,
            src_container=src_container,
        )

    def write_bytes(
        self,
        contents: bytes,
        encoding: Optional[str] = "utf-8",
        errors: Optional[str] = None,
    ) -> int:
        self.backend.write_file(
            str(self), contents=contents, encoding=encoding, errors=errors
        )
        return 0

    def read_bytes(self) -> bytes:
        result = self.backend.read_file(str(self), text=False)
        assert isinstance(result, bytes)
        return result

    def unlink(self, missing_ok: bool = False) -> None:
        self._accessor.unlink(str(self), missing_ok=missing_ok)

    def iterdir(
        self,
        conn: Optional[swiftclient.client.Connection] = None,
        recurse: bool = False,
        include_swiftkeep: bool = False,
    ) -> Generator["SwiftPath", None, None]:
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        for name in self._accessor.listdir(str(self)):
            if name in {".", ".."} or name == ".swiftkeep" and not include_swiftkeep:
                # Yielding a path object for these makes little sense
                continue
            path = self._make_child_relpath(name)
            if not recurse or not str(name).endswith("/") or not path.is_dir():
                yield path
            else:
                yield path
                yield from path.iterdir(conn=conn, recurse=recurse)


class SwiftStorage(StoragePlugin):
    name = "swift"
    PATH_BACKEND = SwiftPath

    @property
    def directory(self) -> str:
        try:
            return self.configuration.get("mirror", "directory")
        except configparser.NoOptionError:
            return "srv/pypi"

    def get_config_value(
        self, config_key: str, *env_keys: Any, default: Optional[str] = None
    ) -> Optional[str]:
        value = None
        try:
            value = self.configuration["swift"][config_key]
        except KeyError:
            os_key = next(iter(k for k in env_keys if k in os.environ), None)
            if os_key is not None:
                value = os.environ[os_key]
        if value is None:
            value = default
        return value

    def initialize_plugin(self) -> None:
        """
        Code to initialize the plugin
        """
        swift_credentials = {
            "user_domain_name": self.get_config_value(
                "user_domain_name", "OS_USER_DOMAIN_NAME", default="default"
            ),
            "project_domain_name": self.get_config_value(
                "project_domain_name", "OS_PROJECT_DOMAIN_NAME", default="default"
            ),
            "password": self.get_config_value("password", "OS_PASSWORD"),
        }
        os_options: Dict[str, Any] = {}
        user_id = self.get_config_value("username", "OS_USER_ID", "OS_USERNAME")
        project = self.get_config_value(
            "project_name", "OS_PROJECT_NAME", "OS_TENANT_NAME"
        )
        auth_url = self.get_config_value(
            "auth_url", "OS_AUTH_URL", "OS_AUTHENTICATION_URL"
        )
        object_storage_url = self.get_config_value(
            "object_storage_url", "OS_STORAGE_URL"
        )
        region = self.get_config_value("region", "OS_REGION_NAME")
        project_id = self.get_config_value("project_id", "OS_PROJECT_ID")
        if user_id:
            swift_credentials["username"] = user_id
        if project:
            swift_credentials["project_name"] = project
            os_options["project_name"] = project
        if object_storage_url:
            os_options["object_storage_url"] = object_storage_url
        if region:
            os_options["region_name"] = region
        if project_id:
            os_options["PROJECT_ID"] = project_id
        if auth_url:
            swift_credentials["auth_url"] = auth_url
        self.os_options = os_options
        self.auth = keystoneauth1.identity.v3.Password(**swift_credentials)
        self._test_connection()
        SwiftPath.register_backend(self)
        _SwiftAccessor.register_backend(self)
        global _swift_accessor
        _swift_accessor = _SwiftAccessor

    def get_lock(self, path: Optional[str] = None) -> SwiftFileLock:
        """
        Retrieve the appropriate `FileLock` backend for this storage plugin

        :param str path: The path to use for locking
        :return: A `FileLock` backend for obtaining locks
        :rtype: SwiftFileLock
        """
        if path is None:
            path = str(self.mirror_base_path / ".lock")
        return SwiftFileLock(path, backend=self)

    def _test_connection(self) -> None:
        with self.connection() as conn:
            try:
                resp_headers, containers = conn.get_account()
            except keystoneauth1.exceptions.catalog.EndpointNotFound as exc:
                logger.exception("Failed authenticating to swift.", exc_info=exc)
            else:
                logger.info(
                    "Validated swift credentials, successfully connected to swift!"
                )
        return

    def _get_session(self) -> keystoneauth1.session.Session:
        return keystoneauth1.session.Session(auth=self.auth)

    @property
    def default_container(self) -> str:
        try:
            return self.configuration["swift"]["default_container"]
        except KeyError:
            return "bandersnatch"

    @contextlib.contextmanager
    def connection(self) -> Generator[swiftclient.client.Connection, None, None]:
        with contextlib.closing(
            swiftclient.client.Connection(
                session=self._get_session(), os_options=self.os_options
            )
        ) as swift_conn:
            yield swift_conn

    def get_container(self, container: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Given the name of a container, return its contents.

        :param str container: The name of the desired container, defaults to
            :attr:`~SwiftStorage.default_container`
        :return: A list of objects in the container if it exists
        :rtype: List[Dict[str, str]]

        Example:

        >>> plugin.get_container("bandersnatch")
        [{
            'bytes': 1101, 'last_modified': '2020-02-27T19:10:17.922970',
            'hash': 'a76b4c69bfcf82313bbdc0393b04438a',
            'name': 'packages/pyyaml/PyYAML-5.3/LICENSE',
            'content_type': 'application/octet-stream'
         }, {
            'bytes': 1779, 'last_modified': '2020-02-27T19:10:17.845520',
            'hash': 'c60081e1ad65830b098a7f21a8a8c90e',
            'name': 'packages/pyyaml/PyYAML-5.3/PKG-INFO',
            'content_type': 'application/octet-stream'
         }, {
            'bytes': 1548, 'last_modified': '2020-02-27T19:10:17.730490',
            'hash': '9a8bdf19e93d4b007598b5eb97b461eb',
            'name': 'packages/pyyaml/PyYAML-5.3/README',
            'content_type': 'application/octet-stream'
         }, ...
        ]
        """
        if not container:
            container = self.default_container
        with self.connection() as conn:
            return conn.get_container(container)  # type: ignore

    def get_object(self, container_name: str, file_path: str) -> bytes:
        """Retrieve an object from swift, base64 decoding the contents."""
        with self.connection() as conn:
            try:
                _, file_contents = conn.get_object(container_name, file_path)
            except swiftclient.exceptions.ClientException:
                raise FileNotFoundError(file_path)
            else:
                if len(file_contents) % 4 == 0 and BASE64_RE.fullmatch(file_contents):
                    return base64.b64decode(file_contents)
                return bytes(file_contents)

    def walk(
        self,
        root: PATH_TYPES,
        dirs: bool = True,
        conn: Optional[swiftclient.client.Connection] = None,
    ) -> List[SwiftPath]:
        results: List[SwiftPath] = []

        with contextlib.ExitStack() as stack:
            if conn is None:
                conn = stack.enter_context(self.connection())
            paths = conn.get_container(self.default_container, prefix=str(root))
            for p in paths:
                if "subdir" in p and dirs:
                    results.append(self.PATH_BACKEND(p["subdir"]))
                else:
                    results.append(self.PATH_BACKEND(p["name"]))
        return results

    def find(self, root: PATH_TYPES, dirs: bool = True) -> str:
        """A test helper simulating 'find'.

        Iterates over directories and filenames, given as relative paths to the
        root.

        """
        results = self.walk(root, dirs=dirs)
        results.sort()
        return "\n".join(str(result.relative_to(root)) for result in results)

    def compare_files(self, file1: PATH_TYPES, file2: PATH_TYPES) -> bool:
        """Compare two files, returning true if they are the same and False if not."""
        file1_contents = self.read_file(file1, text=False)
        file2_contents = self.read_file(file2, text=False)
        assert isinstance(file1_contents, bytes)
        assert isinstance(file2_contents, bytes)
        file1_hash = hashlib.sha256(file1_contents).hexdigest()
        file2_hash = hashlib.sha256(file2_contents).hexdigest()
        return file1_hash == file2_hash

    @contextlib.contextmanager
    def rewrite(
        self, filepath: PATH_TYPES, mode: str = "w", **kw: Any
    ) -> Generator[IO, None, None]:
        """Rewrite an existing file atomically to avoid programs running in
        parallel to have race conditions while reading."""
        # TODO: Account for alternative backends
        if isinstance(filepath, str):
            filename = os.path.basename(filepath)
        else:
            filename = filepath.name
        # Change naming format to be more friendly with distributed POSIX
        # filesystems like GlusterFS that hash based on filename
        # GlusterFS ignore '.' at the start of filenames and this avoid rehashing
        with tempfile.NamedTemporaryFile(
            mode=mode, prefix=f".{filename}.", delete=False, **kw
        ) as f:
            filepath_tmp = f.name
            yield f

        if not os.path.exists(filepath_tmp):
            # Allow our clients to remove the file in case it doesn't want it to be
            # put in place actually but also doesn't want to error out.
            return
        os.chmod(filepath_tmp, 0o100644)
        shutil.move(filepath_tmp, filepath)

    @contextlib.contextmanager
    def update_safe(self, filename: PATH_TYPES, **kw: Any) -> Generator[IO, None, None]:
        """Rewrite a file atomically.

        Clients are allowed to delete the tmpfile to signal that they don't
        want to have it updated.
        """
        with tempfile.NamedTemporaryFile(
            delete=False,
            prefix=f"{os.path.basename(filename)}.",
            **kw,
        ) as tf:
            tf.has_changed = False  # type: ignore
            yield tf
            if not os.path.exists(tf.name):
                return
            local_filename_tmp = pathlib.Path(tf.name)
            filename_tmp = SwiftPath(f"{os.path.dirname(filename)}/{tf.name}")
        self.copy_local_file(str(local_filename_tmp), str(filename_tmp))
        local_filename_tmp.unlink()
        if self.exists(filename) and self.compare_files(
            str(filename_tmp), str(filename)
        ):
            self.delete_file(filename_tmp)
        else:
            self.move_file(filename_tmp, filename)
            tf.has_changed = True  # type: ignore

    def copy_local_file(self, source: PATH_TYPES, dest: PATH_TYPES) -> None:
        """Copy the contents of a local file to a destination in swift"""
        with open(source, "rb") as fh:
            self.write_file(str(dest), fh.read())
        return

    def copy_file(
        self, source: PATH_TYPES, dest: PATH_TYPES, dest_container: Optional[str] = None
    ) -> None:
        """Copy a file from **source** to **dest**"""
        if dest_container is None:
            dest_container = self.default_container
        dest = f"{dest_container}/{dest}"
        with self.connection() as conn:
            conn.copy_object(self.default_container, str(source), dest)
        return

    def move_file(
        self, source: PATH_TYPES, dest: PATH_TYPES, dest_container: Optional[str] = None
    ) -> None:
        """Move a file from **source** to **dest**"""
        if dest_container is None:
            dest_container = self.default_container
        dest = f"{dest_container}/{dest}"
        with self.connection() as conn:
            conn.copy_object(self.default_container, str(source), dest)
            try:
                conn.delete_object(self.default_container, str(source))
            except swiftclient.exceptions.ClientException:
                raise FileNotFoundError(str(source))
        return

    def write_file(
        self,
        path: PATH_TYPES,
        contents: Union[str, bytes, IO],
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
    ) -> None:
        """Write data to the provided path.  If **contents** is a string, the file will
        be opened and written in "r" + "utf-8" mode, if bytes are supplied it will be
        accessed using "rb" mode (i.e. binary write)."""
        if encoding is not None:
            if errors is None:
                try:
                    errors = sys.getfilesystemencodeerrors()
                except AttributeError:
                    errors = "surrogateescape"
            if isinstance(contents, str):
                contents = contents.encode(encoding=encoding, errors=errors)
            elif isinstance(contents, bytes):
                contents = contents.decode(encoding=encoding, errors=errors)
        with self.connection() as conn:
            conn.put_object(self.default_container, str(path), contents)
        return

    @contextlib.contextmanager
    def open_file(
        self, path: PATH_TYPES, text: bool = True
    ) -> Generator[IO, None, None]:
        """Yield a file context to iterate over. If text is false, open the file with
        'rb' mode specified."""
        wrapper = io.StringIO if text else io.BytesIO
        content: IO = wrapper(self.read_file(path, text=text))
        yield content

    def read_file(
        self,
        path: PATH_TYPES,
        text: bool = True,
        encoding: str = "utf-8",
        errors: Optional[str] = None,
    ) -> Union[str, bytes]:
        """Return the contents of the requested file, either a a bytestring or a unicode
        string depending on whether **text** is True"""
        content: Union[str, bytes]
        if not errors:
            try:
                errors = sys.getfilesystemencodeerrors()
            except AttributeError:
                errors = "surrogateescape"
        kwargs: Dict[str, Any] = {}
        if errors:
            kwargs["errors"] = errors
        content = self.get_object(self.default_container, str(path))
        if text and isinstance(content, bytes):
            content = content.decode(encoding=encoding, **kwargs)
        return content

    def delete_file(self, path: PATH_TYPES, dry_run: bool = False) -> int:
        """Delete the provided path, recursively if necessary."""
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        log_prefix = "[DRY RUN] " if dry_run else ""
        with self.connection() as conn:
            logger.info(f"{log_prefix}Deleting item from object storage: {path}")
            if not dry_run:
                try:
                    conn.delete_object(self.default_container, path.as_posix())
                except swiftclient.exceptions.ClientException:
                    raise FileNotFoundError(path.as_posix())
        return 0

    def mkdir(
        self, path: PATH_TYPES, exist_ok: bool = False, parents: bool = False
    ) -> None:
        """
        Create the provided directory

        This operation is a no-op on swift.
        """
        logger.warning(
            f"Creating directory in object storage: {path} with .swiftkeep file"
        )
        if not isinstance(path, self.PATH_BACKEND):
            path = self.PATH_BACKEND(path)
        path.joinpath(".swiftkeep").touch()

    def rmdir(
        self,
        path: PATH_TYPES,
        recurse: bool = False,
        force: bool = False,
        ignore_errors: bool = False,
        dry_run: bool = False,
    ) -> int:
        """
        Remove the directory. If recurse is True, allow removing empty children.

        If force is true, remove contents destructively.
        """
        if not force:
            if not isinstance(path, self.PATH_BACKEND):
                path = self.PATH_BACKEND(path)
            contents = list(path.iterdir(include_swiftkeep=True, recurse=True))
            if contents and all(p.name == ".swiftkeep" for p in contents):
                for p in contents:
                    if p.name == ".swiftkeep":
                        p.unlink()
            raise OSError(
                "Object container directories are auto-destroyed when they are emptied"
            )
        target_path = str(path)
        if target_path == ".":
            target_path = ""
        log_prefix = "[DRY RUN] " if dry_run else ""
        with self.connection() as conn:
            for item in self.walk(root=target_path):
                logger.info(f"{log_prefix}Deleting item from object storage: {item}")
                if not dry_run:
                    conn.delete_object(self.default_container, str(item))
        return 0

    def exists(self, path: PATH_TYPES) -> bool:
        """Check whether the provided path exists"""
        if not isinstance(path, SwiftPath):
            path = SwiftPath(str(path))
        target_path = str(path)
        if target_path == ".":
            target_path = ""
        return any([self.is_dir(path), self.is_file(path)])

    def is_dir(self, path: PATH_TYPES) -> bool:
        """Check whether the provided path is a directory."""
        if not isinstance(path, SwiftPath):
            path = SwiftPath(str(path))
        target_path = str(path)
        if target_path == ".":
            target_path = ""
        if target_path and not target_path.endswith("/"):
            target_path = f"{target_path}/"
        files: List[str] = []
        with self.connection() as conn:
            try:
                files = conn.get_container(self.default_container, prefix=target_path)
            except swiftclient.exceptions.ClientException:
                return False
            return bool(files)

    def is_file(self, path: PATH_TYPES) -> bool:
        """Check whether the provided path is a file."""
        if not isinstance(path, SwiftPath):
            path = SwiftPath(path)
        target_path = str(path)
        if target_path == ".":
            return False
        with self.connection() as conn:
            try:
                conn.head_object(self.default_container, target_path)
            except swiftclient.exceptions.ClientException:
                return False
            else:
                return True

    def is_symlink(self, path: PATH_TYPES) -> bool:
        """Check whether the provided path is a symlink"""
        with self.connection() as conn:
            try:
                headers = conn.head_object(
                    self.default_container, str(path), query_string="symlink=get"
                )
            except swiftclient.exceptions.ClientException:
                return False
            if headers:
                return bool(headers.get("content-type", "") == "application/symlink")
        return False

    def update_timestamp(self, path: PATH_TYPES) -> None:
        with self.connection() as conn:
            conn.post_object(
                self.default_container,
                str(path),
                {"x-timestamp": str(datetime.datetime.now().timestamp())},
            )

    def get_hash(self, path: PATH_TYPES, function: str = "sha256") -> str:
        h = getattr(hashlib, function)(self.read_file(path, text=False))
        return str(h.hexdigest())

    def symlink(
        self,
        src: PATH_TYPES,
        dest: PATH_TYPES,
        src_container: Optional[str] = None,
        src_account: Optional[str] = None,
    ) -> None:
        with self.connection() as conn:
            if src_container is None:
                src_container = self.default_container
            src_path = str(src)
            if not src_path.lstrip("/").startswith(src_container):
                src_path = f"{src_container}/{src_path.lstrip('/')}"
            headers = {
                "X-Symlink-Target": src_path,
            }
            if src_account is not None:
                headers["X-Symlink-Target-Account"] = src_account
            conn.put_object(
                self.default_container,
                str(dest),
                b"",
                content_length=0,
                content_type="application/symlink",
                headers=headers,
            )

    def get_file_size(self, path: PATH_TYPES) -> int:
        with self.connection() as conn:
            headers = conn.head_object(
                self.default_container,
                str(path),
            )
            return int(headers.get("content-length", "0"))

    def get_upload_time(self, path: PATH_TYPES) -> datetime.datetime:
        with self.connection() as conn:
            headers = conn.head_object(
                self.default_container,
                str(path),
            )
            ts = int(headers.get("x-object-meta-upload", "0"))
            return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)

    def set_upload_time(self, path: PATH_TYPES, time: datetime.datetime) -> None:
        """Set the upload time of a given **path**"""
        with self.connection() as conn:
            conn.post_object(
                self.default_container,
                str(path),
                {"x-object-meta-upload": str(time.timestamp())},
            )
