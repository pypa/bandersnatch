import os
import os.path
import re
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir

import aiohttp
import pytest

from bandersnatch.utils import (  # isort:skip
    convert_url_to_path,
    hash,
    recursive_find_files,
    rewrite,
    unlink_parent_dir,
    user_agent,
)


def test_convert_url_to_path():
    assert (
        "packages/8f/1a/1aa000db9c5a799b676227e845d2b64fe725328e05e3d3b30036f"
        + "50eb316/peerme-1.0.0-py36-none-any.whl"
        == convert_url_to_path(
            "https://files.pythonhosted.org/packages/8f/1a/1aa000db9c5a799b67"
            + "6227e845d2b64fe725328e05e3d3b30036f50eb316/"
            + "peerme-1.0.0-py36-none-any.whl"
        )
    )


def test_hash():
    sample = os.path.join(os.path.dirname(__file__), "sample")
    assert hash(sample, function="md5") == "125765989403df246cecb48fa3e87ff8"
    assert hash(sample, function="sha256") == (
        "95c07c174663ebff531eed59b326ebb3fa95f418f680349fc33b07dfbcf29f18"
    )
    assert hash(sample) == (
        "95c07c174663ebff531eed59b326ebb3fa95f418f680349fc33b07dfbcf29f18"
    )


def test_find_files():
    with TemporaryDirectory() as td:
        td_path = Path(td)
        td_sub_path = td_path / "aDir"
        td_sub_path.mkdir()

        expected_found_files = {td_path / "file1", td_sub_path / "file2"}
        for afile in expected_found_files:
            with afile.open("w") as afp:
                afp.write("PyPA ftw!")

        found_files = set()
        recursive_find_files(found_files, td_path)
        assert found_files == expected_found_files


def test_rewrite(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    with open("sample", "w") as f:
        f.write("bsdf")
    with rewrite("sample") as f:
        f.write("csdf")
    assert open("sample").read() == "csdf"
    mode = os.stat("sample").st_mode
    assert oct(mode) == "0o100644"


def test_rewrite_fails(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    with open("sample", "w") as f:
        f.write("bsdf")
    with pytest.raises(Exception):
        with rewrite("sample") as f:
            f.write("csdf")
            raise Exception()
    assert open("sample").read() == "bsdf"


def test_rewrite_nonexisting_file(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    with rewrite("sample", "w") as f:
        f.write("csdf")
    with open("sample") as f:
        assert f.read() == "csdf"


def test_unlink_parent_dir():
    adir = Path(gettempdir()) / f"tb.{os.getpid()}"
    adir.mkdir()
    afile = adir / "file1"
    afile.touch()
    unlink_parent_dir(afile)
    assert not adir.exists()


def test_user_agent():
    assert re.match(
        r"bandersnatch/[0-9]\.[0-9]\.[0-9]\.?d?e?v?[0-9]? \(.*\) "
        + fr"\(aiohttp {aiohttp.__version__}\)",
        user_agent(),
    )
