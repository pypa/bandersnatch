import asyncio
from concurrent.futures import ThreadPoolExecutor
from os import getpid
from pathlib import Path
from shutil import rmtree
from tempfile import gettempdir
from typing import List

import bandersnatch
from bandersnatch.utils import convert_url_to_path, find

from bandersnatch.verify import (  # isort:skip
    _get_latest_json,
    async_verify,
    delete_files,
    metadata_verify,
)


async def do_nothing(*args, **kwargs) -> None:
    pass


def some_dirs(*args, **kwargs) -> List[str]:
    return ["/data/pypi/web/json/bandersnatch", "/data/pypi/web/json/black"]


class FakeArgs:
    delete = True
    dry_run = True
    workers = 2


class FakeConfig:
    def get(self, section: str, item: str) -> str:
        if section == "mirror":
            if item == "directory":
                return "/data/pypi"
            if item == "master":
                return "https://pypi.org/simple/"
        return ""


# TODO: Support testing sharded simple dirs
class FakeMirror:
    def __init__(self, entropy: str = "") -> None:
        self.mirror_base = Path(gettempdir()) / f"pypi_unittest_{getpid()}{entropy}"
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

    def clean_up(self):
        if self.mirror_base.exists():
            rmtree(self.mirror_base)

    def setup_json(self):
        for pkg in self.pypi_packages.keys():
            pkg_json = self.json_path / pkg
            pkg_json.touch()
            pkg_legacy_json = self.pypi_path / pkg / "json"
            pkg_legacy_json.parent.mkdir()
            pkg_legacy_json.symlink_to(str(pkg_json))

    def setup_packages(self):
        for _pkg, dists in self.pypi_packages.items():
            for _version, metadata in dists.items():
                dist_file = self.web_base / convert_url_to_path(metadata["url"])
                dist_file.parent.mkdir(exist_ok=True, parents=True)
                with dist_file.open("w") as dfp:
                    dfp.write(metadata["contents"])

    def setup_simple(self):
        for pkg in self.pypi_packages.keys():
            pkg_dir = self.simple_path / pkg
            pkg_dir.mkdir()
            index_path = pkg_dir / "index.html"
            index_path.touch()


def test_async_verify(monkeypatch):
    fm = FakeMirror("test_async_verify")
    json_files = ["web/json/bandersnatch", "web/json/black"]
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(bandersnatch.verify, "verify", do_nothing)
    loop.run_until_complete(
        async_verify(None, [], fm.mirror_base, json_files, None, None)
    )


def test_fake_mirror():
    expected_mirror_layout = """\
web
web/json
web/json/bandersnatch
web/json/black
web/packages
web/packages/8f
web/packages/8f/1a
web/packages/8f/1a/1aa0
web/packages/8f/1a/1aa0/black-2019.6.9.tar.gz
web/packages/8f/1a/6969
web/packages/8f/1a/6969/bandersnatch-0.6.9.tar.gz
web/packages/8f/1a/6969/black-2018.6.9.tar.gz
web/pypi
web/pypi/bandersnatch
web/pypi/bandersnatch/json
web/pypi/black
web/pypi/black/json
web/simple
web/simple/bandersnatch
web/simple/bandersnatch/index.html
web/simple/black
web/simple/black/index.html"""
    fm = FakeMirror("_mirror_base_test")
    assert expected_mirror_layout == find(str(fm.mirror_base), True)
    fm.clean_up()


def test_delete_files() -> None:
    executor = ThreadPoolExecutor(max_workers=2)
    fm = FakeMirror("_test_delete_files")
    # Leave out black-2018.6.9.tar.gz so it gets deleted
    all_pkgs = [
        fm.mirror_base / "web/packages/8f/1a/1aa0/black-2019.6.9.tar.gz",
        fm.mirror_base / "web/packages/8f/1a/6969/bandersnatch-0.6.9.tar.gz",
    ]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(delete_files(fm.mirror_base, executor, all_pkgs, True))
    loop.run_until_complete(delete_files(fm.mirror_base, executor, all_pkgs, False))
    deleted_path = fm.mirror_base / "web/packages/8f/1a/6969/black-2018.6.9.tar.gz"
    assert not deleted_path.exists()
    fm.clean_up()


def test_get_latest_json(monkeypatch):
    config = FakeConfig()
    executor = ThreadPoolExecutor(max_workers=2)
    json_path = Path(gettempdir()) / f"unittest_{getpid()}.json"
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(bandersnatch.verify, "url_fetch", do_nothing)
    loop.run_until_complete(_get_latest_json(json_path, config, executor))


def test_metadata_verify(monkeypatch):
    fa = FakeArgs()
    fc = FakeConfig()
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(bandersnatch.verify, "async_verify", do_nothing)
    monkeypatch.setattr(bandersnatch.verify, "delete_files", do_nothing)
    monkeypatch.setattr(bandersnatch.verify.os, "listdir", some_dirs)
    loop.run_until_complete(metadata_verify(fc, fa))
