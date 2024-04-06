from collections.abc import Iterable
from contextlib import nullcontext
from pathlib import PurePath
from typing import Any

import pytest

from bandersnatch.config import (
    BandersnatchConfig,
    ConfigurationError,
    InvalidValueError,
    MirrorOptions,
    MissingOptionError,
)
from bandersnatch.config.diff_file_reference import eval_legacy_config_ref


def config_with(content: dict[str, Any] | None = None) -> BandersnatchConfig:
    base = {"mirror": {"directory": "/test"}}
    config = BandersnatchConfig()
    config.read_dict(base)
    if content:
        config.read_dict(content)
    return config


def test_empty_config_raises() -> None:
    config = BandersnatchConfig()
    with pytest.raises(ConfigurationError, match="missing required section"):
        _ = config.get_validated(MirrorOptions)


def test_empty_section_raises() -> None:
    config = BandersnatchConfig()
    config.read_dict({"mirror": {}})
    with pytest.raises(MissingOptionError, match="missing required option"):
        _ = config.get_validated(MirrorOptions)


def test_minimal_mirror_options_are_valid() -> None:
    config = config_with()
    expected_options = MirrorOptions(directory=PurePath("/test"))
    validated_options = config.get_validated(MirrorOptions)
    assert validated_options == expected_options


@pytest.mark.parametrize(
    ("cfg_data", "expected"),
    [
        (
            {
                "mirror": {
                    "diff-file": r"{{mirror_directory}}",
                }
            },
            "/test",
        ),
        (
            {
                "mirror": {
                    "diff-file": r"{{ mirror_directory }}",
                }
            },
            "/test",
        ),
        (
            {
                "mirror": {
                    "diff-file": r"{{ mirror_directory }}/diffs/new-files",
                }
            },
            "/test/diffs/new-files",
        ),
        (
            {
                "strings": {"test": "TESTING"},
                "mirror": {
                    "diff-file": r"/var/log/{{ strings_test }}",
                },
            },
            "/var/log/TESTING",
        ),
        (
            {
                "strings": {"test": "TESTING"},
                "mirror": {
                    "diff-file": r"/var/log/{{ strings_test }}/diffs",
                },
            },
            "/var/log/TESTING/diffs",
        ),
    ],
)
def test_legacy_diff_file_ref_resolves(cfg_data: dict, expected: str) -> None:
    config = config_with(cfg_data)
    mirror_opts = config.get_validated(MirrorOptions)
    assert mirror_opts.diff_file == PurePath(expected)


@pytest.mark.parametrize(
    ("option_value", "expected_message"),
    [
        (
            r"{{ missing.underscore }}/foo",
            "Unable to parse config option reference",
        ),
        (r"/var/{{ mirror_woops }}/foo", "No option 'woops' in section: 'mirror'"),
    ],
)
def test_invalid_legacy_diff_file_ref_raises(
    option_value: str, expected_message: str
) -> None:
    config = config_with({"mirror": {"diff-file": option_value}})
    with pytest.raises(ValueError, match=expected_message):
        _ = eval_legacy_config_ref(config, option_value)


@pytest.mark.parametrize(
    ("release_files_option", "expected_root_uri"),
    [
        ("", ""),
        ("true", ""),
        ("false", "https://files.pythonhosted.org"),
    ],
)
def test_release_files_off_sets_default_root_uri(
    release_files_option: str,
    expected_root_uri: str,
) -> None:
    cfg_data = (
        {"mirror": {"release-files": release_files_option}}
        if release_files_option
        else {}
    )
    config = config_with(cfg_data)
    mirror_opts = config.get_validated(MirrorOptions)
    assert mirror_opts.root_uri == expected_root_uri


def _permutate_case(*texts: str) -> Iterable[str]:
    for t in texts:
        yield t
        yield t.upper()
        yield t.capitalize()


@pytest.mark.parametrize(
    ("config_value", "expected"),
    [
        *((v, True) for v in _permutate_case("on", "yes", "true")),
        *((v, False) for v in _permutate_case("no", "off", "false")),
    ],
)
def test_friendly_boolean_is_valid(config_value: str, expected: bool) -> None:
    content = {"mirror": {"diff-append-epoch": config_value}}
    config = config_with(content)
    mirror_opts = config.get_validated(MirrorOptions)
    assert mirror_opts.diff_append_epoch == expected


@pytest.mark.parametrize(
    ("timeout_value", "expected_timeout"),
    [
        ("-1", pytest.raises(InvalidValueError)),
        ("0", pytest.raises(InvalidValueError)),
        ("1.9", nullcontext(1.9)),
        ("1000.0", nullcontext(1000.0)),
    ],
)
def test_non_positive_timeouts_are_rejected(
    timeout_value: str, expected_timeout: Any
) -> None:
    content = {"mirror": {"timeout": timeout_value}}
    config = config_with(content)
    with expected_timeout as e:
        mirror_opts = config.get_validated(MirrorOptions)
        assert mirror_opts.timeout == pytest.approx(e)


@pytest.mark.parametrize(
    ("workers_value", "expected_workers"),
    [
        ("-1", pytest.raises(InvalidValueError)),
        ("0", pytest.raises(InvalidValueError)),
        ("1", nullcontext(1)),
        ("10", nullcontext(10)),
        ("11", pytest.raises(InvalidValueError)),
    ],
)
def test_out_of_range_worker_counts_are_rejected(
    workers_value: str, expected_workers: Any
) -> None:
    content = {"mirror": {"workers": workers_value}}
    config = config_with(content)
    with expected_workers as e:
        mirror_opts = config.get_validated(MirrorOptions)
        assert mirror_opts.workers == e


_int_convert_error_pattern = r"can't convert option .+ to expected type 'int'"


@pytest.mark.parametrize(
    ("workers_value", "expected_workers"),
    [
        ("1", nullcontext(1)),
        ("01", nullcontext(1)),
        ("0_1", nullcontext(1)),
        ("1_", pytest.raises(InvalidValueError, match=_int_convert_error_pattern)),
        (
            "fooey",
            pytest.raises(InvalidValueError, match=_int_convert_error_pattern),
        ),
        (
            "no",
            pytest.raises(InvalidValueError, match=_int_convert_error_pattern),
        ),
    ],
)
def test_integer_option_string_conversion(
    workers_value: str,
    expected_workers: Any,
) -> None:
    content = {"mirror": {"workers": workers_value}}
    config = config_with(content)
    with expected_workers as e:
        mirror_opts = config.get_validated(MirrorOptions)
        assert mirror_opts.workers == e
