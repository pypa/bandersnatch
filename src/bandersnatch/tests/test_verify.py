import configparser
import json
import logging
import os
import sys
import unittest.mock as mock
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import rmtree
from tempfile import gettempdir
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiohttp.client_exceptions import ClientResponseError, ServerTimeoutError

import bandersnatch
from bandersnatch.master import Master
from bandersnatch.storage import PATH_TYPES, FileSpec
from bandersnatch.utils import convert_url_to_path, find
from bandersnatch_storage_plugins.filesystem import FilesystemStorage

from bandersnatch.verify import (  # isort:skip
    DownloadStats,
    get_latest_json,
    delete_unowned_files,
    log_download_summary,
    metadata_verify,
    verify_producer,
    verify,
    _parse_release_file_size,
)


def _make_fs_storage(directory: Path | str) -> FilesystemStorage:
    """Create a FilesystemStorage backed by *directory* for use in tests."""
    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "mirror": {
                "storage-backend": "filesystem",
                "directory": str(directory),
                "workers": "2",
                "compare-method": "hash",
                "digest_name": "sha256",
                "stop-on-error": "false",
            }
        }
    )
    return FilesystemStorage(config=cfg)


def _verify_mirror_config(
    tmp_path: Path, verifiers: str = "1"
) -> configparser.ConfigParser:
    """Full mirror config for verify_producer() / metadata_verify() integration tests."""
    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "mirror": {
                "storage-backend": "filesystem",
                "directory": str(tmp_path),
                "master": "https://unittest.org",
                "timeout": "10",
                "global-timeout": "1800",
                "workers": "1",
                "verifiers": verifiers,
                "compare-method": "hash",
                "digest_name": "sha256",
                "stop-on-error": "false",
            }
        }
    )
    return cfg


class VerifyArgs:
    dry_run = True
    json_update = False
    delete = False
    workers = 1


async def do_nothing(*args: Any, **kwargs: Any) -> None:
    pass


async def do_nothing_stats(*args: Any, **kwargs: Any) -> DownloadStats:
    return DownloadStats()


async def fake_fetch(_: str, save_path: Path, *__: Any) -> None:
    save_path.write_text("fake text")


def some_paths(*_: Any, **__: Any) -> list[Path]:
    return [Path("/data/pypi/web/json/bandersnatch"), Path("/data/pypi/web/json/black")]


class FakeConfig:
    def get(self, section: str, item: str, fallback: str = "") -> str:
        if section == "mirror":
            if item == "directory":
                return "/data/pypi"
            if item == "master":
                return "https://unittest.org"
            if item == "storage-backend":
                return "filesystem"
        return fallback

    def getfloat(self, section: str, item: str, fallback: float = 0.5) -> float:
        return fallback

    def getint(self, section: str, item: str, fallback: int = 5) -> int:
        return fallback

    def getboolean(self, section: str, item: str, fallback: bool = False) -> bool:
        if section == "mirror":
            if item == "stop-on-error":
                return False
        return fallback


# TODO: Support testing sharded simple dirs
class FakeMirror:
    def __init__(self, entropy: str = "") -> None:
        self.mirror_base = Path(gettempdir()) / f"pypi_unittest_{os.getpid()}{entropy}"
        if self.mirror_base.exists():
            return
        self.web_base = self.mirror_base / "web"
        self.web_base.mkdir(parents=True)
        self.json_path = self.web_base / "json"
        self.package_path = self.web_base / "packages"
        self.pypi_path = self.web_base / "pypi"
        self.simple_path = self.web_base / "simple"

        for web_dir in (
            self.json_path,
            self.package_path,
            self.pypi_path,
            self.simple_path,
        ):
            web_dir.mkdir()

        self.pypi_packages = {
            "bandersnatch": {
                "bandersnatch-0.6.9": {
                    "filename": "bandersnatch-0.6.9.tar.gz",
                    "contents": "69",
                    "sha256": (
                        "b35e87b5838011a3637be660e4238af9a55e4edc74404c990f7a558e7f416658"
                    ),  # noqa: E501
                    "url": (
                        "https://test.pypi.org/packages/8f/1a/6969/bandersnatch-0.6.9.tar.gz"
                    ),  # noqa: E501
                }
            },
            "black": {
                "black-2018.6.9": {
                    "filename": "black-2018.6.9.tar.gz",
                    "contents": "69",
                    "sha256": (
                        "b35e87b5838011a3637be660e4238af9a55e4edc74404c990f7a558e7f416658"
                    ),  # noqa: E501
                    "url": (
                        "https://test.pypi.org/packages/8f/1a/6969/black-2018.6.9.tar.gz"
                    ),  # noqa: E501
                },
                "black-2019.6.9": {
                    "filename": "black-2019.6.9.tar.gz",
                    "contents": "1469",
                    "sha256": (
                        "c896470f5975bd5dc7d173871faca19848855b01bacf3171e9424b8a993b528b"
                    ),  # noqa: E501
                    "url": (
                        "https://test.pypi.org/packages/8f/1a/1aa0/black-2019.6.9.tar.gz"
                    ),  # noqa: E501
                },
            },
        }

        # Create each subdir of web
        self.setup_json()
        self.setup_simple()
        self.setup_packages()

    def clean_up(self) -> None:
        if self.mirror_base.exists():
            rmtree(self.mirror_base)

    def setup_json(self) -> None:
        for pkg in self.pypi_packages.keys():
            pkg_json = self.json_path / pkg
            pkg_json.touch()
            pkg_legacy_json = self.pypi_path / pkg / "json"
            pkg_legacy_json.parent.mkdir()
            pkg_legacy_json.symlink_to(str(pkg_json))

    def setup_packages(self) -> None:
        for _pkg, dists in self.pypi_packages.items():
            for _version, metadata in dists.items():
                dist_file = self.web_base / convert_url_to_path(metadata["url"])
                dist_file.parent.mkdir(exist_ok=True, parents=True)
                with dist_file.open("w") as dfp:
                    dfp.write(metadata["contents"])

    def setup_simple(self) -> None:
        for pkg in self.pypi_packages.keys():
            pkg_dir = self.simple_path / pkg
            pkg_dir.mkdir()
            index_path = pkg_dir / "index.html"
            index_path.touch()


@pytest.mark.asyncio
async def test_verify_producer(monkeypatch: pytest.MonkeyPatch) -> None:
    fm = FakeMirror("test_async_verify")
    fc = configparser.ConfigParser()
    fc["mirror"] = {}
    fc["mirror"]["verifiers"] = "2"
    storage_backend = _make_fs_storage(fm.mirror_base)
    master = Master("https://unittest.org")
    json_files = ["web/json/bandersnatch", "web/json/black"]
    processed: list[str] = []

    async def track_verify(*args: Any, **kwargs: Any) -> None:
        processed.append(args[3])

    monkeypatch.setattr(bandersnatch.verify, "verify", track_verify)
    await verify_producer(
        master, fc, storage_backend, [], fm.mirror_base, json_files, mock.Mock(), None
    )
    assert sorted(processed) == sorted(json_files)


@pytest.mark.asyncio
async def test_verify_producer_distributes_work_with_multiple_verifiers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each package is verified exactly once with multiple concurrent consumers."""
    fc = _verify_mirror_config(tmp_path, verifiers="3")
    storage_backend = FilesystemStorage(config=fc)
    json_files = ["pkgone", "pkgtwo", "pkgthree"]
    processed: list[str] = []

    async def track_verify(*args: Any, **kwargs: Any) -> None:
        processed.append(args[3])

    monkeypatch.setattr(bandersnatch.verify, "verify", track_verify)
    await verify_producer(
        Master("https://unittest.org"),
        fc,
        storage_backend,
        [],
        tmp_path,
        json_files,
        mock.Mock(),
        None,
    )

    assert sorted(processed) == sorted(json_files)
    assert len(processed) == len(json_files)


@pytest.mark.asyncio
async def test_verify_producer_extra_verifiers_finish_cleanly(
    tmp_path: Path,
) -> None:
    """Idle consumers exit when the queue is drained (verifiers > package count)."""
    import hashlib

    fc = _verify_mirror_config(tmp_path, verifiers="5")
    storage_backend = FilesystemStorage(config=fc)

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    url = "https://files.pythonhosted.org/packages/aa/bb/only.whl"
    sha256 = hashlib.sha256(b"content").hexdigest()
    (jsonpath / "onlypkg").write_text(_pkg_json("only.whl", url, sha256, 100))

    stats = await verify_producer(
        Master("https://unittest.org"),
        fc,
        storage_backend,
        [],
        tmp_path,
        ["onlypkg"],
        VerifyArgs(),  # type: ignore[arg-type]
        None,
    )

    assert stats == DownloadStats(file_count=1, total_bytes=100, unknown_size_count=0)


def test_fake_mirror() -> None:
    expected_mirror_layout = """\
web
web{0}json
web{0}json{0}bandersnatch
web{0}json{0}black
web{0}packages
web{0}packages{0}8f
web{0}packages{0}8f{0}1a
web{0}packages{0}8f{0}1a{0}1aa0
web{0}packages{0}8f{0}1a{0}1aa0{0}black-2019.6.9.tar.gz
web{0}packages{0}8f{0}1a{0}6969
web{0}packages{0}8f{0}1a{0}6969{0}bandersnatch-0.6.9.tar.gz
web{0}packages{0}8f{0}1a{0}6969{0}black-2018.6.9.tar.gz
web{0}pypi
web{0}pypi{0}bandersnatch
web{0}pypi{0}bandersnatch{0}json
web{0}pypi{0}black
web{0}pypi{0}black{0}json
web{0}simple
web{0}simple{0}bandersnatch
web{0}simple{0}bandersnatch{0}index.html
web{0}simple{0}black
web{0}simple{0}black{0}index.html""".format(os.sep)
    fm = FakeMirror("_mirror_base_test")
    assert expected_mirror_layout == find(str(fm.mirror_base), True)
    fm.clean_up()


@pytest.mark.asyncio
async def test_delete_unowned_files(caplog: pytest.LogCaptureFixture) -> None:
    executor = ThreadPoolExecutor(max_workers=2)
    fm = FakeMirror("_test_delete_files")
    storage_backend = _make_fs_storage(fm.mirror_base)
    # Leave out black-2018.6.9.tar.gz so it gets deleted
    all_pkgs = [
        fm.mirror_base / "web/packages/8f/1a/1aa0/black-2019.6.9.tar.gz",
        fm.mirror_base / "web/packages/8f/1a/6969/bandersnatch-0.6.9.tar.gz",
    ]
    with caplog.at_level(logging.INFO):
        await delete_unowned_files(
            storage_backend, fm.mirror_base, executor, all_pkgs, True
        )
        await delete_unowned_files(
            storage_backend, fm.mirror_base, executor, all_pkgs, False
        )
    assert "Deleting 1 unowned files" in caplog.text
    deleted_path = fm.mirror_base / "web/packages/8f/1a/6969/black-2018.6.9.tar.gz"
    assert not deleted_path.exists()
    fm.clean_up()


@pytest.mark.asyncio
async def test_get_latest_json(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = ThreadPoolExecutor(max_workers=2)
    json_path = Path(gettempdir()) / f"unittest_{os.getpid()}.json"
    master = Master("https://unittest.org")
    monkeypatch.setattr(master, "url_fetch", fake_fetch)
    await get_latest_json(master, json_path, executor)
    assert json_path.read_text() == "fake text"


@pytest.mark.asyncio
async def test_metadata_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeArgs:
        delete = True
        dry_run = True
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()
    monkeypatch.setattr(bandersnatch.verify, "verify_producer", do_nothing_stats)
    monkeypatch.setattr(bandersnatch.verify, "delete_unowned_files", do_nothing)
    monkeypatch.setattr(Path, "iterdir", some_paths)
    await metadata_verify(fc, fa)  # type: ignore


@pytest.mark.asyncio
async def test_get_latest_json_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeArgs:
        delete = True
        dry_run = False
        json_update = True
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)

    master = Master(fc.get("mirror", "master"))
    url_fetch_timeout = AsyncMock(side_effect=ServerTimeoutError)
    monkeypatch.setattr(master, "url_fetch", url_fetch_timeout)

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    jsonfile = jsonpath / "bandersnatch"
    jsonfile.touch()
    all_package_files: list[Path] = []

    await verify(
        master, fc, storage_backend, "bandersnatch", tmp_path, all_package_files, fa  # type: ignore
    )
    assert jsonfile.exists()
    assert not all_package_files


@pytest.mark.asyncio
async def test_get_latest_json_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeArgs:
        delete = True
        dry_run = False
        json_update = True
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)

    master = Master(fc.get("mirror", "master"))
    url_fetch_404 = AsyncMock(
        side_effect=ClientResponseError(status=404, history=(), request_info=None)
    )
    monkeypatch.setattr(master, "url_fetch", url_fetch_404)

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    jsonfile = jsonpath / "bandersnatch"
    jsonfile.touch()
    all_package_files: list[Path] = []

    await verify(
        master, fc, storage_backend, "bandersnatch", tmp_path, all_package_files, fa  # type: ignore # noqa: E501
    )
    assert not jsonfile.exists()
    assert not all_package_files


@pytest.mark.asyncio
async def test_verify_url_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeArgs:
        delete = True
        dry_run = False
        json_update = False
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)

    master = Master(fc.get("mirror", "master"))

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True, exist_ok=True)
    jsonfile = jsonpath / "bandersnatch"
    with jsonfile.open("w") as f:
        f.write(
            '{"releases":{"1.0":["url":"https://unittests.org/packages/a0/a0/a0a0/package-1.0.0.exe"}]}}'  # noqa: E501
        )
    all_package_files: list[Path] = []

    await verify(master, fc, storage_backend, "bandersnatch", tmp_path, all_package_files, fa)  # type: ignore # noqa: E501
    assert jsonfile.exists()
    assert not all_package_files


@pytest.mark.asyncio
async def test_verify_files_default_missing(tmp_path: Path) -> None:
    """verify_files yields a FileSpec when the file does not exist."""
    import datetime

    storage_backend = _make_fs_storage(tmp_path)
    spec = FileSpec(
        path=tmp_path / "missing.whl",
        url="https://example.com/missing.whl",
        filename="missing.whl",
        size=100,
        digests={"sha256": "abc123"},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in storage_backend.verify_files([spec])]
    assert bad == [spec]


@pytest.mark.asyncio
async def test_verify_files_default_valid(tmp_path: Path) -> None:
    """verify_files does not yield a spec whose digest matches the stored file."""
    import datetime
    import hashlib

    content = b"hello bandersnatch"
    f = tmp_path / "pkg.whl"
    f.write_bytes(content)
    sha256 = hashlib.sha256(content).hexdigest()

    storage_backend = _make_fs_storage(tmp_path)
    spec = FileSpec(
        path=f,
        url="https://example.com/pkg.whl",
        filename="pkg.whl",
        size=len(content),
        digests={"sha256": sha256},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in storage_backend.verify_files([spec])]
    assert bad == []


@pytest.mark.asyncio
async def test_verify_files_default_corrupt(tmp_path: Path) -> None:
    """verify_files yields a spec when the stored digest does not match."""
    import datetime

    f = tmp_path / "pkg.whl"
    f.write_bytes(b"corrupted content")

    storage_backend = _make_fs_storage(tmp_path)
    spec = FileSpec(
        path=f,
        url="https://example.com/pkg.whl",
        filename="pkg.whl",
        size=len(b"corrupted content"),
        digests={"sha256": "deadbeef" * 8},
        upload_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )
    bad = [s async for s in storage_backend.verify_files([spec])]
    assert bad == [spec]


@pytest.mark.asyncio
async def test_verify_files_stat_mode(tmp_path: Path) -> None:
    """With compare-method=stat, a matching upload_time skips the hash check."""
    import datetime

    f = tmp_path / "pkg.whl"
    f.write_bytes(b"data")

    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "mirror": {
                "storage-backend": "filesystem",
                "directory": str(tmp_path),
                "workers": "2",
                "compare-method": "stat",
                "digest_name": "sha256",
            }
        }
    )
    storage_backend = FilesystemStorage(config=cfg)

    # Set the upload time on disk to match what the spec says.
    upload_time = datetime.datetime(2024, 6, 1, tzinfo=datetime.UTC)
    storage_backend.set_upload_time(f, upload_time)

    spec = FileSpec(
        path=f,
        url="https://example.com/pkg.whl",
        filename="pkg.whl",
        size=4,
        digests={"sha256": "wrong_hash_should_not_be_checked"},
        upload_time=upload_time,
    )
    bad = [s async for s in storage_backend.verify_files([spec])]
    assert bad == []


def test_iter_package_files(tmp_path: Path) -> None:
    """iter_package_files yields real files without any keep_file concepts."""
    packages = tmp_path / "web" / "packages"
    (packages / "8f" / "1a").mkdir(parents=True)
    f1 = packages / "8f" / "1a" / "pkg-1.0.whl"
    f2 = packages / "8f" / "1a" / "pkg-2.0.whl"
    f1.write_bytes(b"a")
    f2.write_bytes(b"b")

    storage_backend = _make_fs_storage(tmp_path)
    found = set(storage_backend.iter_package_files(packages))
    assert found == {f1, f2}


def _pkg_json(filename: str, url: str, sha256: str, size: int | None) -> str:
    """Minimal PyPI-style JSON for a single-file package."""
    return json.dumps(
        {
            "info": {"name": "mypackage"},
            "releases": {
                "1.0": [
                    {
                        "filename": filename,
                        "url": url,
                        "size": size,
                        "digests": {"sha256": sha256},
                        "upload_time_iso_8601": "2024-01-01T00:00:00Z",
                    }
                ]
            },
        }
    )


@pytest.mark.asyncio
async def test_verify_skips_invalid_metadata(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """verify() skips JSON that parses but lacks required PyPI metadata."""
    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "badpackage").write_text(json.dumps({"releases": {}}))

    class FakeArgs:
        dry_run = False
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))
    all_files: list[PATH_TYPES] = []

    with caplog.at_level("ERROR"):
        await verify(
            master,
            fc,  # type: ignore[arg-type]
            storage_backend,
            "badpackage",
            tmp_path,
            all_files,
            FakeArgs(),  # type: ignore[arg-type]
        )

    assert all_files == []
    assert "into a Package" in caplog.text


@pytest.mark.asyncio
async def test_verify_skips_malformed_json(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """verify() skips JSON files that fail to parse."""
    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "badpackage").write_text("{not valid json")

    class FakeArgs:
        dry_run = False
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))
    all_files: list[PATH_TYPES] = []

    with caplog.at_level("ERROR"):
        await verify(
            master,
            fc,  # type: ignore[arg-type]
            storage_backend,
            "badpackage",
            tmp_path,
            all_files,
            FakeArgs(),  # type: ignore[arg-type]
        )

    assert all_files == []
    assert "metadata:" in caplog.text
    assert "into a Package" not in caplog.text


@pytest.mark.asyncio
async def test_verify_dry_run_logs_but_does_not_fetch(tmp_path: Path) -> None:
    """verify() logs [DRY RUN] and never calls fetch_and_store when dry_run=True."""
    content = b"wheel content"
    import hashlib

    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    class FakeArgs:
        dry_run = True
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))
    all_files: list[PATH_TYPES] = []

    with mock.patch("bandersnatch.verify.fetch_and_store") as mock_fetch:
        await verify(master, fc, storage_backend, "mypackage", tmp_path, all_files, FakeArgs())  # type: ignore

    mock_fetch.assert_not_called()
    assert len(all_files) == 1  # spec was registered


@pytest.mark.asyncio
async def test_verify_remediates_missing_file(tmp_path: Path) -> None:
    """verify() calls fetch_and_store for a file that verify_files reports as bad."""
    import hashlib

    content = b"wheel content"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    class FakeArgs:
        dry_run = False
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))

    async def _noop_fetch(*args: Any, **kwargs: Any) -> None:
        pass

    all_files: list[PATH_TYPES] = []
    with mock.patch(
        "bandersnatch.verify.fetch_and_store", side_effect=_noop_fetch
    ) as mock_fetch:
        await verify(master, fc, storage_backend, "mypackage", tmp_path, all_files, FakeArgs())  # type: ignore

    mock_fetch.assert_called_once()
    assert len(all_files) == 1


@pytest.mark.asyncio
async def test_verify_defers_fetch_exception(tmp_path: Path) -> None:
    """When fetch_and_store raises, the error is logged and deferred to on_error."""
    import hashlib

    content = b"data"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    class FakeArgs:
        dry_run = False
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))

    async def _failing_fetch(*args: Any, **kwargs: Any) -> None:
        raise ValueError("download failed")

    with mock.patch("bandersnatch.verify.fetch_and_store", side_effect=_failing_fetch):
        with mock.patch("bandersnatch.verify.on_error") as mock_on_error:
            await verify(master, fc, storage_backend, "mypackage", tmp_path, [], FakeArgs())  # type: ignore

    mock_on_error.assert_called_once()
    call_exc = mock_on_error.call_args[0][1]
    assert isinstance(call_exc, ValueError)


# ---------------------------------------------------------------------------
# storage.py base-class coverage
# ---------------------------------------------------------------------------


def test_stamp_file_metadata_calls_set_upload_time_and_set_hash(tmp_path: Path) -> None:
    """The base stamp_file_metadata calls set_upload_time then set_hash."""
    import datetime
    import hashlib

    storage_backend = _make_fs_storage(tmp_path)
    f = tmp_path / "pkg.whl"
    f.write_bytes(b"content")

    upload_time = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
    sha256 = hashlib.sha256(b"content").hexdigest()

    with mock.patch.object(storage_backend, "set_upload_time") as mock_upload:
        with mock.patch.object(storage_backend, "set_hash") as mock_hash:
            storage_backend.stamp_file_metadata(f, sha256, upload_time)

    mock_upload.assert_called_once_with(f, upload_time)
    mock_hash.assert_called_once_with(f, sha256, "sha256")


def test_iter_package_files_nonexistent_path(tmp_path: Path) -> None:
    """iter_package_files returns nothing when packages_path does not exist."""
    storage_backend = _make_fs_storage(tmp_path)
    result = list(storage_backend.iter_package_files(tmp_path / "does_not_exist"))
    assert result == []


@pytest.mark.asyncio
async def test_verify_files_stat_mode_mismatch(tmp_path: Path) -> None:
    """With compare-method=stat, a file whose upload time does not match is flagged."""
    import datetime

    f = tmp_path / "pkg.whl"
    f.write_bytes(b"data")

    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "mirror": {
                "storage-backend": "filesystem",
                "directory": str(tmp_path),
                "workers": "2",
                "compare-method": "stat",
                "digest_name": "sha256",
                "stop-on-error": "false",
            }
        }
    )
    storage_backend = FilesystemStorage(config=cfg)

    wrong_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
    spec = FileSpec(
        path=f,
        url="https://example.com/pkg.whl",
        filename="pkg.whl",
        size=len(b"data"),
        digests={"sha256": "dontcare"},
        upload_time=wrong_time,
    )
    bad = [s async for s in storage_backend.verify_files([spec])]
    assert bad == [spec]


# ---------------------------------------------------------------------------
# filesystem.py coverage — empty-parent cleanup after delete
# ---------------------------------------------------------------------------


def test_delete_package_file_removes_empty_parent(tmp_path: Path) -> None:
    """delete_package_file removes the parent directory when it becomes empty."""
    pkg_dir = tmp_path / "packages" / "aa" / "bb"
    pkg_dir.mkdir(parents=True)
    pkg_file = pkg_dir / "pkg-1.0.whl"
    pkg_file.write_bytes(b"x")

    storage_backend = _make_fs_storage(tmp_path)
    storage_backend.delete_package_file(pkg_file)

    assert not pkg_file.exists()
    assert not pkg_dir.exists()


def test_parse_release_file_size() -> None:
    assert _parse_release_file_size({"filename": "a.whl", "size": 1024}, "pkg") == 1024
    assert _parse_release_file_size({"filename": "a.whl"}, "pkg") is None
    assert _parse_release_file_size({"filename": "a.whl", "size": "bad"}, "pkg") is None
    assert _parse_release_file_size({"filename": "a.whl", "size": -5}, "pkg") is None


def test_download_stats_addition() -> None:
    left = DownloadStats(file_count=1, total_bytes=100, unknown_size_count=1)
    right = DownloadStats(file_count=2, total_bytes=250, unknown_size_count=0)
    total = left + right
    assert total == DownloadStats(file_count=3, total_bytes=350, unknown_size_count=1)


def test_log_download_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_download_summary(DownloadStats(), dry_run=True)
    assert "[DRY RUN] No files would be downloaded" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO):
        log_download_summary(
            DownloadStats(file_count=2, total_bytes=2048),
            dry_run=True,
        )
    assert "Would download 2 files" in caplog.text
    assert "~2 KiB" in caplog.text
    assert "unknown sizes" not in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        log_download_summary(
            DownloadStats(
                file_count=1,
                total_bytes=0,
                unknown_size_count=1,
            ),
            dry_run=True,
        )

    assert "unknown sizes in metadata" in caplog.text


def test_log_download_summary_live_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_download_summary(
            DownloadStats(file_count=2, total_bytes=2048),
            dry_run=False,
        )

    assert "[DRY RUN]" not in caplog.text
    assert "Downloaded 2 files (2 KiB)" in caplog.text


@pytest.mark.asyncio
async def test_verify_dry_run_accumulates_download_stats(tmp_path: Path) -> None:
    """verify() adds missing release files to stats when dry_run=True."""
    import hashlib

    content = b"wheel content"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    class FakeArgs:
        dry_run = True
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))
    stats = DownloadStats()

    await verify(
        master,
        fc,  # type: ignore[arg-type]
        storage_backend,
        "mypackage",
        tmp_path,
        [],
        FakeArgs(),  # type: ignore[arg-type]
        stats=stats,
    )

    assert stats == DownloadStats(
        file_count=1, total_bytes=len(content), unknown_size_count=0
    )


@pytest.mark.asyncio
async def test_verify_dry_run_unknown_size_in_stats(tmp_path: Path) -> None:
    """Release files missing size metadata are skipped."""
    import hashlib

    sha256 = hashlib.sha256(b"wheel content").hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, None)
    )

    class FakeArgs:
        dry_run = True
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))
    stats = DownloadStats()

    await verify(
        master,
        fc,  # type: ignore[arg-type]
        storage_backend,
        "mypackage",
        tmp_path,
        [],
        FakeArgs(),  # type: ignore[arg-type]
        stats=stats,
    )

    assert stats == DownloadStats()


@pytest.mark.asyncio
async def test_verify_skips_invalid_release_file_size(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """verify() skips release files whose size metadata is not a valid integer."""
    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        json.dumps(
            {
                "info": {"name": "mypackage"},
                "releases": {
                    "1.0": [
                        {
                            "filename": "mypackage-1.0.whl",
                            "url": (
                                "https://files.pythonhosted.org/packages/aa/bb/cc/"
                                "mypackage-1.0.whl"
                            ),
                            "size": "not-a-number",
                            "digests": {"sha256": "abc"},
                            "upload_time_iso_8601": "2024-01-01T00:00:00Z",
                        }
                    ]
                },
            }
        )
    )

    class FakeArgs:
        dry_run = True
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))
    all_files: list[PATH_TYPES] = []
    stats = DownloadStats()

    with caplog.at_level(logging.ERROR):
        await verify(
            master,
            fc,  # type: ignore[arg-type]
            storage_backend,
            "mypackage",
            tmp_path,
            all_files,
            FakeArgs(),  # type: ignore[arg-type]
            stats=stats,
        )

    assert all_files == []
    assert stats == DownloadStats()
    assert "Invalid size" in caplog.text


@pytest.mark.asyncio
async def test_verify_producer_merges_dry_run_download_stats(
    tmp_path: Path,
) -> None:
    """verify_producer() merges per-consumer dry-run stats across verifiers."""
    import hashlib

    fc = _verify_mirror_config(tmp_path, verifiers="2")
    storage_backend = FilesystemStorage(config=fc)
    master = Master("https://unittest.org")

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    packages = (
        ("pkgone", 1000),
        ("pkgtwo", 2500),
    )
    for name, size in packages:
        url = f"https://files.pythonhosted.org/packages/aa/bb/{name}.whl"
        sha256 = hashlib.sha256(b"content").hexdigest()
        (jsonpath / name).write_text(_pkg_json(f"{name}.whl", url, sha256, size))

    stats = await verify_producer(
        master,
        fc,
        storage_backend,
        [],
        tmp_path,
        [name for name, _ in packages],
        VerifyArgs(),  # type: ignore[arg-type]
        None,
    )

    assert stats == DownloadStats(file_count=2, total_bytes=3500, unknown_size_count=0)


@pytest.mark.asyncio
async def test_verify_producer_returns_empty_stats_without_dry_run(
    tmp_path: Path,
) -> None:
    fc = _verify_mirror_config(tmp_path)
    storage_backend = FilesystemStorage(config=fc)

    class LiveRunArgs:
        dry_run = False
        json_update = False
        delete = False
        workers = 1

    stats = await verify_producer(
        Master("https://unittest.org"),
        fc,
        storage_backend,
        [],
        tmp_path,
        [],
        LiveRunArgs(),  # type: ignore[arg-type]
        None,
    )

    assert stats == DownloadStats()


@pytest.mark.asyncio
async def test_verify_producer_dry_run_no_downloads_when_files_valid(
    tmp_path: Path,
) -> None:
    """verify_producer() reports zero downloads when all expected files exist."""
    import hashlib

    content = b"wheel content"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"
    artifact = tmp_path / "web" / convert_url_to_path(url)
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(content)

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    fc = _verify_mirror_config(tmp_path)
    storage_backend = FilesystemStorage(config=fc)

    stats = await verify_producer(
        Master("https://unittest.org"),
        fc,
        storage_backend,
        [],
        tmp_path,
        ["mypackage"],
        VerifyArgs(),  # type: ignore[arg-type]
        None,
    )

    assert stats == DownloadStats()


@pytest.mark.asyncio
async def test_verify_records_stats_when_not_dry_run(tmp_path: Path) -> None:
    import hashlib

    content = b"wheel content"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    class LiveRunArgs:
        dry_run = False
        json_update = False
        delete = False
        workers = 1

    fc = FakeConfig()
    storage_backend = _make_fs_storage(tmp_path)
    master = Master(fc.get("mirror", "master"))
    stats = DownloadStats()

    with mock.patch("bandersnatch.verify.fetch_and_store", return_value=len(content)):
        await verify(
            master,
            fc,  # type: ignore[arg-type]
            storage_backend,
            "mypackage",
            tmp_path,
            [],
            LiveRunArgs(),  # type: ignore[arg-type]
            stats=stats,
        )

    assert stats == DownloadStats(
        file_count=1,
        total_bytes=len(content),
        unknown_size_count=0,
    )


@pytest.mark.asyncio
async def test_metadata_verify_dry_run_logs_download_summary(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """metadata_verify() logs the dry-run download summary after verify_producer()."""
    import hashlib

    content = b"wheel content"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    cfg = _verify_mirror_config(tmp_path)

    class Args:
        dry_run = True
        delete = False
        json_update = False
        workers = 1

    with caplog.at_level(logging.INFO):
        assert (await metadata_verify(cfg, Args())) == 0  # type: ignore[arg-type]

    assert "Would download 1 files (~" in caplog.text


@pytest.mark.asyncio
async def test_metadata_verify_dry_run_no_downloads_when_files_valid(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """metadata_verify() logs zero-download summary when mirror is complete."""
    import hashlib

    content = b"wheel content"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"
    artifact = tmp_path / "web" / convert_url_to_path(url)
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(content)

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    class Args:
        dry_run = True
        delete = False
        json_update = False
        workers = 1

    with caplog.at_level(logging.INFO):
        assert (
            await metadata_verify(_verify_mirror_config(tmp_path), Args())  # type: ignore[arg-type]
        ) == 0

    assert "[DRY RUN] No files would be downloaded" in caplog.text


@pytest.mark.asyncio
async def test_metadata_verify_live_run_logs_download_summary(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """metadata_verify() logs the live-run download summary after verify_producer()."""
    import hashlib

    content = b"wheel content"
    sha256 = hashlib.sha256(content).hexdigest()
    url = "https://files.pythonhosted.org/packages/aa/bb/cc/mypackage-1.0.whl"

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    (jsonpath / "mypackage").write_text(
        _pkg_json("mypackage-1.0.whl", url, sha256, len(content))
    )

    cfg = _verify_mirror_config(tmp_path)

    class Args:
        dry_run = False
        delete = False
        json_update = False
        workers = 1

    with caplog.at_level(logging.INFO):
        with mock.patch(
            "bandersnatch.verify.fetch_and_store", return_value=len(content)
        ):
            assert (await metadata_verify(cfg, Args())) == 0  # type: ignore[arg-type]

    assert "Downloaded 1 files (" in caplog.text
    assert "[DRY RUN]" not in caplog.text


if __name__ == "__main__":
    pytest.main(sys.argv)
