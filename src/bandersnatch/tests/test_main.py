import configparser
import os.path
import sys
import unittest.mock as mock

import pytest

import bandersnatch.mirror
from bandersnatch.configuration import Singleton
from bandersnatch.main import main


def setup():
    """ simple setup function to clear Singleton._instances before each test"""
    Singleton._instances = {}


def test_main_help(capfd):
    sys.argv = ["bandersnatch", "--help"]
    with pytest.raises(SystemExit):
        main()
    out, err = capfd.readouterr()
    assert out.startswith("usage: bandersnatch")
    assert "" == err


def test_main_create_config(caplog, tmpdir):
    sys.argv = ["bandersnatch", "-c", str(tmpdir / "bandersnatch.conf"), "mirror"]
    assert main() == 1
    assert "creating default config" in caplog.text
    assert os.path.exists(str(tmpdir / "bandersnatch.conf"))


def test_main_cant_create_config(caplog, tmpdir):
    sys.argv = [
        "bandersnatch",
        "-c",
        str(tmpdir / "foo" / "bandersnatch.conf"),
        "mirror",
    ]
    assert main() == 1
    assert "creating default config" in caplog.text
    assert "Could not create config file" in caplog.text
    assert not os.path.exists(str(tmpdir / "bandersnatch.conf"))


def test_main_reads_config_values(mirror_mock):
    config = os.path.dirname(bandersnatch.__file__) + "/default.conf"
    sys.argv = ["bandersnatch", "-c", config, "mirror"]
    assert os.path.exists(config)
    assert isinstance(bandersnatch.mirror.Mirror, mock.Mock)
    main()
    (homedir, master), kwargs = mirror_mock.call_args_list[0]
    assert "/srv/pypi" == homedir
    assert isinstance(master, bandersnatch.master.Master)
    assert {
        "stop_on_error": False,
        "hash_index": False,
        "workers": 3,
        "root_uri": None,
        "json_save": False,
        "digest_name": "sha256",
        "keep_index_versions": 0,
    } == kwargs
    assert mirror_mock().synchronize.called


def test_main_reads_custom_config_values(mirror_mock, logging_mock, customconfig):
    setup()
    conffile = str(customconfig / "bandersnatch.conf")
    sys.argv = ["bandersnatch", "-c", conffile, "mirror"]
    main()
    (log_config, kwargs) = logging_mock.call_args_list[0]
    assert log_config == (str(customconfig / "bandersnatch-log.conf"),)
    assert mirror_mock().synchronize.called


def test_main_throws_exception_on_unsupported_digest_name(customconfig):
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
        main()

    assert "foobar is not supported" in str(e.value)


@pytest.fixture
def customconfig(tmpdir):
    default = os.path.dirname(bandersnatch.__file__) + "/default.conf"
    config = open(default).read()
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
