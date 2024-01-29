import configparser
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
from _pytest.monkeypatch import MonkeyPatch
from aiohttp.client_exceptions import ClientResponseError, ServerTimeoutError

import bandersnatch
from bandersnatch.master import Master
from bandersnatch.utils import convert_url_to_path, find
from bandersnatch_storage_plugins.filesystem import pathlib

from bandersnatch.verify import (  # isort:skip
    get_latest_json,
    delete_unowned_files,
    metadata_verify,
    verify_producer,
    verify,
)


async def do_nothing(*args: Any, **kwargs: Any) -> None:
    pass


async def fake_fetch(_: str, save_path: Path, *__: Any) -> None:
    save_path.write_text("fake text")


def some_dirs(*args: Any, **kwargs: Any) -> list[str]:
    return ["/data/pypi/web/json/bandersnatch", "/data/pypi/web/json/black"]


def some_paths(*_: Any, **__: Any) -> list[Path]:
    return [Path("/data/pypi/web/json/bandersnatch"), Path("/data/pypi/web/json/black")]


class FakeConfig:
    def get(self, section: str, item: str) -> str:
        if section == "mirror":
            if item == "directory":
                return "/data/pypi"
            if item == "master":
                return "https://unittest.org"
            if item == "storage-backend":
                return "filesystem"
        return ""

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
                    "sha256": "b35e87b5838011a3637be660e4238af9a55e4edc74404c990f7a558e7f416658",  # noqa: E501
                    "url": "https://test.pypi.org/packages/8f/1a/6969/bandersnatch-0.6.9.tar.gz",  # noqa: E501
                }
            },
            "black": {
                "black-2018.6.9": {
                    "filename": "black-2018.6.9.tar.gz",
                    "contents": "69",
                    "sha256": "b35e87b5838011a3637be660e4238af9a55e4edc74404c990f7a558e7f416658",  # noqa: E501
                    "url": "https://test.pypi.org/packages/8f/1a/6969/black-2018.6.9.tar.gz",  # noqa: E501
                },
                "black-2019.6.9": {
                    "filename": "black-2019.6.9.tar.gz",
                    "contents": "1469",
                    "sha256": "c896470f5975bd5dc7d173871faca19848855b01bacf3171e9424b8a993b528b",  # noqa: E501
                    "url": "https://test.pypi.org/packages/8f/1a/1aa0/black-2019.6.9.tar.gz",  # noqa: E501
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
async def test_verify_producer(monkeypatch: MonkeyPatch) -> None:
    fm = FakeMirror("test_async_verify")
    fc = configparser.ConfigParser()
    fc["mirror"] = {}
    fc["mirror"]["verifiers"] = "2"
    master = Master("https://unittest.org")
    json_files = ["web/json/bandersnatch", "web/json/black"]
    monkeypatch.setattr(bandersnatch.verify, "verify", do_nothing)
    await verify_producer(master, fc, [], fm.mirror_base, json_files, mock.Mock(), None)


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
web{0}simple{0}black{0}index.html""".format(
        os.sep
    )
    fm = FakeMirror("_mirror_base_test")
    assert expected_mirror_layout == find(str(fm.mirror_base), True)
    fm.clean_up()


@pytest.mark.asyncio
async def test_delete_unowned_files() -> None:
    executor = ThreadPoolExecutor(max_workers=2)
    fm = FakeMirror("_test_delete_files")
    # Leave out black-2018.6.9.tar.gz so it gets deleted
    all_pkgs = [
        fm.mirror_base / "web/packages/8f/1a/1aa0/black-2019.6.9.tar.gz",
        fm.mirror_base / "web/packages/8f/1a/6969/bandersnatch-0.6.9.tar.gz",
    ]
    await delete_unowned_files(fm.mirror_base, executor, all_pkgs, True)
    await delete_unowned_files(fm.mirror_base, executor, all_pkgs, False)
    deleted_path = fm.mirror_base / "web/packages/8f/1a/6969/black-2018.6.9.tar.gz"
    assert not deleted_path.exists()
    fm.clean_up()


@pytest.mark.asyncio
async def test_get_latest_json(monkeypatch: MonkeyPatch) -> None:
    executor = ThreadPoolExecutor(max_workers=2)
    json_path = Path(gettempdir()) / f"unittest_{os.getpid()}.json"
    master = Master("https://unittest.org")
    monkeypatch.setattr(master, "url_fetch", fake_fetch)
    await get_latest_json(master, json_path, executor)
    assert json_path.read_text() == "fake text"


@pytest.mark.asyncio
async def test_metadata_verify(monkeypatch: MonkeyPatch) -> None:
    class FakeArgs:
        delete = True
        dry_run = True
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()
    monkeypatch.setattr(bandersnatch.verify, "verify_producer", do_nothing)
    monkeypatch.setattr(bandersnatch.verify, "delete_unowned_files", do_nothing)
    monkeypatch.setattr(pathlib.Path, "iterdir", some_paths)
    await metadata_verify(fc, fa)  # type: ignore


@pytest.mark.asyncio
async def test_get_latest_json_timeout(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    class FakeArgs:
        delete = True
        dry_run = False
        json_update = True
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()

    master = Master(fc.get("mirror", "master"))
    url_fetch_timeout = AsyncMock(side_effect=ServerTimeoutError)
    monkeypatch.setattr(master, "url_fetch", url_fetch_timeout)

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True)
    jsonfile = jsonpath / "bandersnatch"
    jsonfile.touch()
    all_package_files: list[Path] = []

    await verify(
        master, fc, "bandersnatch", tmp_path, all_package_files, fa  # type: ignore
    )  # noqa: E501
    assert jsonfile.exists()
    assert not all_package_files


@pytest.mark.asyncio
async def test_get_latest_json_404(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    class FakeArgs:
        delete = True
        dry_run = False
        json_update = True
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()

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
        master, fc, "bandersnatch", tmp_path, all_package_files, fa  # type: ignore # noqa: E501
    )
    assert not jsonfile.exists()
    assert not all_package_files


@pytest.mark.asyncio
async def test_verify_url_exception(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    class FakeArgs:
        delete = True
        dry_run = False
        json_update = False
        workers = 2

    fa = FakeArgs()
    fc = FakeConfig()

    master = Master(fc.get("mirror", "master"))
    url_fetch_404 = AsyncMock(
        side_effect=ClientResponseError(status=404, history=(), request_info=None)
    )
    monkeypatch.setattr(master, "url_fetch", url_fetch_404)

    jsonpath = tmp_path / "web" / "json"
    jsonpath.mkdir(parents=True, exist_ok=True)
    jsonfile = jsonpath / "bandersnatch"
    with jsonfile.open("w") as f:
        f.write(
            '{"releases":{"1.0":["url":"https://unittests.org/packages/a0/a0/a0a0/package-1.0.0.exe"}]}}'  # noqa: E501
        )
    all_package_files: list[Path] = []

    await verify(master, fc, "bandersnatch", tmp_path, all_package_files, fa)  # type: ignore # noqa: E501
    assert jsonfile.exists()
    assert not all_package_files


if __name__ == "__main__":
    pytest.main(sys.argv)
