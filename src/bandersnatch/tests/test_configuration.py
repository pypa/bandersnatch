from collections.abc import Callable
from configparser import ConfigParser, DuplicateOptionError
from contextlib import nullcontext as does_not_raise
from pathlib import Path, PurePath
from typing import Any

import pytest

from bandersnatch.configuration import BandersnatchConfig, ConfigurationError
from bandersnatch.configuration.diff_file_reference import eval_legacy_config_ref
from bandersnatch.configuration.exceptions import (
    MissingRequiredOptionError,
    OptionValidationError,
)
from bandersnatch.configuration.mirror_options import (
    FileCompareMethod,
    get_mirror_options,
)
from bandersnatch.simple import SimpleDigest, SimpleFormat

#
# Configuration test fixtures
#


@pytest.fixture
def empty_config() -> BandersnatchConfig:
    return BandersnatchConfig()


@pytest.fixture
def config_with_defaults(empty_config: BandersnatchConfig) -> BandersnatchConfig:
    empty_config.read_defaults_file()
    empty_config.read_dict({"mirror": {"directory": "/test"}})
    return empty_config


@pytest.fixture
def config_factory(
    config_with_defaults: BandersnatchConfig,
) -> Callable[..., BandersnatchConfig]:
    conf = config_with_defaults

    def apply_overrides(**kwargs: dict[str, str]) -> BandersnatchConfig:
        for section, options in kwargs.items():
            if section not in conf:
                conf.add_section(section)
            for name, value in options.items():
                conf.set(section, name, value)
        return conf

    return apply_overrides


#
# BandersnatchConfig / configparser subclass
#


def test__bandersnatchconfig__normalizes_option_names() -> None:
    conf = BandersnatchConfig()

    with pytest.raises(DuplicateOptionError):
        conf.read_dict(
            {
                "test_section": {
                    "option_name": "1",
                    "option-name": "2",
                    "OPTION_NAME": "3",
                }
            }
        )

    conf.read_dict({"section": {"option-name": "yes"}})
    assert conf.get("section", "option_name") == "yes"


def test__bandersnatchconfig__read_defaults_file() -> None:
    conf = BandersnatchConfig()
    assert len(conf.sections()) == 0

    conf.read_defaults_file()

    assert conf.has_section("mirror")
    assert conf.has_option("mirror", "storage-backend")
    assert not conf.has_option("mirror", "directory")


def test__bandersnatchconfig__read_path(tmp_path: Path) -> None:
    source = ConfigParser()
    source.read_dict(
        {"red": {"one": "yes", "two": "no"}, "blue": {"three": "on", "four": "off"}}
    )

    with open(tmp_path / "test.cfg", mode="w", encoding="utf-8") as config_file:
        source.write(config_file)

    conf = BandersnatchConfig()
    conf.read_path(tmp_path / "test.cfg")

    assert conf.sections() == ["red", "blue"]
    assert dict(conf["blue"]) == {"three": "on", "four": "off"}


#
# MirrorOptions / get_mirror_options
#


def test__get_mirror_options__requires_section() -> None:
    empty = ConfigParser()
    with pytest.raises(ConfigurationError, match="missing required section"):
        _ = get_mirror_options(empty)


def test__get_mirror_options__requires_option() -> None:
    almost_empty = ConfigParser()
    almost_empty.add_section("mirror")
    with pytest.raises(MissingRequiredOptionError):
        _ = get_mirror_options(almost_empty)


def test__get_mirror_options__accepts_default_config() -> None:
    config = BandersnatchConfig()
    config.read_defaults_file()
    config["mirror"]["directory"] = "/test"
    try:
        _ = get_mirror_options(config)
    except ConfigurationError as err:
        raise AssertionError(f"failed to process default config: {err}")


def test__get_mirror_options__converts_paths(
    config_factory: Callable[..., ConfigParser],
) -> None:
    conf = config_factory(
        mirror={
            "diff_file": "/test/example/diff.txt",
            "log_config": "/test/conf/logs.cfg",
        }
    )

    opts = get_mirror_options(conf)

    assert isinstance(opts["directory"], PurePath)
    assert isinstance(opts["diff_file"], PurePath)
    assert isinstance(opts["log_config"], PurePath)


@pytest.mark.parametrize(
    "option_name",
    ("keep_index_versions", "timeout", "global_timeout", "workers", "verifiers"),
)
def test__get_mirror_options__invalidates_negative_numbers(
    option_name: str, config_factory: Callable[..., ConfigParser]
) -> None:
    conf = config_factory(mirror={option_name: "-1"})

    with pytest.raises(OptionValidationError):
        _ = get_mirror_options(conf)


def test__get_mirror_options__converts_bools(
    config_factory: Callable[..., ConfigParser],
) -> None:
    truthy = {
        "diff_append_epoch": "1",
        "release_files": "yes",
        "json": "on",
        "stop_on_error": "true",
        "hash_index": "True",
    }

    conf = config_factory(mirror=truthy)
    opts = get_mirror_options(conf)
    keys_expected_true = (
        "diff_append_epoch",
        "save_json",
        "save_release_files",
        "stop_on_error",
        "hash_index",
    )
    for key in keys_expected_true:
        assert opts[key]  # type: ignore


@pytest.mark.parametrize("bool_option_name", ["json", "release_files", "stop_on_error"])
def test__get_mirror_options__rejects_invalid_bools(
    bool_option_name: str, config_factory: Callable[..., ConfigParser]
) -> None:
    conf = config_factory(mirror={bool_option_name: "Not A Bool"})

    with pytest.raises(OptionValidationError, match="must be convertible to a boolean"):
        _ = get_mirror_options(conf)


@pytest.mark.parametrize("str_option_name", ["directory", "storage_backend", "master"])
def test__get_mirror_options__requires_non_empty_str(
    str_option_name: str, config_factory: Callable[..., ConfigParser]
) -> None:
    conf = config_factory(mirror={str_option_name: ""})

    with pytest.raises(OptionValidationError, match="must have a value"):
        _ = get_mirror_options(conf)


def test__get_mirror_options__converts_enums(
    config_factory: Callable[..., ConfigParser],
) -> None:
    enum_options = {
        "simple_format": SimpleFormat.HTML,
        "digest_name": SimpleDigest.MD5,
        "compare_method": FileCompareMethod.STAT,
    }
    conf = config_factory(
        mirror={k: v.name for k, v in enum_options.items()},  # type: ignore
    )

    opts = get_mirror_options(conf)

    for key, input_val in enum_options.items():
        parsed_value = opts[key]  # type: ignore
        assert type(parsed_value) is type(input_val)
        assert parsed_value == input_val


@pytest.mark.parametrize(
    "enum_option_name", ["simple_format", "digest_name", "compare_method"]
)
def test__get_mirror_options__rejects_invalid_enums(
    enum_option_name: str, config_factory: Callable[..., ConfigParser]
) -> None:
    conf = config_factory(mirror={enum_option_name: "test garbage"})

    with pytest.raises(
        OptionValidationError, match=r".+not a valid .+; must be one of: \[.+\]"
    ):
        _ = get_mirror_options(conf)


@pytest.mark.parametrize(
    ("input_value", "expected_result"),
    [
        ("1", does_not_raise(1)),
        ("10", does_not_raise(10)),
        ("-1", pytest.raises(OptionValidationError)),
        ("0", pytest.raises(OptionValidationError)),
        ("11", pytest.raises(OptionValidationError)),
    ],
)
def test__get_mirror_options__range_checks_workers(
    input_value: str, expected_result: Any, config_factory: Callable[..., ConfigParser]
) -> None:
    conf = config_factory(mirror={"workers": input_value})

    with expected_result as e:
        opts = get_mirror_options(conf)
        assert opts["workers"] == e


def test__get_mirror_options__sets_root_uri(
    config_factory: Callable[..., ConfigParser],
) -> None:
    conf = config_factory(mirror={"release_files": "no", "root_uri": ""})
    opts = get_mirror_options(conf)
    assert opts["root_uri"] == "https://files.pythonhosted.org"


#
# diff-file section_option interpolation
#

diff_file_test_cases = [
    (
        {
            "mirror": {
                "directory": "/test",
                "diff-file": r"{{mirror_directory}}",
            }
        },
        "/test",
    ),
    (
        {
            "mirror": {
                "directory": "/test",
                "diff-file": r"{{ mirror_directory }}",
            }
        },
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
]


@pytest.mark.parametrize(("input_options", "expected_path"), diff_file_test_cases)
def test_get_mirror_options_with_diff_file_reference(
    input_options: dict[str, Any],
    expected_path: str,
    config_factory: Callable[..., BandersnatchConfig],
) -> None:
    conf = config_factory(**input_options)
    opts = get_mirror_options(conf)
    assert isinstance(opts["diff_file"], PurePath)
    assert opts["diff_file"] == PurePath(expected_path)


invalid_diff_file_cases = [
    (
        r"{{ missing.underscore }}/foo",
        "Unable to parse config option reference",
    ),
    (r"/var/{{ mirror_woops }}/foo", "No option 'woops' in section: 'mirror'"),
]


@pytest.mark.parametrize(("input", "expected_error"), invalid_diff_file_cases)
def test_invalid_diff_file_reference_throws_exception(
    input: str, expected_error: str, config_with_defaults: ConfigParser
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        _ = eval_legacy_config_ref(config_with_defaults, input)
