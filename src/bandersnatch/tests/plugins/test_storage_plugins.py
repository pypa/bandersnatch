import atexit
import contextlib
import datetime
import hashlib
import json
import mimetypes
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest import TestCase, mock

import bandersnatch.storage
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.storage import PATH_TYPES
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_storage_plugins import filesystem, swift

if TYPE_CHECKING:
    import swiftclient


BASE_SAMPLE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample"
)
SWIFT_CONTAINER_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "swift_container.json"
)


def get_swift_file_attrs(path: Path, base: Path, container: str = "") -> dict[str, Any]:
    path = strip_dir_prefix(base, path, container=container)
    if not path.is_absolute():
        path = "/" / path
    try:
        last_modified = get_swift_date(
            datetime.datetime.fromtimestamp(path.stat().st_mtime)
        )
    except Exception:
        print(list(path.parent.iterdir()), file=sys.stderr)
    data = path.read_bytes()
    posix_format = path.as_posix().lstrip("/")
    name_start = 0
    posix_base = base.as_posix()
    if posix_base in posix_format:
        name_start = posix_format.index(posix_base) + len(posix_base)
    name = posix_format[name_start:]
    mimetype, encoding = mimetypes.guess_type(posix_format)
    if mimetype is None:
        mimetype = "application/octet-stream"
    if encoding is not None:
        mimetype = f"{mimetype}; encoding={encoding}"
    result_dict = {
        "bytes": len(data),
        "hash": hashlib.md5(data).hexdigest(),
        "name": str(Path(name.lstrip("/"))),
        "content_type": mimetype,
        "last_modified": last_modified,
    }
    if path.is_symlink():
        result_dict["symlink_path"] = str(os.readlink(path))
    return result_dict


def strip_dir_prefix(
    base_dir: Path, subdir: Path, container: str | None = None
) -> Path:
    if container is not None:
        base_dir = base_dir.joinpath(container)
    base_dir_prefix = base_dir.as_posix()[1:]
    result = subdir.as_posix()
    if result.startswith(base_dir_prefix):
        return type(base_dir)(result[len(base_dir_prefix) :].lstrip("/"))  # noqa:E203
    return type(base_dir)(result.lstrip("/"))


def iter_dir(
    path: Path, base: Path | None = None, recurse: bool = False, container: str = ""
) -> Iterator[dict[str, Any]]:
    if base is None:
        base = path
    if path.is_dir():
        for sub_path in path.iterdir():
            if sub_path.is_dir():
                subdir_path = strip_dir_prefix(base, sub_path, container=container)
                yield {"subdir": subdir_path, "container": container}
                if recurse:
                    yield from iter_dir(
                        sub_path, base, recurse=recurse, container=container
                    )
            else:
                yield get_swift_file_attrs(sub_path, base, container=container)
    else:
        yield get_swift_file_attrs(path, base, container=container)


def get_swift_object_date(date: datetime.datetime) -> str:
    return (
        date.astimezone(datetime.timezone.utc)
        .strftime("%a, %d %b %Y %H:%M:%S %Z")
        .replace("UTC", "GMT")
    )


def get_swift_date(date: datetime.datetime) -> str:
    return date.astimezone(datetime.timezone.utc).isoformat()


class MockConnection:
    """
    Compatible class to provide local files over the swift interface.

    This is used to mock out the swift interface for testing against the
    storage plugin system.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.tmpdir = kwargs.pop("tmpdir", None)
        if not self.tmpdir:
            self.tmpdir = tempfile.TemporaryDirectory()
            atexit.register(self.tmpdir.cleanup)
        self.base = pathlib.Path(self.tmpdir.name)
        self.container_path = self.base / "bandersnatch"
        self.container_path.mkdir(exist_ok=True)
        _conn_mock = mock.MagicMock("swiftclient.client.Connection", autospec=True)
        _connection = _conn_mock()
        _connection.get_account.return_value = ("", "")
        self._connection = _connection

    def __getattr__(self, key: str) -> Any:
        try:
            return self.__getattribute__(key)
        except AttributeError:
            return self.__getattribute__("_connection").getattr(key)

    def clean_path(self, container: PATH_TYPES, obj: PATH_TYPES) -> Path:
        base_prefix = f"{self.tmpdir.name}/{container}"
        if isinstance(obj, str):
            obj = Path(obj)
        if not any(
            str(obj).startswith(prefix) for prefix in (base_prefix, base_prefix[1:])
        ):
            obj = Path(f"{base_prefix}/{obj!s}")
        if not obj.anchor:
            obj = Path(f"/{obj!s}")
        return obj

    def _strip_prefix(self, prefix: str, container: str | None = None) -> str:
        base_dir_prefix = self.tmpdir.name[1:]
        if container is not None:
            base_dir_prefix = os.path.join(base_dir_prefix, container)
        if prefix.startswith(base_dir_prefix):
            return prefix[len(base_dir_prefix) :].lstrip("/")  # noqa:E203
        return prefix.lstrip("/")

    def get_account(self) -> tuple[dict[Any, Any], dict[Any, Any]]:
        return {}, {}

    def get_object(self, container: str, obj: str) -> tuple[dict[Any, Any], bytes]:
        path = self.clean_path(container, obj)
        if not path.exists():
            from swiftclient.exceptions import ClientException

            raise ClientException(f"No such path: {path!s}")
        return {}, path.read_bytes()

    def head_object(
        self,
        container: str,
        obj: str,
        headers: dict[str, str] | None = None,
        query_string: str | None = None,
    ) -> dict[str, str]:
        path = self.clean_path(container, obj)
        if not path.exists():
            from swiftclient.exceptions import ClientException

            raise ClientException(f"No such path: {path!s}")
        try:
            max_date = max(path.stat().st_mtime, path.stat().st_ctime)
            current_timestamp = get_swift_object_date(datetime.datetime.now())
            path_contents = path.read_bytes()
        except Exception:
            from swiftclient.exceptions import ClientException

            raise ClientException(f"Not a file: {path!s}")
        name = path.as_posix()
        mimetype, encoding = mimetypes.guess_type(name)
        if mimetype is None:
            mimetype = "application/octet-stream"
        if encoding is not None:
            mimetype = f"{mimetype}; encoding={encoding}"
        return {
            "date": current_timestamp,
            "server": "Apache/2.4.29 (Ubuntu)",
            "content-length": f"{len(path_contents)}",
            "accept-ranges": "bytes",
            "last-modified": f"{path.stat().st_mtime}",
            "etag": hashlib.md5(path_contents).hexdigest(),
            "x-timestamp": f"{max_date}",
            "content-type": mimetype,
            "x-trans-id": "txfcbf2e82791411eaa6bd-cf51efeb8527",
            "x-openstack-request-id": "txfcbf2e82791411eaa6bd-cf51efeb8527",
        }

    def post_object(
        self,
        container: str,
        obj: str,
        headers: dict[str, str],
        response_dict: dict[str, Any] | None = None,
    ) -> None:
        path = self.clean_path(container, obj)
        path.touch()

    def _get_container(
        self,
        container: str,
        marker: str | None = None,
        limit: int | None = None,
        prefix: str | None = None,
        delimiter: str | None = None,
        end_marker: str | None = None,
        path: Path | None = None,
        full_listing: bool = False,
        headers: dict[str, str] | None = None,
        query_string: str | None = None,
    ) -> list[dict[str, Any]]:
        base = self.base
        if container:
            base = base / container
        if prefix:
            base = self.clean_path(container, prefix)
        if not base.is_dir():
            return []
        if delimiter:
            files = iter_dir(base, base=None, recurse=False, container=container)
        else:
            files = iter_dir(base, base=None, recurse=True, container=container)
        return list(files)

    def get_container(
        self,
        container: str,
        marker: str | None = None,
        limit: int | None = None,
        prefix: str | None = None,
        delimiter: str | None = None,
        end_marker: str | None = None,
        path: Path | None = None,
        full_listing: bool = False,
        headers: dict[str, str] | None = None,
        query_string: str | None = None,
    ) -> list[dict[str, Any]]:
        with open(SWIFT_CONTAINER_FILE) as fh:
            contents = json.load(fh)
        if prefix:
            contents = [p for p in contents if p["name"].startswith(prefix)]
        results = self._get_container(
            container, limit=limit, prefix=prefix, delimiter=delimiter
        )
        if delimiter:
            subdirs = set()
            prefix = "" if not prefix else prefix
            prefix_delims = prefix.count(delimiter)
            for entry in contents:
                split_entry = entry["name"].split(delimiter)
                if len(split_entry[prefix_delims:]) > 1:
                    subdirs.add(delimiter.join(split_entry[: prefix_delims + 1]))
                else:
                    results.append(entry)
            for subdir in subdirs:
                results.append({"subdir": subdir})
        else:
            results.extend(contents)
        if limit:
            results = results[:limit]
        return results

    def copy_object(
        self,
        container: str,
        obj: str,
        destination: str,
        headers: dict[str, str] | None = None,
        fresh_metadata: Any = None,
        response_dict: dict[str, Any] | None = None,
    ) -> None:
        # destination path always starts with container/
        dest_container, _, dest_path = destination.partition("/")
        dest = self.clean_path(dest_container, dest_path)
        base = self.clean_path(container, obj)
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True)
        dest.write_bytes(base.read_bytes())

    def put_object(
        self,
        container: str,
        obj: str,
        contents: str | bytes,
        content_length: int | None = None,
        etag: Any = None,
        chunk_size: int | None = None,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
        query_string: str | None = None,
        response_dict: dict[str, Any] | None = None,
    ) -> None:
        dest = self.clean_path(container, obj)
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True)
        if headers and "X-Symlink-Target" in headers:
            src_container, _, src_path = headers["X-Symlink-Target"].partition("/")
            src = self.clean_path(src_container, src_path)
            if os.name != "nt":
                os.symlink(str(src), str(dest))
            else:
                shutil.copyfile(str(src), str(dest))
            return None
        if isinstance(contents, bytes):
            dest.write_bytes(contents)
        else:
            dest.write_text(contents)

    def delete_object(
        self,
        container: str,
        obj: str,
        query_string: str | None = None,
        response_dict: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        target = self.clean_path(container, obj)
        if not target.exists():
            from swiftclient.exceptions import ClientException

            raise ClientException(f"File does not exist: {target!s}")
        target.unlink()
        if not list(target.parent.iterdir()):
            target.parent.rmdir()


class BasePluginTestCase(TestCase):
    tempdir = None
    cwd = None
    backend: str | None = None

    config_contents = """\
[mirror]
directory = srv/pypi
storage-backend = {0}
master = https://pypi.org
json = false
timeout = 10
global-timeout = 18000
verifiers = 3
diff-file = {{mirror_directory}}/mirrored-files
diff-append-epoch = false
stop-on-error = false
hash-index = false
workers = 3
; keep_index_versions = 0
; log-config = /etc/bandersnatch-log.conf
"""

    def setUp(self) -> None:
        if self.backend is None:
            raise unittest.SkipTest("Skipping base test case")
        self.cwd = os.getcwd()
        self.tempdir = tempfile.TemporaryDirectory()
        self.pkgs: list[Package] = []
        self.container: str | None = None
        self.config_data = mock_config(self.config_contents.format(self.backend))
        os.chdir(self.tempdir.name)
        self.setUp_backEnd()
        self.setUp_plugin()
        self.setUp_mirror()
        self.setUp_Structure()

    def setUp_dirs(self) -> None:
        self.web_base_path = os.path.join(self.mirror_base_path, "web")
        self.json_base_path = os.path.join(self.web_base_path, "json")
        self.pypi_base_path = os.path.join(self.web_base_path, "pypi")
        self.simple_base_path = os.path.join(self.web_base_path, "simple")
        paths = (self.json_base_path, self.pypi_base_path, self.simple_base_path)
        for path in paths:
            os.makedirs(path, exist_ok=True)

    def setUp_backEnd(self) -> None:
        pypi_dir = mirror_path = "srv/pypi"
        if self.backend == "swift":
            self.container = "bandersnatch"
            pypi_dir = f"{self.container}/{pypi_dir}"
            self.setUp_swift()
        assert self.tempdir
        self.mirror_base_path = os.path.join(self.tempdir.name, pypi_dir)
        self.setUp_dirs()
        target_sample_file = "sample"
        if self.container is not None:
            target_sample_file = f"{self.container}/{target_sample_file}"
        assert self.tempdir
        self.sample_file = os.path.join(self.tempdir.name, target_sample_file)
        shutil.copy(BASE_SAMPLE_FILE, self.sample_file)
        if self.backend == "swift":
            self.mirror_path = Path(mirror_path)
        else:
            self.mirror_path = Path(self.mirror_base_path)

    def setUp_mirror(self) -> None:
        self.master = Master(url="https://foo.bar.com")
        self.mirror = BandersnatchMirror(self.mirror_path, self.master, self.backend)
        pkg = Package("foobar", serial=1)
        pkg._metadata = {
            "info": {"name": "foobar", "version": "1.0"},
            "releases": mock.Mock(),
        }
        self.pkgs.append(pkg)

    def setUp_plugin(self) -> None:
        self.plugin = next(
            iter(
                bandersnatch.storage.storage_backend_plugins(
                    self.backend, clear_cache=True
                )
            )
        )

    def setUp_mirrorDirs(self) -> None:
        pypi_dir = (
            "srv/pypi" if self.container is None else f"{self.container}/srv/pypi"
        )
        assert self.tempdir
        self.mirror_base_path = os.path.join(self.tempdir.name, pypi_dir)
        self.web_base_path = os.path.join(self.mirror_base_path, "web")
        self.json_base_path = os.path.join(self.web_base_path, "json")
        self.pypi_base_path = os.path.join(self.web_base_path, "pypi")
        self.simple_base_path = os.path.join(self.web_base_path, "simple")
        os.makedirs(self.json_base_path, exist_ok=True)
        os.makedirs(self.pypi_base_path, exist_ok=True)
        os.makedirs(self.simple_base_path, exist_ok=True)

    def setUp_swift(self) -> None:
        self.setUp_swiftVars()
        self.conn_patcher = mock.patch(
            "swiftclient.client.Connection", side_effect=MockConnection
        )
        Connection = self.conn_patcher.start()
        Connection.get_account.return_value = ("", "")

        from bandersnatch_storage_plugins.swift import SwiftStorage

        @contextlib.contextmanager
        def connection(o: SwiftStorage) -> Iterator["swiftclient.client.Connection"]:
            yield Connection(tmpdir=self.tempdir)

        def is_dir(self: SwiftStorage, path: Path) -> bool:
            """Check whether the provided path is a directory."""
            target_path = str(path)
            if target_path == ".":
                target_path = ""
            if target_path and not target_path.endswith("/"):
                target_path = f"{target_path}/"
            files = []
            with self.connection() as conn:
                try:
                    files = conn.get_container(
                        self.default_container, prefix=target_path
                    )
                except OSError:
                    return False
                return bool(files)

        self.swift_patcher = mock.patch.object(SwiftStorage, "connection", connection)
        self.is_dir_patcher = mock.patch(
            "bandersnatch_storage_plugins.swift.SwiftStorage.is_dir", is_dir
        )
        self.swift_patcher.start()
        self.is_dir_patcher.start()

    def setUp_swiftVars(self) -> None:
        swift_keys = (
            "OS_USER_DOMAIN_NAME",
            "OS_PROJECT_DOMAIN_NAME",
            "OS_PASSWORD",
            "OS_USER_ID",
            "OS_USERNAME",
            "OS_PROJECT_NAME",
            "OS_TENANT_NAME",
            "OS_AUTH_URL",
            "OS_AUTHENTICATION_URL",
            "OS_STORAGE_URL",
            "OS_REGION_NAME",
            "OS_PROJECT_ID",
        )
        self.original_swiftvars = {
            k: os.environ[k] for k in swift_keys if k in os.environ
        }
        self.os_dict = {
            "OS_USER_DOMAIN_NAME": "default",
            "OS_PROJECT_DOMAIN_NAME": "default",
            "OS_PASSWORD": "test123",
            "OS_USER_ID": "test_userid",
            "OS_PROJECT_NAME": "test_project",
            "OS_AUTH_URL": "https://keystone.localhost:5000/v3",
            "OS_STORAGE_URL": "https://swift-proxy.localhost:8080/v1/AUTH_test_project",
            "OS_REGION_NAME": "test_region",
        }
        os.environ.update(self.os_dict)

    def tearDown_swiftVars(self) -> None:
        for k in self.os_dict.keys():
            if k in os.environ:
                del os.environ[k]
        os.environ.update(self.original_swiftvars)
        self.is_dir_patcher
        self.swift_patcher.stop()
        self.conn_patcher.stop()

    def setUp_Structure(self) -> None:
        web_files = [
            "last-modified",
            "local-stats/days",
            "packages/2.7/f/foo/foo.whl",
            "packages/3.8/f/foo/foo.whl",
            "packages/any/f/foo/foo.zip",
            "simple/foobar/index.html",
            "simple/index.html",
        ]
        for path in web_files:
            p = pathlib.Path(self.web_base_path) / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        paths = ["generation", "sample", "status"]
        for path in paths:
            p = pathlib.Path(self.mirror_base_path) / path
            p.touch()
        pathlib.Path(self.mirror_base_path).joinpath("status").write_text("20")
        pathlib.Path(self.web_base_path).joinpath("simple/index.html").write_text(
            """<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foobar/">foobar</a><br/>
  </body>
</html>""".strip()
        )

    def tearDown(self) -> None:
        if self.tempdir:
            assert self.cwd
            os.chdir(self.cwd)
            self.tempdir.cleanup()
        if self.backend == "swift":
            self.tearDown_swiftVars()


class BaseStoragePluginTestCase(BasePluginTestCase):
    plugin_map = {
        "filesystem": filesystem.FilesystemStorage,
        "swift": swift.SwiftStorage,
    }
    path_backends = {
        "filesystem": pathlib.Path,
        "swift": swift.SwiftPath,
    }

    base_find_contents = r"""
.lock
generation
sample
status
web
web{0}json
web{0}last-modified
web{0}local-stats
web{0}local-stats{0}days
web{0}local-stats{0}days{0}.swiftkeep
web{0}packages
web{0}packages{0}2.7
web{0}packages{0}2.7{0}f
web{0}packages{0}2.7{0}f{0}foo
web{0}packages{0}2.7{0}f{0}foo{0}foo.whl
web{0}packages{0}3.8
web{0}packages{0}3.8{0}f
web{0}packages{0}3.8{0}f{0}foo
web{0}packages{0}3.8{0}f{0}foo{0}foo.whl
web{0}packages{0}any
web{0}packages{0}any{0}f
web{0}packages{0}any{0}f{0}foo
web{0}packages{0}any{0}f{0}foo{0}foo.zip
web{0}pypi
web{0}simple
web{0}simple{0}foobar
web{0}simple{0}foobar{0}index.html
web{0}simple{0}index.html""".format(
        os.sep
    ).strip()
    if sys.platform == "win32":
        base_find_contents = base_find_contents.replace(".lock\n", "")

    def test_plugin_type(self) -> None:
        assert self.backend
        self.assertTrue(isinstance(self.plugin, self.plugin_map[self.backend]))
        self.assertTrue(self.plugin.PATH_BACKEND is self.path_backends[self.backend])

    def test_json_paths(self) -> None:
        config = mock_config(self.config_contents).config
        mirror_dir = self.plugin.PATH_BACKEND(config.get("mirror", "directory"))
        packages = {
            "bandersnatch": [
                mirror_dir / "web/json/bandersnatch",
                mirror_dir / "web/pypi/bandersnatch",
            ],
            "black": [mirror_dir / "web/json/black", mirror_dir / "web/pypi/black"],
        }
        for name, json_paths in packages.items():
            with self.subTest(name=name, json_paths=json_paths):
                self.assertEqual(self.plugin.get_json_paths(name), json_paths)

    def test_canonicalize_package(self) -> None:
        packages = (
            ("SQLAlchemy", "sqlalchemy"),
            ("mypy_extensions", "mypy-extensions"),
            ("py_ecc", "py-ecc"),
            ("Requests", "requests"),
            ("oslo.utils", "oslo-utils"),
        )
        for name, normalized in packages:
            with self.subTest(name=name, normalized=normalized):
                self.assertEqual(self.plugin.canonicalize_package(name), normalized)

    def test_hash_file(self) -> None:
        path = self.plugin.PATH_BACKEND(self.sample_file)
        md5_digest = "125765989403df246cecb48fa3e87ff8"
        sha256_digest = (
            "95c07c174663ebff531eed59b326ebb3fa95f418f680349fc33b07dfbcf29f18"
        )
        # newlines make the hash different here
        if sys.platform == "win32":
            md5_digest = "91ef8f60d130b312af17543b34bfb372"
            sha256_digest = (
                "398e162e08d9af1d87c8eb2ee46d7c64248867afbe30dee807122022dc497332"
            )
        expected_hashes = (
            ("md5", md5_digest),
            ("sha256", sha256_digest),
        )
        for hash_func, hash_val in expected_hashes:
            with self.subTest(hash_func=hash_func, hash_val=hash_val):
                self.assertEqual(
                    self.plugin.hash_file(path, function=hash_func), hash_val
                )

    def test_iter_dir(self) -> None:
        base_path = self.plugin.PATH_BACKEND(self.simple_base_path)
        lists = [
            (base_path.joinpath("foobar"), True),
            (base_path.joinpath("index.html"), False),
        ]

        self.assertListEqual(
            list(sorted(base_path.iterdir(), key=lambda p: str(p))),
            list(sorted((elem[0] for elem in lists), key=lambda p: str(p))),
        )
        for expected, is_dir in lists:
            with self.subTest(is_dir=is_dir, produced_path=expected):
                self.assertIs(is_dir, self.plugin.is_dir(expected))
                if is_dir is False:
                    self.assertIs(True, self.plugin.is_file(expected))

    def test_rewrite(self) -> None:
        target_file = os.path.join(self.mirror_base_path, "example.txt")
        replace_with = "new text"
        with open(target_file, "w") as fh:
            fh.write("sample text")
        with self.plugin.rewrite(target_file) as fh:
            fh.write(replace_with)
        with open(target_file) as fh:
            self.assertEqual(fh.read().strip(), replace_with)

    def test_update_safe(self) -> None:
        target_file = os.path.join(self.mirror_base_path, "example.txt")
        replace_with = "new text"
        with open(target_file, "w") as fh:
            fh.write("sample text")
        with self.plugin.update_safe(target_file, mode="w") as fh:
            fh.write(replace_with)
        with open(target_file) as fh:
            self.assertEqual(fh.read().strip(), replace_with)

    def test_compare_files(self) -> None:
        target_file1 = os.path.join(self.mirror_base_path, "cmp_example1.txt")
        target_file2 = os.path.join(self.mirror_base_path, "cmp_example2.txt")
        target_file3 = os.path.join(self.mirror_base_path, "cmp_example3.txt")
        for fn in (target_file1, target_file2):
            with open(fn, "w") as fh:
                fh.write("sample text")
        with open(target_file3, "w") as fh:
            fh.write("some other text")
        files = [target_file1, target_file2, target_file3]
        comparisons = (
            (target_file1, target_file2, True),
            (target_file1, target_file3, False),
            (target_file2, target_file3, False),
        )
        for cmp_file1, cmp_file2, rv in comparisons:
            with self.subTest(cmp_file1=cmp_file1, cmp_file2=cmp_file2, rv=rv):
                msg = "file1 contents: {!r}\n\nfile2 contents: {!r}".format(
                    self.plugin.read_file(cmp_file1), self.plugin.read_file(cmp_file2)
                )
                self.assertTrue(
                    self.plugin.compare_files(cmp_file1, cmp_file2) is rv, msg
                )
        for fn in files:
            os.unlink(fn)

    def test_find(self) -> None:
        base_path = self.mirror_base_path

        # Clean up GitHub Actions environment on macOS tests
        if sys.platform == "darwin":
            env_garbage_path = os.path.join(self.mirror_base_path, "var")
            shutil.rmtree(env_garbage_path, ignore_errors=True)

        self.assertEqual(self.base_find_contents, self.plugin.find(base_path))

    def test_open_file(self) -> None:
        self.plugin.write_file(os.path.join(self.mirror_base_path, "status"), "20")
        rvs = (
            (
                os.path.join(self.web_base_path, "simple/index.html"),
                """\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foobar/">foobar</a><br/>
  </body>
</html>""",
            ),
            (os.path.join(self.mirror_base_path, "status"), "20"),
        )
        for path, rv in rvs:
            with self.subTest(path=path, rv=rv):
                with self.plugin.open_file(path, text=True) as fh:
                    self.assertEqual(fh.read(), rv)

    def test_write_file(self) -> None:
        data: list[str | bytes] = ["this is some text", b"this is some text"]
        tmp_path = os.path.join(self.mirror_base_path, "test_write_file.txt")
        for write_val in data:
            with self.subTest(write_val=write_val):
                self.plugin.write_file(tmp_path, write_val)
                rv: str | bytes
                if not isinstance(write_val, str):
                    rv = self.plugin.PATH_BACKEND(tmp_path).read_bytes()
                else:
                    rv = self.plugin.PATH_BACKEND(tmp_path).read_text()
                self.assertEqual(rv, write_val)
        os.unlink(tmp_path)

    def test_read_file(self) -> None:
        self.plugin.write_file(os.path.join(self.mirror_base_path, "status"), "20")
        rvs = (
            (
                self.plugin.PATH_BACKEND(self.web_base_path).joinpath(
                    "simple/index.html"
                ),
                """\
<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foobar/">foobar</a><br/>
  </body>
</html>""",
            ),
            (self.plugin.PATH_BACKEND(self.mirror_base_path).joinpath("status"), "20"),
        )
        for path, rv in rvs:
            with self.subTest(path=path, rv=rv):
                self.assertEqual(self.plugin.read_file(path), rv)

    def test_delete(self) -> None:
        delete_path = self.plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete.txt"
        )
        delete_dir = self.plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete_dir"
        )
        delete_dir.mkdir()
        delete_path.touch()
        for path in [delete_path, delete_dir]:
            with self.subTest(path=path):
                self.assertTrue(path.exists())
                self.plugin.delete(path)
                self.assertFalse(path.exists())

    def test_delete_file(self) -> None:
        delete_path = self.plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete.txt"
        )
        print(f"delete path: {delete_path!r}")
        delete_path.touch()
        self.assertTrue(delete_path.exists())
        self.plugin.delete_file(delete_path)
        self.assertFalse(delete_path.exists())

    def test_copy_file(self) -> None:
        file_content = "this is some data"
        dest_file = os.path.join(self.mirror_base_path, "temp_file.txt")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            atexit.register(os.unlink, tf.name)
            tf.write(file_content)
            tf.flush()
        self.plugin.copy_file(tf.name, dest_file)
        with open(dest_file) as fh:
            copied_content = fh.read()
        os.unlink(dest_file)
        self.assertEqual(copied_content, file_content)

    def test_mkdir(self) -> None:
        self.plugin.mkdir(os.path.join(self.mirror_base_path, "test_dir"))
        self.assertTrue(
            self.plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )
        self.plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir")
        ).rmdir()

    def test_scandir(self) -> None:
        test_dir = os.path.join(self.mirror_base_path, "test_dir")
        sub_dir = os.path.join(test_dir, "sub_dir")
        sub_file = os.path.join(test_dir, "sub_file")
        sub_link = os.path.join(test_dir, "sub_link")
        self.plugin.mkdir(test_dir)
        self.plugin.mkdir(sub_dir)
        self.plugin.write_file(sub_file, "test")
        self.plugin.symlink(sub_file, sub_link)
        for ent in self.plugin.scandir(test_dir):
            if ent.name == "sub_dir":
                assert ent.is_dir()
            elif ent.name == "sub_file":
                assert ent.is_file()
            elif ent.name == "sub_link":
                assert ent.is_symlink()
            else:
                raise ValueError(f"unexpected dir entry {str(ent.name)}")
        self.plugin.delete(sub_link)
        self.plugin.delete(sub_file)
        self.plugin.delete(sub_dir)
        self.plugin.delete(test_dir)

    def test_rmdir(self) -> None:
        self.plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir")
        ).mkdir()
        self.assertTrue(
            self.plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )
        self.plugin.rmdir(
            self.plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir"))
        )
        self.assertFalse(
            self.plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )

    def test_is_dir(self) -> None:
        self.plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir")
        ).mkdir()
        self.assertTrue(
            self.plugin.is_dir(
                self.plugin.PATH_BACKEND(
                    os.path.join(self.mirror_base_path, "test_dir")
                )
            )
        )
        self.plugin.rmdir(
            self.plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir")),
            force=True,
        )

    def test_is_file(self) -> None:
        delete_path = self.plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete.txt"
        )
        delete_path.touch()
        self.assertTrue(self.plugin.is_file(delete_path))
        delete_path.unlink()

    def test_symlink(self) -> None:
        file_content = "this is some text"
        test_path = self.plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "symlink_file.txt"
        )
        test_path.write_text(file_content)
        symlink_dest = test_path.parent.joinpath("symlink_dest.txt")
        self.plugin.symlink(test_path, symlink_dest)
        self.assertEqual(self.plugin.read_file(symlink_dest), file_content)

    def test_get_hash(self) -> None:
        path = self.plugin.PATH_BACKEND(self.sample_file)
        md5_digest = "125765989403df246cecb48fa3e87ff8"
        sha256_digest = (
            "95c07c174663ebff531eed59b326ebb3fa95f418f680349fc33b07dfbcf29f18"
        )
        # newlines make the hash different here
        if sys.platform == "win32":
            md5_digest = "91ef8f60d130b312af17543b34bfb372"
            sha256_digest = (
                "398e162e08d9af1d87c8eb2ee46d7c64248867afbe30dee807122022dc497332"
            )
        expected_hashes = (
            ("md5", md5_digest),
            ("sha256", sha256_digest),
        )
        for fn, hash_val in expected_hashes:
            with self.subTest(fn=fn, hash_val=hash_val):
                self.assertEqual(self.plugin.get_hash(path, function=fn), hash_val)


class TestFilesystemStoragePlugin(BaseStoragePluginTestCase):
    backend = "filesystem"
    base_find_contents = "\n".join(
        [
            line
            for line in BaseStoragePluginTestCase.base_find_contents.split("\n")
            if "web{0}local-stats{0}days{0}.swiftkeep".format(os.path.sep)
            != line.strip()
        ]
    )


class TestSwiftStoragePlugin(BaseStoragePluginTestCase):
    backend = "swift"
    base_find_contents = BaseStoragePluginTestCase.base_find_contents.replace(
        ".lock\n", ""
    ).strip()

    def setUp(self) -> None:
        if os.name == "nt":
            raise unittest.SkipTest("Skipping swift tests on windows")
        super().setUp()

    def test_mkdir(self) -> None:
        tmp_filename = next(tempfile._get_candidate_names())  # type: ignore
        tmp_file = self.plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir", tmp_filename)
        )
        tmp_file.write_text("")
        self.assertTrue(
            self.plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )
        tmp_file.unlink()

    def test_rmdir(self) -> None:
        tmp_filename = next(tempfile._get_candidate_names())  # type: ignore
        tmp_file = self.plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir", tmp_filename)
        )
        tmp_file.write_text("")
        self.assertTrue(
            self.plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )
        tmp_file.unlink()
        self.assertFalse(
            self.plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )

    def test_copy_file(self) -> None:
        file_content = "this is some data"
        dest_file = os.path.join(self.mirror_base_path, "temp_file.txt")
        assert self.tempdir
        with tempfile.NamedTemporaryFile(
            dir=os.path.join(self.tempdir.name, "bandersnatch"), mode="w"
        ) as tf:
            tf.write(file_content)
            tf.flush()
            self.plugin.copy_file(tf.name, dest_file)
        with open(dest_file) as fh:
            copied_content = fh.read()
        os.unlink(dest_file)
        self.assertEqual(copied_content, file_content)


if __name__ == "__main__":
    unittest.main()
