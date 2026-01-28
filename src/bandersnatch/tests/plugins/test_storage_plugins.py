import atexit
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from typing import TYPE_CHECKING
from unittest import TestCase, mock

import bandersnatch.storage
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_storage_plugins import filesystem

if TYPE_CHECKING:
    pass

SAMPLE_FILE_CONTENT = "I am a sample!\n"
BASE_SAMPLE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample"
)


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
        pypi_dir = "srv/pypi"
        assert self.tempdir
        self.mirror_base_path = os.path.join(self.tempdir.name, pypi_dir)
        self.setUp_dirs()
        target_sample_file = "sample"
        if self.container is not None:
            target_sample_file = f"{self.container}/{target_sample_file}"
        assert self.tempdir
        self.sample_file = os.path.join(self.tempdir.name, target_sample_file)
        with open(self.sample_file, mode="w") as sample_file:
            sample_file.write(SAMPLE_FILE_CONTENT)

        self.mirror_path = pathlib.Path(self.mirror_base_path)

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


class BaseStoragePluginTestCase(BasePluginTestCase):
    plugin_map = {
        "filesystem": filesystem.FilesystemStorage,
    }
    path_backends = {
        "filesystem": pathlib.Path,
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
web{0}simple{0}index.html""".format(os.sep).strip()
    if sys.platform == "win32":
        base_find_contents = base_find_contents.replace(".lock\n", "")

    def test_plugin_type(self) -> None:
        assert self.backend
        self.assertTrue(isinstance(self.plugin, self.plugin_map[self.backend]))
        self.assertTrue(self.plugin.PATH_BACKEND is self.path_backends[self.backend])

    def test_json_paths(self) -> None:
        config = mock_config(self.config_contents)
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
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            atexit.register(os.unlink, tf.name)
            tf.write(file_content)
            tf.flush()

        dest_file = os.path.join(self.mirror_base_path, "temp_file.txt")
        # Set permissions on the tmp file explicitly to avoid false-positives
        # caused by umask.
        os.chmod(tf.name, 0o700)
        self.plugin.copy_file(tf.name, dest_file)
        with open(dest_file) as fh:
            copied_content = fh.read()
            self.assertEqual(os.stat(tf.name).st_mode, os.stat(dest_file).st_mode)
        self.assertEqual(copied_content, file_content)
        os.unlink(dest_file)

        dest_file2 = os.path.join(self.mirror_base_path, "temp_file2.txt")
        self.plugin.manage_permissions = False
        os.chmod(tf.name, 0o777)
        self.plugin.copy_file(tf.name, dest_file2)
        with open(dest_file2) as fh:
            if sys.platform == "win32":
                self.assertEqual(os.stat(tf.name).st_mode, os.stat(dest_file2).st_mode)
            else:
                self.assertNotEqual(
                    os.stat(tf.name).st_mode, os.stat(dest_file2).st_mode
                )

        os.unlink(dest_file2)

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


if __name__ == "__main__":
    unittest.main()
