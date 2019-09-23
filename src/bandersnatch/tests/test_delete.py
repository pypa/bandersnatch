import asyncio
from argparse import Namespace
from configparser import ConfigParser
from json import loads
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlparse

from bandersnatch.delete import delete_packages, delete_path
from bandersnatch.utils import find

EXPECTED_WEB_BEFORE_DELETION = """\
json
json/cooper.json
json/unittest.json
packages
packages/69
packages/69/cooper-6.9.tar.gz
packages/69/unittest-6.9.tar.gz
packages/7b
packages/7b/cooper-6.9-py3-none-any.whl
packages/7b/unittest-6.9-py3-none-any.whl
simple
simple/cooper
simple/cooper/index.html
simple/unittest
simple/unittest/index.html\
"""
EXPECTED_WEB_AFTER_DELETION = """\
json
packages
packages/69
packages/7b
simple\
"""
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
    return cp


def test_delete_path() -> None:
    with TemporaryDirectory() as td:
        td_path = Path(td)
        fake_path = td_path / "unittest-file.tgz"
        with patch("bandersnatch.delete.logger.info") as mock_log:
            assert delete_path(fake_path, True) == 0
            assert mock_log.call_count == 1

        with patch("bandersnatch.delete.logger.debug") as mock_log:
            assert delete_path(fake_path, False) == 0
            assert mock_log.call_count == 1

        fake_path.touch()
        # Remove file
        assert delete_path(fake_path, False) == 0
        # File should be gone - We should log that via debug
        with patch("bandersnatch.delete.logger.debug") as mock_log:
            assert delete_path(fake_path, False) == 0
            assert mock_log.call_count == 1


def test_delete_packages() -> None:
    args = _fake_args()
    config = _fake_config()
    loop = asyncio.get_event_loop()

    with TemporaryDirectory() as td:
        td_path = Path(td)
        config["mirror"]["directory"] = td
        web_path = td_path / "web"
        json_path = web_path / "json"
        json_path.mkdir(parents=True)
        simple_path = web_path / "simple"

        # Setup web tree with some json, package index.html + fake blobs
        for package_name in args.pypi_packages:
            package_simple_path = simple_path / package_name
            package_simple_path.mkdir(parents=True)
            package_index_path = package_simple_path / "index.html"
            package_index_path.touch()

            package_json_str = MOCK_JSON_TEMPLATE.replace("PKGNAME", package_name)
            package_json_path = json_path / f"{package_name}.json"
            with package_json_path.open("w") as pjfp:
                pjfp.write(package_json_str)

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
        assert loop.run_until_complete(delete_packages(config, args)) == 0

        args.dry_run = False
        with patch("bandersnatch.delete.logger.info") as mock_log:
            assert loop.run_until_complete(delete_packages(config, args)) == 0
            assert mock_log.call_count == 1

        # See we've deleted it all
        assert find(web_path) == EXPECTED_WEB_AFTER_DELETION


def test_delete_packages_no_exist() -> None:
    loop = asyncio.get_event_loop()
    args = _fake_args()
    with patch("bandersnatch.delete.logger.error") as mock_log:
        assert loop.run_until_complete(delete_packages(_fake_config(), args)) == 0
        assert mock_log.call_count == len(args.pypi_packages)
