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
from collections import defaultdict
from typing import Any, Dict, Optional, Union
from unittest import TestCase, mock

import bandersnatch.storage
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package
from bandersnatch_storage_plugins import filesystem

BASE_SAMPLE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample"
)
SWIFT_CONTAINER_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "swift_container.json"
)


def get_swift_file_attrs(path, base, container=""):
    path = strip_dir_prefix(base, path, container=container)
    if not str(path).startswith("/"):
        path = type(path)(f"/{path!s}")
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
        "name": type(path)(name.lstrip("/")),
        "content_type": mimetype,
        "last_modified": last_modified,
    }
    return result_dict


def strip_dir_prefix(base_dir, subdir, container=None):
    if container is not None:
        base_dir = base_dir.joinpath(container)
    base_dir_prefix = base_dir.as_posix()[1:]
    result = subdir.as_posix()
    if result.startswith(base_dir_prefix):
        return type(base_dir)(result[len(base_dir_prefix) :].lstrip("/"))
    return type(base_dir)(result.lstrip("/"))


def iter_dir(path, base=None, recurse=False, container=""):
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


def get_swift_object_date(date):
    return (
        date.astimezone(datetime.timezone.utc)
        .strftime("%a, %d %b %Y %H:%M:%S %Z")
        .replace("UTC", "GMT")
    )


def get_swift_date(date):
    return date.astimezone(datetime.timezone.utc).isoformat()


class MockConnection:
    def __init__(self, *args, **kwargs):
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

    def __getattr__(self, key, *args, **kwargs):
        try:
            return self.__getattribute__(key, *args, **kwargs)
        except AttributeError:
            return self.__getattribute__("_connection").getattr(key, *args, **kwargs)

    def clean_path(self, container, obj):
        base_prefix = f"{self.tmpdir.name}/{container}"
        if isinstance(obj, str):
            obj = type(self.base)(obj)
        if not any(
            str(obj).startswith(prefix) for prefix in (base_prefix, base_prefix[1:])
        ):
            obj = type(obj)(f"{base_prefix}/{obj!s}")
        if not obj.anchor:
            obj = type(obj)(f"/{obj!s}")
        return obj

    def _strip_prefix(self, prefix, container=None):
        base_dir_prefix = self.tmpdir.name[1:]
        if container is not None:
            base_dir_prefix = os.path.join(base_dir_prefix, container)
        if prefix.startswith(base_dir_prefix):
            return prefix[len(base_dir_prefix) :].lstrip("/")
        return prefix.lstrip("/")

    def get_account(self):
        return {}, {}

    def get_object(self, container, obj):
        path = self.clean_path(container, obj)
        if not path.exists():
            from swiftclient.exceptions import ClientException

            raise ClientException(f"No such path: {path!s}")
        return {}, path.read_bytes()

    def head_object(self, container, obj, headers=None, query_string=None):
        path = self.clean_path(container, obj)
        if not path.exists():
            from swiftclient.exceptions import ClientException

            raise ClientException(f"No such path: {path!s}")
        try:
            max_date = max(path.stat().st_mtime, path.stat().st_ctime)
            current_timestamp = get_swift_object_date(datetime.datetime.now())
            date_field = get_swift_object_date(
                datetime.datetime.fromtimestamp(path.stat().st_mtime)
            )
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
            "content-length": "{}".format(len(path_contents)),
            "accept-ranges": "bytes",
            "last-modified": f"{path.stat().st_mtime}",
            "etag": hashlib.md5(path_contents).hexdigest(),
            "x-timestamp": f"{max_date}",
            "content-type": mimetype,
            "x-trans-id": "txfcbf2e82791411eaa6bd-cf51efeb8527",
            "x-openstack-request-id": "txfcbf2e82791411eaa6bd-cf51efeb8527",
        }

    def post_object(self, container, obj, headers, response_dict=None):
        path = self.clean_path(container, obj)
        path.touch()

    def _get_container(
        self,
        container,
        marker=None,
        limit=None,
        prefix=None,
        delimiter=None,
        end_marker=None,
        path=None,
        full_listing=False,
        headers=None,
        query_string=None,
    ):
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
        marker: Optional[str] = None,
        limit: Optional[int] = None,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        end_marker: Optional[str] = None,
        path: Optional[str] = None,
        full_listing: bool = False,
        headers: Optional[Dict[str, str]] = None,
        query_string: Optional[str] = None,
    ):
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
        return {}, results

    def copy_object(
        self,
        container: str,
        obj: str,
        destination: str,
        headers: Optional[Dict[str, str]] = None,
        fresh_metadata: Any = None,
        response_dict: Optional[Dict[str, Any]] = None,
    ):
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
        contents: Union[str, bytes],
        content_length: Optional[int] = None,
        etag: Any = None,
        chunk_size: Optional[int] = None,
        content_type: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        query_string: Optional[str] = None,
        response_dict: Optional[Dict[str, Any]] = None,
    ):
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
        query_string: Optional[str] = None,
        response_dict: Optional[Dict[str, Any]] = None,
        headers: Dict[str, str] = None,
    ):
        target = self.clean_path(container, obj)
        if not target.exists():
            from swiftclient.exceptions import ClientException

            raise ClientException(f"File does not exist: {target!s}")
        target.unlink()
        if not list(target.parent.iterdir()):
            target.parent.rmdir()


def is_dir(self, path) -> bool:
    """Check whether the provided path is a directory."""
    target_path = str(path)
    if target_path == ".":
        target_path = ""
    if target_path and not target_path.endswith("/"):
        target_path = f"{target_path}/"
    files = []
    with self.connection() as conn:
        try:
            _, files = conn.get_container(self.default_container, prefix=target_path)
        except (FileNotFoundError, OSError):
            return False
        return bool(files)


def _mock_config(contents, filename="test.conf"):
    """
    Creates a config file with contents and loads them into a
    BandersnatchConfig instance.
    """
    with open(filename, "w") as fd:
        fd.write(contents)

    instance = BandersnatchConfig()
    instance.config_file = filename
    instance.load_configuration()
    return instance


class BasePluginTestCase(TestCase):

    tempdir = None
    cwd = None
    backend = "filesystem"

    config_contents = """\
[mirror]
directory = srv/pypi
storage_backend = {0}
master = https://pypi.org
json = false
timeout = 10
verifiers = 3
diff-file = /tmp/pypi/mirrored-files
diff-append-epoch = false
stop-on-error = false
hash-index = false
workers = 3
; keep_index_versions = 0
; log-config = /etc/bandersnatch-log.conf
"""

    def setUp(self):
        self.cwd = os.getcwd()
        self.tempdir = tempfile.TemporaryDirectory()
        self.pkgs = []
        self.container = None
        if self.backend == "swift":
            mirror_path = "srv/pypi"
            self.container = "bandersnatch"
            self.setUp_swift()
        _mock_config(self.config_contents.format(self.backend))
        bandersnatch.storage.loaded_storage_plugins = defaultdict(list)
        os.chdir(self.tempdir.name)
        self.setUp_mirrorDirs()
        mirror_path = self.mirror_base_path if self.backend != "swift" else mirror_path
        target_sample_file = "sample"
        if self.container is not None:
            target_sample_file = f"{self.container}/{target_sample_file}"
        self.sample_file = os.path.join(self.tempdir.name, target_sample_file)
        shutil.copy(BASE_SAMPLE_FILE, self.sample_file)
        self.mirror = Mirror(mirror_path, Master(url="https://foo.bar.com"))
        pkg = Package("foobar", 1, self.mirror)
        pkg.info = {"name": "foobar", "version": "1.0"}
        pkg.releases = mock.Mock()
        self.pkgs.append(pkg)

    def setUp_mirrorDirs(self):
        pypi_dir = (
            "srv/pypi" if self.container is None else f"{self.container}/srv/pypi"
        )
        self.mirror_base_path = os.path.join(self.tempdir.name, pypi_dir)
        self.web_base_path = os.path.join(self.mirror_base_path, "web")
        self.json_base_path = os.path.join(self.web_base_path, "json")
        self.pypi_base_path = os.path.join(self.web_base_path, "pypi")
        self.simple_base_path = os.path.join(self.web_base_path, "simple")
        os.makedirs(self.json_base_path, exist_ok=True)
        os.makedirs(self.pypi_base_path, exist_ok=True)
        os.makedirs(self.simple_base_path, exist_ok=True)
        self.setUp_Structure()

    def setUp_swift(self):
        self.setUp_swiftVars()
        self.conn_patcher = mock.patch(
            "swiftclient.client.Connection", side_effect=MockConnection
        )
        Connection = self.conn_patcher.start()
        Connection.get_account.return_value = ("", "")

        @contextlib.contextmanager
        def connection(o):
            yield Connection(tmpdir=self.tempdir)

        from bandersnatch_storage_plugins.swift import SwiftStorage

        self.swift_patcher = mock.patch.object(SwiftStorage, "connection", connection)
        self.is_dir_patcher = mock.patch(
            "bandersnatch_storage_plugins.swift.SwiftStorage.is_dir", is_dir
        )
        self.swift_patcher.start()
        self.is_dir_patcher.start()

    def setUp_swiftVars(self):
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

    def tearDown_swiftVars(self):
        for k in self.os_dict.keys():
            if k in os.environ:
                del os.environ[k]
        os.environ.update(self.original_swiftvars)
        self.is_dir_patcher
        self.swift_patcher.stop()
        self.conn_patcher.stop()

    def setUp_Structure(self):
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

    def tearDown(self):
        if self.tempdir:
            os.chdir(self.cwd)
            self.tempdir.cleanup()
        if self.backend == "swift":
            self.tearDown_swiftVars()


class BaseStoragePluginTestCase(BasePluginTestCase):
    base_find_contents = """\
.lock
generation
sample
web
web{0}json
web{0}last-modified
web{0}local-stats
web{0}local-stats{0}days
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
    )

    def test_json_paths(self):
        config = _mock_config(self.config_contents).config

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        mirror_dir = plugin.PATH_BACKEND(config.get("mirror", "directory"))
        packages = {
            "bandersnatch": [
                mirror_dir / "web/json/bandersnatch",
                mirror_dir / "web/pypi/bandersnatch",
            ],
            "black": [mirror_dir / "web/json/black", mirror_dir / "web/pypi/black"],
        }
        for name, json_paths in packages.items():
            with self.subTest(name=name, json_paths=json_paths):
                self.assertEqual(plugin.get_json_paths(name), json_paths)

    def test_canonicalize_package(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        packages = (
            ("SQLAlchemy", "sqlalchemy"),
            ("mypy_extensions", "mypy-extensions"),
            ("py_ecc", "py-ecc"),
            ("Requests", "requests"),
            ("oslo.utils", "oslo-utils"),
        )
        for name, normalized in packages:
            with self.subTest(name=name, normalized=normalized):
                self.assertEqual(plugin.canonicalize_package(name), normalized)

    def test_hash_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        path = plugin.PATH_BACKEND(self.sample_file)
        hashes = (
            ("md5", "125765989403df246cecb48fa3e87ff8"),
            (
                "sha256",
                "95c07c174663ebff531eed59b326ebb3fa95f418f680349fc33b07dfbcf29f18",
            ),
        )
        for hash_func, hash_val in hashes:
            with self.subTest(hash_func=hash_func, hash_val=hash_val):
                self.assertEqual(plugin.hash_file(path, function=hash_func), hash_val)

    def test_iter_dir(self):
        _mock_config(self.config_contents)
        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        base_path = plugin.PATH_BACKEND(self.simple_base_path)
        lists = [
            [base_path.joinpath("foobar"), True],
            [base_path.joinpath("index.html"), False,],
        ]

        self.assertListEqual(list(base_path.iterdir()), [elem[0] for elem in lists])
        for expected, is_dir in lists:
            with self.subTest(is_dir=is_dir, produced_path=expected):
                self.assertIs(is_dir, plugin.is_dir(expected))
                if is_dir is False:
                    self.assertIs(True, plugin.is_file(expected))

    def test_rewrite(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        target_file = os.path.join(self.mirror_base_path, "example.txt")
        replace_with = "new text"
        with open(target_file, "w") as fh:
            fh.write("sample text")
        with plugin.rewrite(target_file) as fh:
            fh.write(replace_with)
        with open(target_file) as fh:
            self.assertEqual(fh.read().strip(), replace_with)

    def test_update_safe(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        target_file = os.path.join(self.mirror_base_path, "example.txt")
        replace_with = "new text"
        with open(target_file, "w") as fh:
            fh.write("sample text")
        with plugin.update_safe(target_file, mode="w") as fh:
            fh.write(replace_with)
        with open(target_file) as fh:
            self.assertEqual(fh.read().strip(), replace_with)

    def test_compare_files(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
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
                msg = "file1 contents: {}\n\nfile2 contents: {}".format(
                    plugin.read_file(cmp_file1), plugin.read_file(cmp_file2)
                )
                self.assertTrue(plugin.compare_files(cmp_file1, cmp_file2) is rv, msg)
        for fn in files:
            os.unlink(fn)

    def test_find(self):
        _mock_config(self.config_contents)
        base_path = self.mirror_base_path
        if self.backend == "swift":
            base_path = base_path.lstrip("/")

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        self.assertEqual(self.base_find_contents, plugin.find(base_path))

    def test_open_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        plugin.write_file(os.path.join(self.mirror_base_path, "status"), "20")
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
                with plugin.open_file(path, text=True) as fh:
                    self.assertEqual(fh.read(), rv)

    def test_write_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        data = ["this is some text", b"this is some text"]
        tmp_path = os.path.join(self.mirror_base_path, "test_write_file.txt")
        for write_val in data:
            with self.subTest(write_val=write_val):
                plugin.write_file(tmp_path, write_val)
                if not isinstance(write_val, str):
                    rv = plugin.PATH_BACKEND(tmp_path).read_bytes()
                else:
                    rv = plugin.PATH_BACKEND(tmp_path).read_text()
                self.assertEqual(rv, write_val)
        os.unlink(tmp_path)

    def test_read_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        plugin.write_file(os.path.join(self.mirror_base_path, "status"), "20")
        rvs = (
            (
                plugin.PATH_BACKEND(self.web_base_path).joinpath("simple/index.html"),
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
            (plugin.PATH_BACKEND(self.mirror_base_path).joinpath("status"), "20"),
        )
        for path, rv in rvs:
            with self.subTest(path=path, rv=rv):
                self.assertEqual(plugin.read_file(path), rv)

    def test_delete(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        delete_path = plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete.txt"
        )
        delete_dir = plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete_dir"
        )
        delete_dir.mkdir()
        delete_path.touch()
        for path in [delete_path, delete_dir]:
            with self.subTest(path=path):
                self.assertTrue(path.exists())
                plugin.delete(path)
                self.assertFalse(path.exists())

    def test_delete_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        delete_path = plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete.txt"
        )
        print(f"delete path: {delete_path!r}")
        delete_path.touch()
        self.assertTrue(delete_path.exists())
        plugin.delete_file(delete_path)
        self.assertFalse(delete_path.exists())

    def test_copy_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        file_content = "this is some data"
        dest_file = os.path.join(self.mirror_base_path, "temp_file.txt")
        with tempfile.NamedTemporaryFile(mode="w") as tf:
            tf.write(file_content)
            tf.flush()
            plugin.copy_file(tf.name, dest_file)
        with open(dest_file) as fh:
            copied_content = fh.read()
        os.unlink(dest_file)
        self.assertEqual(copied_content, file_content)

    def test_mkdir(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        plugin.mkdir(os.path.join(self.mirror_base_path, "test_dir"))
        self.assertTrue(
            plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )
        plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir")).rmdir()

    def test_rmdir(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir")).mkdir()
        assert plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir")
        ).exists()
        plugin.rmdir(
            plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir"))
        )
        self.assertFalse(
            plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )

    def test_is_dir(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir")).mkdir()
        self.assertTrue(
            plugin.is_dir(
                plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir"))
            )
        )
        plugin.rmdir(
            plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir")),
            force=True,
        )

    def test_is_file(self):
        _mock_config(self.config_contents)
        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        delete_path = plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "test_delete.txt"
        )
        delete_path.touch()
        self.assertTrue(plugin.is_file(delete_path))
        delete_path.unlink()

    def test_symlink(self):
        _mock_config(self.config_contents)
        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        file_content = "this is some text"
        test_path = plugin.PATH_BACKEND(self.mirror_base_path).joinpath(
            "symlink_file.txt"
        )
        test_path.write_text(file_content)
        symlink_dest = test_path.parent.joinpath("symlink_dest.txt")
        plugin.symlink(test_path, symlink_dest)
        self.assertEqual(plugin.read_file(symlink_dest), file_content)

    def test_get_hash(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        path = plugin.PATH_BACKEND(self.sample_file)
        expected_hashes = (
            ("md5", "125765989403df246cecb48fa3e87ff8"),
            (
                "sha256",
                "95c07c174663ebff531eed59b326ebb3fa95f418f680349fc33b07dfbcf29f18",
            ),
        )
        for fn, hash_val in expected_hashes:
            with self.subTest(fn=fn, hash_val=hash_val):
                self.assertEqual(plugin.get_hash(path, function=fn), hash_val)


class TestFilesystemStoragePlugin(BaseStoragePluginTestCase):

    config_contents = """\
[mirror]
directory = srv/pypi
storage_backend = filesystem
master = https://pypi.org
json = false
timeout = 10
verifiers = 3
diff-file = /tmp/pypi/mirrored-files
diff-append-epoch = false
stop-on-error = false
hash-index = false
workers = 3
; keep_index_versions = 0
; log-config = /etc/bandersnatch-log.conf
"""

    def test_plugin_is_filesystem(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))

        assert type(plugin) == filesystem.FilesystemStorage
        assert plugin.PATH_BACKEND == pathlib.Path


class TestSwiftStoragePlugin(BaseStoragePluginTestCase):
    backend = "swift"
    base_find_contents = BaseStoragePluginTestCase.base_find_contents.replace(
        ".lock\n", ""
    )

    def test_plugin_is_swift(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        from bandersnatch_storage_plugins import swift

        assert type(plugin) == swift.SwiftStorage, type(plugin)
        assert plugin.PATH_BACKEND == swift.SwiftPath

    def test_mkdir(self):
        _mock_config(self.config_contents)
        tmp_filename = next(tempfile._get_candidate_names())
        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        tmp_file = plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir", tmp_filename)
        )
        tmp_file.write_text("")
        self.assertTrue(
            plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )
        tmp_file.unlink()

    def test_rmdir(self):
        _mock_config(self.config_contents)

        tmp_filename = next(tempfile._get_candidate_names())
        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        tmp_file = plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir", tmp_filename)
        )
        tmp_file.write_text("")
        assert plugin.PATH_BACKEND(
            os.path.join(self.mirror_base_path, "test_dir")
        ).exists()
        tmp_file.unlink()
        self.assertFalse(
            plugin.PATH_BACKEND(
                os.path.join(self.mirror_base_path, "test_dir")
            ).exists()
        )

    def test_copy_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        file_content = "this is some data"
        dest_file = os.path.join(self.mirror_base_path, "temp_file.txt")
        with tempfile.NamedTemporaryFile(
            dir=os.path.join(self.tempdir.name, "bandersnatch"), mode="w"
        ) as tf:
            tf.write(file_content)
            tf.flush()
            plugin.copy_file(tf.name, dest_file)
        with open(dest_file) as fh:
            copied_content = fh.read()
        os.unlink(dest_file)
        self.assertEqual(copied_content, file_content)


if __name__ == "__main__":
    unittest.main()
