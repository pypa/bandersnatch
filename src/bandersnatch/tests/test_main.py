import asyncio
import configparser
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture

import bandersnatch.mirror
import bandersnatch.storage
from bandersnatch.configuration import Singleton
from bandersnatch.main import main
from bandersnatch.simple import SimpleFormat

if TYPE_CHECKING:
    from bandersnatch.mirror import BandersnatchMirror


async def empty_dict(*args: Any, **kwargs: Any) -> dict:
    return {}


def setup() -> None:
    """simple setup function to clear Singleton._instances before each test"""
    Singleton._instances = {}


def test_main_help(capfd: CaptureFixture) -> None:
    sys.argv = ["bandersnatch", "--help"]
    with pytest.raises(SystemExit):
        main(asyncio.new_event_loop())
    out, err = capfd.readouterr()
    assert out.startswith("usage: bandersnatch")
    assert "" == err


def test_main_create_config(caplog: LogCaptureFixture, tmpdir: Path) -> None:
    sys.argv = ["bandersnatch", "-c", str(tmpdir / "bandersnatch.conf"), "mirror"]
    assert main(asyncio.new_event_loop()) == 1
    assert "creating default config" in caplog.text
    conf_path = Path(tmpdir) / "bandersnatch.conf"
    assert conf_path.exists()


def test_main_cant_create_config(caplog: LogCaptureFixture, tmpdir: Path) -> None:
    sys.argv = [
        "bandersnatch",
        "-c",
        str(tmpdir / "foo" / "bandersnatch.conf"),
        "mirror",
    ]
    assert main(asyncio.new_event_loop()) == 1
    assert "creating default config" in caplog.text
    assert "Could not create config file" in caplog.text
    conf_path = Path(tmpdir) / "bandersnatch.conf"
    assert not conf_path.exists()


def test_main_reads_config_values(mirror_mock: mock.MagicMock, tmpdir: Path) -> None:
    base_config_path = Path(bandersnatch.__file__).parent / "unittest.conf"
    diff_file = Path(tempfile.gettempdir()) / "srv/pypi/mirrored-files"
    config_lines = [
        (
            f"diff-file = {diff_file.as_posix()}\n"
            if line.startswith("diff-file")
            else line
        )
        for line in base_config_path.read_text().splitlines()
    ]
    config_path = tmpdir / "unittest.conf"
    config_path.write_text("\n".join(config_lines), encoding="utf-8")
    sys.argv = ["bandersnatch", "-c", str(config_path), "mirror"]
    assert config_path.exists()
    main(asyncio.new_event_loop())
    (homedir, master), kwargs = mirror_mock.call_args_list[0]

    assert Path("/srv/pypi") == homedir
    assert isinstance(master, bandersnatch.master.Master)
    assert {
        "stop_on_error": False,
        "hash_index": False,
        "workers": 3,
        "root_uri": "",
        "json_save": False,
        "digest_name": "sha256",
        "keep_index_versions": 0,
        "release_files_save": True,
        "storage_backend": "filesystem",
        "diff_file": diff_file,
        "diff_append_epoch": False,
        "diff_full_path": diff_file,
        "cleanup": False,
        "compare_method": "hash",
        "download_mirror": "",
        "download_mirror_no_fallback": False,
        "simple_format": SimpleFormat.ALL,
    } == kwargs


def test_main_reads_custom_config_values(
    mirror_mock: "BandersnatchMirror", logging_mock: mock.MagicMock, customconfig: Path
) -> None:
    setup()
    conffile = str(customconfig / "bandersnatch.conf")
    sys.argv = ["bandersnatch", "-c", conffile, "mirror"]
    main(asyncio.new_event_loop())
    (log_config, _kwargs) = logging_mock.call_args_list[0]
    assert log_config == (str(customconfig / "bandersnatch-log.conf"),)


def test_main_throws_exception_on_unsupported_digest_name(
    customconfig: Path,
) -> None:
    setup()
    conffile = str(customconfig / "bandersnatch.conf")
    parser = configparser.ConfigParser()
    parser.read(conffile)
    parser["mirror"]["digest_name"] = "foobar"
    del parser["mirror"]["log-config"]
    with open(conffile, "w") as fp:
        parser.write(fp)
    sys.argv = ["bandersnatch", "-c", conffile, "mirror"]

    with pytest.raises(ValueError) as e:
        main(asyncio.new_event_loop())

    assert "foobar is not a valid" in str(e.value)


@pytest.fixture
def customconfig(tmpdir: Path) -> Path:
    default_path = Path(bandersnatch.__file__).parent / "unittest.conf"
    with default_path.open("r") as dfp:
        config = dfp.read()
    config = config.replace("/srv/pypi", str(tmpdir / "pypi"))
    with open(str(tmpdir / "bandersnatch.conf"), "w") as f:
        f.write(config)
    config = config.replace("; log-config", "log-config")
    config = config.replace(
        "/etc/bandersnatch-log.conf", str(tmpdir / "bandersnatch-log.conf")
    )
    with open(str(tmpdir / "bandersnatch.conf"), "w") as f:
        f.write(config)
    return tmpdir
