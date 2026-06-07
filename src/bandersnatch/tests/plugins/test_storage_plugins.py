import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import bandersnatch.storage
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.package import Package
from bandersnatch.tests.mock_config import mock_config
from bandersnatch_storage_plugins import filesystem

CONFIG = """\
[mirror]
directory = srv/pypi
storage-backend = {backend}
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


@dataclass
class StorageTestEnv:
    plugin: Any
    mirror_base_path: Path
    web_base_path: Path
    json_base_path: Path
    pypi_base_path: Path
    simple_base_path: Path
    sample_file: Path
    mirror: BandersnatchMirror
    pkgs: list[Package]


@pytest.fixture(params=["filesystem"])
def backend(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def storage_env(
    plugin_test_dir: Path,
    backend: str,
) -> StorageTestEnv:
    mock_config(CONFIG.format(backend=backend))

    mirror_root = plugin_test_dir / "srv" / "pypi"
    web_root = mirror_root / "web"

    for p in (
        web_root / "json",
        web_root / "pypi",
        web_root / "simple",
    ):
        p.mkdir(parents=True, exist_ok=True)

    sample = plugin_test_dir / "sample"
    sample.write_text("I am a sample!\n")

    plugin = next(
        iter(
            bandersnatch.storage.storage_backend_plugins(
                backend,
                clear_cache=True,
            )
        )
    )

    master = Master("https://foo.bar.com")

    mirror = BandersnatchMirror(
        mirror_root,
        master,
        backend,
    )

    pkg = Package("foobar", serial=1)
    pkg._metadata = {
        "info": {
            "name": "foobar",
            "version": "1.0",
        },
        "releases": {},
    }

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
        p = web_root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()

    for path in ["generation", "sample", "status"]:
        p = mirror_root / path
        p.touch()

    mirror_root.joinpath("status").write_text("20")
    web_root.joinpath("simple/index.html").write_text("""<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foobar/">foobar</a><br/>
  </body>
</html>""".strip())

    return StorageTestEnv(
        plugin=plugin,
        mirror_base_path=mirror_root,
        web_base_path=web_root,
        json_base_path=web_root / "json",
        pypi_base_path=web_root / "pypi",
        simple_base_path=web_root / "simple",
        sample_file=sample,
        mirror=mirror,
        pkgs=[pkg],
    )


@pytest.fixture
def expected_hashes() -> dict[str, str]:
    hashes = {
        "md5": "125765989403df246cecb48fa3e87ff8",
        "sha256": "95c07c174663ebff531eed59b326ebb3fa95f418f680349fc33b07dfbcf29f18",
    }
    if sys.platform == "win32":
        hashes = {
            "md5": "91ef8f60d130b312af17543b34bfb372",
            "sha256": (
                "398e162e08d9af1d87c8eb2ee46d7c64248867afbe30dee807122022dc497332"
            ),
        }
    return hashes


PLUGIN_MAP = {
    "filesystem": filesystem.FilesystemStorage,
}
PATH_BACKENDS = {
    "filesystem": Path,
}

BASE_FIND_CONTENTS = r"""
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
# filelock 3.25.1+ deletes lock file on release on all platforms


def test_plugin_type(storage_env: StorageTestEnv, backend: str) -> None:
    assert isinstance(storage_env.plugin, PLUGIN_MAP[backend])
    assert storage_env.plugin.PATH_BACKEND is PATH_BACKENDS[backend]


@pytest.mark.parametrize(
    "name",
    ["bandersnatch", "black"],
)
def test_json_paths(
    storage_env: StorageTestEnv,
    backend: str,
    name: str,
) -> None:
    config = mock_config(CONFIG.format(backend=backend))
    mirror_dir = storage_env.plugin.PATH_BACKEND(config.get("mirror", "directory"))
    expected = [
        mirror_dir / f"web/json/{name}",
        mirror_dir / f"web/pypi/{name}",
    ]
    assert storage_env.plugin.get_json_paths(name) == expected


@pytest.mark.parametrize(
    ("name", "normalized"),
    [
        ("SQLAlchemy", "sqlalchemy"),
        ("mypy_extensions", "mypy-extensions"),
        ("py_ecc", "py-ecc"),
        ("Requests", "requests"),
        ("oslo.utils", "oslo-utils"),
    ],
)
def test_canonicalize_package(
    storage_env: StorageTestEnv,
    name: str,
    normalized: str,
) -> None:
    assert storage_env.plugin.canonicalize_package(name) == normalized


@pytest.mark.parametrize("hash_func", ["md5", "sha256"])
def test_hash_file(
    storage_env: StorageTestEnv,
    expected_hashes: dict[str, str],
    hash_func: str,
) -> None:
    path = storage_env.plugin.PATH_BACKEND(storage_env.sample_file)
    assert (
        storage_env.plugin.hash_file(path, function=hash_func)
        == expected_hashes[hash_func]
    )


def test_iter_dir(storage_env: StorageTestEnv) -> None:
    base_path = storage_env.plugin.PATH_BACKEND(storage_env.simple_base_path)
    lists = [
        (base_path.joinpath("foobar"), True),
        (base_path.joinpath("index.html"), False),
    ]

    assert sorted(base_path.iterdir(), key=lambda p: str(p)) == sorted(
        (elem[0] for elem in lists), key=lambda p: str(p)
    )

    for expected, is_dir in lists:
        assert storage_env.plugin.is_dir(expected) is is_dir
        if is_dir is False:
            assert storage_env.plugin.is_file(expected) is True


def test_rewrite(storage_env: StorageTestEnv) -> None:
    target_file = storage_env.mirror_base_path / "example.txt"
    replace_with = "new text"
    target_file.write_text("sample text")
    with storage_env.plugin.rewrite(target_file) as fh:
        fh.write(replace_with)
    assert target_file.read_text().strip() == replace_with


def test_update_safe(storage_env: StorageTestEnv) -> None:
    target_file = storage_env.mirror_base_path / "example.txt"
    replace_with = "new text"
    target_file.write_text("sample text")
    with storage_env.plugin.update_safe(target_file, mode="w") as fh:
        fh.write(replace_with)
    assert target_file.read_text().strip() == replace_with


def test_compare_files(storage_env: StorageTestEnv) -> None:
    target_file1 = storage_env.mirror_base_path / "cmp_example1.txt"
    target_file2 = storage_env.mirror_base_path / "cmp_example2.txt"
    target_file3 = storage_env.mirror_base_path / "cmp_example3.txt"

    target_file1.write_text("sample text")
    target_file2.write_text("sample text")
    target_file3.write_text("some other text")

    comparisons = [
        (target_file1, target_file2, True),
        (target_file1, target_file3, False),
        (target_file2, target_file3, False),
    ]
    for cmp_file1, cmp_file2, rv in comparisons:
        assert storage_env.plugin.compare_files(cmp_file1, cmp_file2) is rv


def test_find(storage_env: StorageTestEnv) -> None:
    base_path = storage_env.mirror_base_path

    # Clean up GitHub Actions environment on macOS tests
    if sys.platform == "darwin":
        env_garbage_path = base_path / "var"
        if env_garbage_path.exists():
            import shutil

            shutil.rmtree(env_garbage_path, ignore_errors=True)

    assert storage_env.plugin.find(base_path) == BASE_FIND_CONTENTS


def test_open_file(storage_env: StorageTestEnv) -> None:
    storage_env.plugin.write_file(storage_env.mirror_base_path / "status", "20")
    rvs = [
        (
            storage_env.web_base_path / "simple/index.html",
            """<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foobar/">foobar</a><br/>
  </body>
</html>""".strip(),
        ),
        (storage_env.mirror_base_path / "status", "20"),
    ]
    for path, expected in rvs:
        with storage_env.plugin.open_file(path, text=True) as fh:
            assert fh.read() == expected


@pytest.mark.parametrize(
    "write_val",
    ["this is some text", b"this is some text"],
)
def test_write_file(storage_env: StorageTestEnv, write_val: str | bytes) -> None:
    tmp_path = storage_env.mirror_base_path / "test_write_file.txt"
    storage_env.plugin.write_file(tmp_path, write_val)
    if isinstance(write_val, str):
        rv = storage_env.plugin.PATH_BACKEND(tmp_path).read_text()
    else:
        rv = storage_env.plugin.PATH_BACKEND(tmp_path).read_bytes()
    assert rv == write_val


def test_read_file(storage_env: StorageTestEnv) -> None:
    storage_env.plugin.write_file(storage_env.mirror_base_path / "status", "20")
    rvs = [
        (
            storage_env.plugin.PATH_BACKEND(storage_env.web_base_path).joinpath(
                "simple/index.html"
            ),
            """<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foobar/">foobar</a><br/>
  </body>
</html>""".strip(),
        ),
        (
            storage_env.plugin.PATH_BACKEND(storage_env.mirror_base_path).joinpath(
                "status"
            ),
            "20",
        ),
    ]
    for path, expected in rvs:
        assert storage_env.plugin.read_file(path) == expected


def test_delete(storage_env: StorageTestEnv) -> None:
    delete_path = storage_env.plugin.PATH_BACKEND(
        storage_env.mirror_base_path
    ).joinpath("test_delete.txt")
    delete_dir = storage_env.plugin.PATH_BACKEND(storage_env.mirror_base_path).joinpath(
        "test_delete_dir"
    )
    delete_dir.mkdir()
    delete_path.touch()
    for path in [delete_path, delete_dir]:
        assert path.exists()
        storage_env.plugin.delete(path)
        assert not path.exists()


def test_delete_file(storage_env: StorageTestEnv) -> None:
    delete_path = storage_env.plugin.PATH_BACKEND(
        storage_env.mirror_base_path
    ).joinpath("test_delete.txt")
    delete_path.touch()
    assert delete_path.exists()
    storage_env.plugin.delete_file(delete_path)
    assert not delete_path.exists()


def test_copy_file(storage_env: StorageTestEnv, plugin_test_dir: Path) -> None:
    file_content = "this is some data"
    src_file = plugin_test_dir / "src_temp.txt"
    src_file.write_text(file_content)

    dest_file = storage_env.mirror_base_path / "temp_file.txt"
    # Set permissions on the tmp file explicitly to avoid false-positives
    # caused by umask.
    src_file.chmod(0o700)
    storage_env.plugin.copy_file(str(src_file), str(dest_file))

    assert dest_file.read_text() == file_content
    assert src_file.stat().st_mode == dest_file.stat().st_mode

    dest_file2 = storage_env.mirror_base_path / "temp_file2.txt"
    storage_env.plugin.manage_permissions = False
    src_file.chmod(0o777)
    storage_env.plugin.copy_file(str(src_file), str(dest_file2))

    if sys.platform == "win32":
        assert src_file.stat().st_mode == dest_file2.stat().st_mode
    else:
        assert src_file.stat().st_mode != dest_file2.stat().st_mode


def test_mkdir(storage_env: StorageTestEnv) -> None:
    test_dir = storage_env.mirror_base_path / "test_dir"
    storage_env.plugin.mkdir(str(test_dir))
    assert storage_env.plugin.PATH_BACKEND(test_dir).exists()


def test_scandir(storage_env: StorageTestEnv) -> None:
    test_dir = storage_env.mirror_base_path / "test_dir"
    sub_dir = test_dir / "sub_dir"
    sub_file = test_dir / "sub_file"
    sub_link = test_dir / "sub_link"

    storage_env.plugin.mkdir(str(test_dir))
    storage_env.plugin.mkdir(str(sub_dir))
    storage_env.plugin.write_file(str(sub_file), "test")
    storage_env.plugin.symlink(str(sub_file), str(sub_link))

    entries = {ent.name: ent for ent in storage_env.plugin.scandir(str(test_dir))}

    assert len(entries) == 3
    assert entries["sub_dir"].is_dir()
    assert entries["sub_file"].is_file()
    assert entries["sub_link"].is_symlink()


def test_rmdir(storage_env: StorageTestEnv) -> None:
    test_dir = storage_env.mirror_base_path / "test_dir"
    storage_env.plugin.PATH_BACKEND(test_dir).mkdir()
    assert storage_env.plugin.PATH_BACKEND(test_dir).exists()
    storage_env.plugin.rmdir(storage_env.plugin.PATH_BACKEND(test_dir))
    assert not storage_env.plugin.PATH_BACKEND(test_dir).exists()


def test_is_dir(storage_env: StorageTestEnv) -> None:
    test_dir = storage_env.mirror_base_path / "test_dir"
    storage_env.plugin.PATH_BACKEND(test_dir).mkdir()
    assert storage_env.plugin.is_dir(storage_env.plugin.PATH_BACKEND(test_dir))


def test_is_file(storage_env: StorageTestEnv) -> None:
    delete_path = storage_env.plugin.PATH_BACKEND(
        storage_env.mirror_base_path
    ).joinpath("test_delete.txt")
    delete_path.touch()
    assert storage_env.plugin.is_file(delete_path)


def test_symlink(storage_env: StorageTestEnv) -> None:
    file_content = "this is some text"
    test_path = storage_env.plugin.PATH_BACKEND(storage_env.mirror_base_path).joinpath(
        "symlink_file.txt"
    )
    test_path.write_text(file_content)
    symlink_dest = test_path.parent.joinpath("symlink_dest.txt")
    storage_env.plugin.symlink(test_path, symlink_dest)
    assert storage_env.plugin.read_file(symlink_dest) == file_content


@pytest.mark.parametrize("hash_func", ["md5", "sha256"])
def test_get_hash(
    storage_env: StorageTestEnv,
    expected_hashes: dict[str, str],
    hash_func: str,
) -> None:
    path = storage_env.plugin.PATH_BACKEND(storage_env.sample_file)
    assert (
        storage_env.plugin.get_hash(path, function=hash_func)
        == expected_hashes[hash_func]
    )
