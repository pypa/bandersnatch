import os
from argparse import Namespace
from configparser import ConfigParser
from json import loads
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

import pytest
from aiohttp import ClientResponseError
from pytest import MonkeyPatch

from bandersnatch.delete import delete_packages, delete_path, delete_simple_page
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.utils import find

EXPECTED_WEB_BEFORE_DELETION = """\
json
json{0}cooper
json{0}unittest
packages
packages{0}69
packages{0}69{0}cooper-6.9.tar.gz
packages{0}69{0}unittest-6.9.tar.gz
packages{0}7b
packages{0}7b{0}cooper-6.9-py3-none-any.whl
packages{0}7b{0}unittest-6.9-py3-none-any.whl
pypi
pypi{0}cooper
pypi{0}cooper{0}json
pypi{0}unittest
pypi{0}unittest{0}json
simple
simple{0}cooper
simple{0}cooper{0}index.html
simple{0}unittest
simple{0}unittest{0}index.html\
""".format(os.sep)
EXPECTED_WEB_AFTER_DELETION = """\
json
packages
packages{0}69
packages{0}7b
pypi
simple\
""".format(os.sep)
MOCK_JSON_TEMPLATE = """{
    "releases": {
        "6.9": [
            {"url": "https://files.ph.org/packages/7b/PKGNAME-6.9-py3-none-any.whl"},
            {"url": "https://files.ph.org/packages/69/PKGNAME-6.9.tar.gz"}
        ]
    }
}
"""


def _fake_args() -> Namespace:
    return Namespace(dry_run=True, pypi_packages=["cooper", "unittest"], workers=0)


def _fake_config() -> ConfigParser:
    cp = ConfigParser()
    cp.add_section("mirror")
    cp["mirror"]["directory"] = "/tmp/unittest"
    cp["mirror"]["workers"] = "1"
    cp["mirror"]["storage-backend"] = "filesystem"
    cp["mirror"]["hash-index"] = "true"
    return cp


@pytest.mark.asyncio
async def test_delete_path() -> None:
    with TemporaryDirectory() as td:
        td_path = Path(td)
        fake_path = td_path / "unittest-file.tgz"
        with patch("bandersnatch.delete.logger.info") as mock_log:
            assert await delete_path(fake_path, True) == 0
            assert mock_log.call_count == 1

        with patch("bandersnatch.delete.logger.debug") as mock_log:
            assert await delete_path(fake_path, False) == 0
            assert mock_log.call_count == 1

        fake_path.touch()
        # Remove file
        assert await delete_path(fake_path, False) == 0
        # File should be gone - We should log that via debug
        with patch("bandersnatch.delete.logger.debug") as mock_log:
            assert await delete_path(fake_path, False) == 0
            assert mock_log.call_count == 1


@pytest.mark.asyncio
async def test_delete_packages() -> None:
    args = _fake_args()
    config = _fake_config()
    master = Master("https://unittest.org")

    with TemporaryDirectory() as td:
        td_path = Path(td)
        config["mirror"]["directory"] = td
        web_path = td_path / "web"
        json_path = web_path / "json"
        json_path.mkdir(parents=True)
        pypi_path = web_path / "pypi"
        pypi_path.mkdir(parents=True)
        simple_path = web_path / "simple"

        # Setup web tree with some json, package index.html + fake blobs
        for package_name in args.pypi_packages:
            package_simple_path = simple_path / package_name
            package_simple_path.mkdir(parents=True)
            package_index_path = package_simple_path / "index.html"
            package_index_path.touch()

            package_json_str = MOCK_JSON_TEMPLATE.replace("PKGNAME", package_name)
            package_json_path = json_path / package_name
            with package_json_path.open("w") as pjfp:
                pjfp.write(package_json_str)
            legacy_json_path = pypi_path / package_name / "json"
            legacy_json_path.parent.mkdir()
            legacy_json_path.write_bytes(package_json_path.read_bytes())

            package_json = loads(package_json_str)
            for _version, blobs in package_json["releases"].items():
                for blob in blobs:
                    url_parts = urlparse(blob["url"])
                    blob_path = web_path / url_parts.path[1:]
                    blob_path.parent.mkdir(parents=True, exist_ok=True)
                    blob_path.touch()

        # See we have a correct mirror setup
        assert find(web_path) == EXPECTED_WEB_BEFORE_DELETION

        args.dry_run = True
        assert await delete_packages(config, args, master) == 0

        args.dry_run = False
        with patch("bandersnatch.delete.logger.info") as mock_log:
            assert await delete_packages(config, args, master) == 0
            assert mock_log.call_count == 1

        # See we've deleted it all
        assert find(web_path) == EXPECTED_WEB_AFTER_DELETION


@pytest.mark.asyncio
async def test_delete_packages_no_exist() -> None:
    args = _fake_args()
    master = Master("https://unittest.org")
    with patch("bandersnatch.delete.logger.error") as mock_log:
        assert await delete_packages(_fake_config(), args, master) == 0
        assert mock_log.call_count == len(args.pypi_packages)


@pytest.mark.asyncio
async def test_delete_simple_page() -> None:
    with TemporaryDirectory() as td:
        td_path = Path(td)
        packages = ["foo", "bar"]
        # creating simple pages
        for p in packages:
            index = td_path / p
            index_hashed = td_path / p[0] / p
            json_dir = index / "json"
            hashed_json_dir = index_hashed / "json"
            index.mkdir(parents=True)
            index_hashed.mkdir(parents=True)
            json_dir.mkdir(parents=True)
            hashed_json_dir.mkdir(parents=True)
            (index / "index.html").touch()
            (index_hashed / "index.html").touch()
        await delete_simple_page(td_path, "foo", dry_run=False)
        assert not (td_path / "foo" / "index.html").exists()
        assert not (td_path / "foo" / "json").exists()
        assert (td_path / "f" / "foo").exists()
        assert (td_path / "f" / "foo" / "index.html").exists()
        assert (td_path / "bar").exists()
        assert (td_path / "bar" / "index.html").exists()
        await delete_simple_page(td_path, "foo", hash_index=True, dry_run=False)
        assert not (td_path / "f" / "foo" / "index.html").exists()
        assert not (td_path / "f" / "foo" / "json").exists()


@pytest.mark.asyncio
async def test_delete_package_json_not_exists(
    mirror: BandersnatchMirror, monkeypatch: MonkeyPatch
) -> None:
    master = mirror.master
    url_fetch_404 = AsyncMock(
        side_effect=ClientResponseError(status=404, history=(), request_info=None)
    )
    monkeypatch.setattr(master, "url_fetch", url_fetch_404)
    package_simple_dir = mirror.webdir / "simple" / "cooper"
    package_simple_dir.mkdir()
    index_page = package_simple_dir / "index.html"
    index_page.touch()
    assert index_page.exists()
    args = _fake_args()
    args.dry_run = False
    config = _fake_config()
    config["mirror"]["directory"] = str(mirror.homedir)
    assert await delete_packages(config, args, master) == 0
    assert not index_page.exists()
    assert not package_simple_dir.exists()
