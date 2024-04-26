import asyncio
import configparser
import importlib
import importlib.resources
import sys
import unittest.mock as mock
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture

import bandersnatch.mirror
import bandersnatch.storage
from bandersnatch.configuration import BandersnatchConfig, ConfigurationError
from bandersnatch.configuration.mirror_options import FileCompareMethod
from bandersnatch.main import main
from bandersnatch.simple import SimpleDigest, SimpleFormat

if TYPE_CHECKING:
    from bandersnatch.mirror import BandersnatchMirror


async def empty_dict(*args: Any, **kwargs: Any) -> dict:
    return {}


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
    assert "Creating example config" in caplog.text
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
    assert "Creating example config" in caplog.text
    assert "Could not create config file" in caplog.text
    conf_path = Path(tmpdir) / "bandersnatch.conf"
    assert not conf_path.exists()


def test_main_reads_config_values(mirror_mock: mock.MagicMock, tmp_path: Path) -> None:
    config = BandersnatchConfig()

    # read configuration options from unittest.conf file in bandersnatch package dir
    base_config_res = importlib.resources.files("bandersnatch") / "unittest.conf"
    with importlib.resources.as_file(base_config_res) as base_config_path:
        config.read_path(base_config_path)

    # overwrite the 'diff-file' option to a path within the test's tmp folder
    target_diff_file = tmp_path / "srv/pypi/mirrored-files"
    config.set("mirror", "diff-file", target_diff_file.as_posix())

    # write the config to a file for 'main' to read from
    test_config_path = tmp_path / "unittest.conf"
    with test_config_path.open(mode="w", encoding="utf-8") as test_config_file:
        config.write(test_config_file)

    assert test_config_path.exists()

    # run bandersnatch with the config file we just wrote to disk
    sys.argv = ["bandersnatch", "-c", str(test_config_path), "mirror"]
    main(asyncio.new_event_loop())
    (homedir, master, _storage, _filters), kwargs = mirror_mock.call_args_list[0]

    assert Path("/srv/pypi") == homedir
    assert isinstance(master, bandersnatch.master.Master)
    assert {
        "stop_on_error": False,
        "hash_index": False,
        "workers": 3,
        "root_uri": "",
        "json_save": False,
        "digest_name": SimpleDigest.SHA256,
        "keep_index_versions": 0,
        "release_files_save": True,
        "diff_append_epoch": False,
        "diff_full_path": target_diff_file,
        "cleanup": False,
        "compare_method": FileCompareMethod.HASH,
        "download_mirror": "",
        "download_mirror_no_fallback": False,
        "simple_format": SimpleFormat.ALL,
    } == kwargs


def test_main_reads_custom_config_values(
    mirror_mock: "BandersnatchMirror", logging_mock: mock.MagicMock, customconfig: Path
) -> None:
    conffile = customconfig / "bandersnatch.conf"
    sys.argv = ["bandersnatch", "-c", str(conffile), "mirror"]
    main(asyncio.new_event_loop())
    (log_config, _kwargs) = logging_mock.call_args_list[0]
    assert log_config == ((customconfig / "bandersnatch-log.conf"),)


def test_main_throws_exception_on_unsupported_digest_name(
    customconfig: Path,
) -> None:
    conffile = str(customconfig / "bandersnatch.conf")
    parser = configparser.ConfigParser()
    parser.read(conffile)
    parser["mirror"]["digest_name"] = "foobar"
    del parser["mirror"]["log-config"]
    with open(conffile, "w") as fp:
        parser.write(fp)
    sys.argv = ["bandersnatch", "-c", conffile, "mirror"]

    with pytest.raises(
        ConfigurationError, match="not a valid Simple API file hash digest"
    ):
        main(asyncio.new_event_loop())


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
