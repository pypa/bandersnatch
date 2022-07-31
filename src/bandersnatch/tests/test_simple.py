from configparser import ConfigParser
from os import sep
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from bandersnatch import utils
from bandersnatch.package import Package
from bandersnatch.simple import InvalidSimpleFormat, SimpleAPI, SimpleFormat
from bandersnatch.storage import Storage
from bandersnatch.tests.test_simple_fixtures import (
    EXPECTED_SIMPLE_GLOBAL_JSON_PRETTY,
    EXPECTED_SIMPLE_SIXTYNINE_JSON,
    EXPECTED_SIMPLE_SIXTYNINE_JSON_PRETTY,
    SIXTYNINE_METADATA,
)
from bandersnatch_storage_plugins.filesystem import FilesystemStorage


def test_format_invalid() -> None:
    with pytest.raises(InvalidSimpleFormat):
        SimpleAPI(Storage(), "l33t", [], "digest", False, None)


def test_format_valid() -> None:
    s = SimpleAPI(Storage(), "ALL", [], "digest", False, None)
    assert s.format == SimpleFormat.ALL


def test_json_package_page() -> None:
    s = SimpleAPI(Storage(), SimpleFormat.JSON, [], "digest", False, None)
    p = Package("69")
    p._metadata = SIXTYNINE_METADATA
    assert EXPECTED_SIMPLE_SIXTYNINE_JSON == s.generate_json_simple_page(p)
    # Only testing pretty so it's easier for humans ...
    assert EXPECTED_SIMPLE_SIXTYNINE_JSON_PRETTY == s.generate_json_simple_page(
        p, pretty=True
    )


def test_json_index_page() -> None:
    c = ConfigParser()
    c.add_section("mirror")
    c["mirror"]["workers"] = "1"
    s = SimpleAPI(
        FilesystemStorage(config=c), SimpleFormat.ALL, [], "digest", False, None
    )
    with TemporaryDirectory() as td:
        td_path = Path(td)
        simple_dir = td_path / "simple"
        sixtynine_dir = simple_dir / "69"
        foo_dir = simple_dir / "foo"
        for a_dir in (sixtynine_dir, foo_dir):
            a_dir.mkdir(parents=True)

        sixtynine_html = sixtynine_dir / "index.html"
        foo_html = foo_dir / "index.html"
        for a_file in (sixtynine_html, foo_html):
            a_file.touch()

        s.sync_index_page(True, td_path, 12345, pretty=True)
        # See we get the files we expect on the file system
        # index.html is needed to trigger the global index finding the package
        assert """\
simple
simple{0}69
simple{0}69{0}index.html
simple{0}foo
simple{0}foo{0}index.html
simple{0}index.html
simple{0}index.v1_html
simple{0}index.v1_json""".format(
            sep
        ) == utils.find(
            td_path
        )
        # Check format of JSON
        assert (simple_dir / "index.v1_json").open(
            "r"
        ).read() == EXPECTED_SIMPLE_GLOBAL_JSON_PRETTY
