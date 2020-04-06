import os
import pathlib
import shutil
import sys
import unittest
from collections import defaultdict
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest import TestCase, mock

import bandersnatch.storage
from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.master import Master
from bandersnatch.mirror import Mirror
from bandersnatch.package import Package
from bandersnatch_storage_plugins import filesystem


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

    def setUp(self):
        _mock_config(self.config_contents)
        self.cwd = os.getcwd()
        self.tempdir = TemporaryDirectory()
        self.pkgs = []
        bandersnatch.storage.loaded_storage_plugins = defaultdict(list)
        sample_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample"
        )
        self.sample_file = os.path.join(self.tempdir.name, "sample")
        os.chdir(self.tempdir.name)
        self.setUp_mirrorDirs()
        shutil.copy(sample_file, self.sample_file)
        self.mirror = Mirror(self.mirror_base_path, Master(url="https://foo.bar.com"))
        pkg = Package("foobar", 1, self.mirror)
        pkg.info = {"name": "foobar", "version": "1.0"}
        pkg.releases = mock.Mock()
        self.pkgs.append(pkg)

    def setUp_mirrorDirs(self):
        self.mirror_base_path = os.path.join(self.tempdir.name, "srv/pypi")
        self.web_base_path = os.path.join(self.mirror_base_path, "web")
        self.json_base_path = os.path.join(self.web_base_path, "json")
        self.pypi_base_path = os.path.join(self.web_base_path, "pypi")
        self.simple_base_path = os.path.join(self.web_base_path, "simple")
        os.makedirs(self.json_base_path, exist_ok=True)
        os.makedirs(self.pypi_base_path, exist_ok=True)
        os.makedirs(self.simple_base_path, exist_ok=True)
        self.setUp_Structure()

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
        paths = [".lock", "generation", "sample", "status"]
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
            self.tempdir = None


class BaseStoragePluginTestCase(BasePluginTestCase):
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
        lists = [
            [[plugin.PATH_BACKEND(self.simple_base_path).joinpath("foobar")], True],
            [
                [plugin.PATH_BACKEND(self.simple_base_path).joinpath("index.html")],
                False,
            ],
        ]

        def include_path(pth, is_dir_condition):
            if pth.is_dir():
                if is_dir_condition:
                    return True
                return False
            return True

        for expected, is_dir in lists:
            with self.subTest(is_dir=is_dir, expected=expected):
                paths = [
                    path
                    for path in plugin.iter_dir(self.simple_base_path)
                    if (is_dir and plugin.is_dir(path))
                    or (not is_dir and plugin.is_file(path))
                ]
                self.assertEqual(paths, expected)

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

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        self.assertEqual(
            """\
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
            ),
            plugin.find(self.mirror_base_path),
        )

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
                print(str(os.listdir(self.mirror_base_path)), file=sys.stderr)
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
        delete_path.touch()
        self.assertTrue(delete_path.exists())
        plugin.delete_file(delete_path)
        self.assertFalse(delete_path.exists())

    def test_copy_file(self):
        _mock_config(self.config_contents)

        plugin = next(iter(bandersnatch.storage.storage_backend_plugins()))
        file_content = "this is some data"
        dest_file = os.path.join(self.mirror_base_path, "temp_file.txt")
        with NamedTemporaryFile(mode="w") as tf:
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
        plugin.PATH_BACKEND(os.path.join(self.mirror_base_path, "test_dir")).rmdir()

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


if __name__ == "__main__":
    unittest.main()
