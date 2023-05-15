import os
import os.path
import re
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory, gettempdir

import aiohttp
import pytest
from _pytest.monkeypatch import MonkeyPatch

from bandersnatch.utils import (  # isort:skip
    bandersnatch_safe_name,
    convert_url_to_path,
    hash,
    parse_version,
    find_all_files,
    removeprefix,
    rewrite,
    unlink_parent_dir,
    user_agent,
    WINDOWS,
)


def test_convert_url_to_path() -> None:
    assert (
        "packages/8f/1a/1aa000db9c5a799b676227e845d2b64fe725328e05e3d3b30036f"
        + "50eb316/peerme-1.0.0-py36-none-any.whl"
        == convert_url_to_path(
            "https://files.pythonhosted.org/packages/8f/1a/1aa000db9c5a799b67"
            + "6227e845d2b64fe725328e05e3d3b30036f50eb316/"
            + "peerme-1.0.0-py36-none-any.whl"
        )
    )


def test_hash() -> None:
    expected_md5 = "b2855c4a4340dad73d9d870630390885"
    expected_sha256 = "a2a5e3823bf4cccfaad4e2f0fbabe72bc8c3cf78bc51eb396b5c7af99e17f07a"
    with NamedTemporaryFile(delete=False) as ntf:
        ntf_path = Path(ntf.name)
        ntf.close()
        try:
            with ntf_path.open("w") as ntfp:
                ntfp.write("Unittest File for hashing Fun!")

            assert hash(ntf_path, function="md5") == expected_md5
            assert hash(ntf_path, function="sha256") == expected_sha256
            assert hash(ntf_path) == expected_sha256
        finally:
            if ntf_path.exists():
                ntf_path.unlink()


def test_find_files() -> None:
    with TemporaryDirectory() as td:
        td_path = Path(td)
        td_sub_path = td_path / "aDir"
        td_sub_path.mkdir()

        expected_found_files = {td_path / "file1", td_sub_path / "file2"}
        for afile in expected_found_files:
            with afile.open("w") as afp:
                afp.write("PyPA ftw!")

        found_files: set[Path] = set()
        find_all_files(found_files, td_path)
        assert found_files == expected_found_files


def test_rewrite(tmpdir: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmpdir)
    with open("sample", "w") as f:
        f.write("bsdf")
    with rewrite("sample") as f:
        f.write("csdf")
    assert open("sample").read() == "csdf"
    mode = os.stat("sample").st_mode
    # chmod doesn't work on windows machines. Permissions are pinned at 666
    if not WINDOWS:
        assert oct(mode) == "0o100644"


def test_rewrite_fails(tmpdir: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmpdir)
    with open("sample", "w") as f:
        f.write("bsdf")
    with pytest.raises(OSError):
        with rewrite("sample", "r") as f:
            f.write("csdf")
    assert open("sample").read() == "bsdf"


def test_rewrite_nonexisting_file(tmpdir: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmpdir)
    with rewrite("sample", "w") as f:
        f.write("csdf")
    with open("sample") as f:
        assert f.read() == "csdf"


def test_unlink_parent_dir() -> None:
    adir = Path(gettempdir()) / f"tb.{os.getpid()}"
    adir.mkdir()
    afile = adir / "file1"
    afile.touch()
    unlink_parent_dir(afile)
    assert not adir.exists()


def test_user_agent() -> None:
    assert re.match(
        r"bandersnatch/[0-9]\.[0-9]\.[0-9]\.?d?e?v?[0-9]? \(.*\) "
        + rf"\(aiohttp {aiohttp.__version__}\)",
        user_agent(),
    )


def test_bandersnatch_safe_name() -> None:
    bad_name = "Flake_8_Fake"
    assert "flake-8-fake" == bandersnatch_safe_name(bad_name)


def test_removeprefix() -> None:
    version_str = "py3.6"
    prefix_str = "py"
    assert "3.6" == removeprefix(version_str, prefix_str)


def test_parse_version() -> None:
    version_str = "3.6"
    versions_list = ["-cp36-", "-pp36-", "-ip36-", "-jy36-", "-py3.6-", "-py3.6."]
    assert versions_list == parse_version(version_str)
    assert "-cp36-" in parse_version(version_str)
    assert "-py3.6." in parse_version(version_str)
