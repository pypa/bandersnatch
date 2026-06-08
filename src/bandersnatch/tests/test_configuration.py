import configparser
import importlib.resources
from collections.abc import Iterator
from pathlib import Path

import pytest

from bandersnatch.config.diff_file_reference import eval_config_reference
from bandersnatch.configuration import (
    BandersnatchConfig,
    SetConfigValues,
    Singleton,
    validate_config_values,
)
from bandersnatch.simple import SimpleFormat


@pytest.fixture(autouse=True)
def isolated_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """
    Isolate each test's working directory and singleton state.
    """
    monkeypatch.chdir(tmp_path)

    # Ensure each test gets a fresh instance if needed
    # We have a dedicated test to ensure we're creating a singleton
    Singleton._instances = {}

    yield

    Singleton._instances = {}


# Singleton / basic config


def test_is_singleton() -> None:
    instance1 = BandersnatchConfig()
    instance2 = BandersnatchConfig()
    assert id(instance1) == id(instance2)


def test_single_config__default__all_sections_present() -> None:
    config_file = Path(str(importlib.resources.files("bandersnatch") / "unittest.conf"))
    instance = BandersnatchConfig(config_file)
    for section in ["mirror", "plugins", "blocklist"]:
        assert section in instance.sections()


def test_single_config__default__mirror__setting_attributes() -> None:
    instance = BandersnatchConfig()
    options = {option for option in instance["mirror"]}
    assert options == {
        "allow-non-https",
        "api-method",
        "cleanup",
        "compare-method",
        "diff-append-epoch",
        "diff-file",
        "digest_name",
        "download-mirror",
        "download-mirror-no-fallback",
        "global-timeout",
        "hash-index",
        "json",
        "keep-index-versions",
        "log-config",
        "master",
        "proxy",
        "release-files",
        "root_uri",
        "simple-format",
        "stop-on-error",
        "storage-backend",
        "storage-filesystem-manage-permissions",
        "timeout",
        "verifiers",
        "workers",
    }


def test_single_config__default__mirror__setting__types() -> None:
    """
    Make sure all default mirror settings will cast to the correct types
    """
    instance = BandersnatchConfig()
    for option, option_type in [
        ("directory", str),
        ("hash-index", bool),
        ("json", bool),
        ("master", str),
        ("stop-on-error", bool),
        ("storage-backend", str),
        ("timeout", int),
        ("global-timeout", int),
        ("workers", int),
        ("compare-method", str),
        ("api-method", str),
    ]:
        assert isinstance(option_type(instance["mirror"].get(option)), option_type)


def test_single_config_custom_setting_boolean() -> None:
    instance = BandersnatchConfig()
    instance.read_string("[mirror]\nhash-index=false\n")
    assert not instance["mirror"].getboolean("hash-index")


def test_single_config_custom_setting_int() -> None:
    instance = BandersnatchConfig()
    instance.read_string("[mirror]\ntimeout=999\n")
    assert int(instance["mirror"]["timeout"]) == 999


def test_single_config_custom_setting_str() -> None:
    instance = BandersnatchConfig()
    instance.read_string("[mirror]\nmaster=https://foo.bar.baz\n")
    assert instance["mirror"]["master"] == "https://foo.bar.baz"


def test_multiple_instances_custom_setting_str() -> None:
    instance1 = BandersnatchConfig()
    instance1.read_string("[mirror]\nmaster=https://foo.bar.baz\n")
    instance2 = BandersnatchConfig()
    assert instance2["mirror"]["master"] == "https://foo.bar.baz"


# validate_config_values


def test_validate_config_values() -> None:
    default_values = SetConfigValues(
        False,
        "",
        "",
        False,
        "sha256",
        "filesystem",
        False,
        True,
        "hash",
        "",
        False,
        SimpleFormat.ALL,
        "simple",
    )
    no_options_configparser = BandersnatchConfig(load_defaults=True)
    assert default_values == validate_config_values(no_options_configparser)


def test_validate_config_values_release_files_false_sets_root_uri() -> None:
    default_values = SetConfigValues(
        False,
        "https://files.pythonhosted.org",
        "",
        False,
        "sha256",
        "filesystem",
        False,
        False,
        "hash",
        "",
        False,
        SimpleFormat.ALL,
        "simple",
    )
    release_files_false_configparser = BandersnatchConfig(load_defaults=True)
    release_files_false_configparser["mirror"].update({"release-files": "false"})
    assert default_values == validate_config_values(release_files_false_configparser)


def test_validate_config_values_download_mirror_false_sets_no_fallback() -> None:
    default_values = SetConfigValues(
        False,
        "",
        "",
        False,
        "sha256",
        "filesystem",
        False,
        True,
        "hash",
        "",
        False,
        SimpleFormat.ALL,
        "simple",
    )
    release_files_false_configparser = BandersnatchConfig(load_defaults=True)
    release_files_false_configparser["mirror"].update(
        {
            "download-mirror-no-fallback": "true",
        }
    )
    assert default_values == validate_config_values(release_files_false_configparser)


def test_validate_config_values_api_method_simple() -> None:
    """Test that api_method='simple' is accepted and validated."""
    simple_api_values = SetConfigValues(
        False,
        "",
        "",
        False,
        "sha256",
        "filesystem",
        False,
        True,
        "hash",
        "",
        False,
        SimpleFormat.ALL,
        "simple",
    )
    simple_api_config = BandersnatchConfig(load_defaults=True)
    simple_api_config["mirror"].update({"api-method": "simple"})
    assert simple_api_values == validate_config_values(simple_api_config)


def test_validate_config_values_api_method_xmlrpc() -> None:
    """Test that api_method='xmlrpc' is accepted and validated."""
    xmlrpc_api_values = SetConfigValues(
        False,
        "",
        "",
        False,
        "sha256",
        "filesystem",
        False,
        True,
        "hash",
        "",
        False,
        SimpleFormat.ALL,
        "xmlrpc",
    )
    xmlrpc_api_config = BandersnatchConfig(load_defaults=True)
    xmlrpc_api_config["mirror"].update({"api-method": "xmlrpc"})
    assert xmlrpc_api_values == validate_config_values(xmlrpc_api_config)


def test_validate_config_values_api_method_invalid() -> None:
    """Test that invalid api_method raises ValueError."""
    invalid_api_config = BandersnatchConfig(load_defaults=True)
    invalid_api_config["mirror"].update({"api-method": "invalid"})

    with pytest.raises(ValueError) as exc_info:
        validate_config_values(invalid_api_config)

    msg = str(exc_info.value)
    assert "api-method invalid is not supported" in msg
    assert "('simple', 'xmlrpc')" in msg


def test_validate_config_values_api_method_defaults_to_simple() -> None:
    """Test that api_method defaults to 'simple' when not specified."""
    config = BandersnatchConfig(load_defaults=True)
    # Remove the api-method config if it exists
    if config.has_option("mirror", "api-method"):
        config.remove_option("mirror", "api-method")
    result = validate_config_values(config)
    assert result.api_method == "simple"


# diff-file reference expansion


@pytest.mark.parametrize(
    ("cfg_data", "expected"),
    [
        (
            {"mirror": {"directory": "/test", "diff-file": r"{{mirror_directory}}"}},
            "/test",
        ),
        (
            {"mirror": {"directory": "/test", "diff-file": r"{{ mirror_directory }}"}},
            "/test",
        ),
        (
            {
                "mirror": {
                    "directory": "/test",
                    "diff-file": r"{{ mirror_directory }}/diffs/new-files",
                }
            },
            "/test/diffs/new-files",
        ),
        (
            {
                "strings": {"test": "TESTING"},
                "mirror": {"diff-file": r"/var/log/{{ strings_test }}"},
            },
            "/var/log/TESTING",
        ),
        (
            {
                "strings": {"test": "TESTING"},
                "mirror": {"diff-file": r"/var/log/{{ strings_test }}/diffs"},
            },
            "/var/log/TESTING/diffs",
        ),
    ],
)
def test_validate_config_diff_file_reference(cfg_data: dict, expected: str) -> None:
    cfg = BandersnatchConfig(load_defaults=True)
    cfg.read_dict(cfg_data)
    config_values = validate_config_values(cfg)
    assert isinstance(config_values.diff_file_path, str)
    assert config_values.diff_file_path == expected


@pytest.mark.parametrize(
    ("diff_file_val", "expected_error"),
    [
        (r"{{ missing.underscore }}/foo", "Unable to parse config option reference"),
        (r"/var/{{ mirror_woops }}/foo", "No option 'woops' in section: 'mirror'"),
    ],
)
def test_invalid_diff_file_reference_throws_exception(
    diff_file_val: str, expected_error: str
) -> None:
    cfg = configparser.ConfigParser()
    cfg.read_dict({"mirror": {"diff-file": diff_file_val}})
    with pytest.raises(ValueError, match=expected_error):
        eval_config_reference(cfg, diff_file_val)
