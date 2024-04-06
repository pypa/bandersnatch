from configparser import ConfigParser, NoOptionError, NoSectionError
from logging import getLogger
from pathlib import PurePath
from typing import Any

import attrs

from bandersnatch.simple import (
    SimpleDigest,
    SimpleFormat,
    get_digest_value,
    get_format_value,
)

from .attrs_utils import get_name_value_for_option, only_if_str, validate_not_empty
from .comparison_method import ComparisonMethod, get_comparison_value
from .diff_file_reference import eval_legacy_config_ref, has_legacy_config_ref
from .errors import ConfigurationError, InvalidValueError

logger = getLogger("bandersnatch")

_default_master_url = "https://pypi.org"
_default_root_uri = "https://files.pythonhosted.org"


@attrs.define(kw_only=True)
class MirrorOptions:
    """Class with attributes for all the options that may appear in the
    '[mirror]' section of a config file.
    """

    directory: PurePath = attrs.field(converter=PurePath)

    storage_backend_name: str = attrs.field(
        default="filesystem",
        alias="storage_backend",
        validator=validate_not_empty,
    )

    master_url: str = attrs.field(default=_default_master_url, alias="master")
    proxy_url: str | None = attrs.field(default=None, alias="proxy")

    download_mirror_url: str | None = attrs.field(default=None, alias="download_mirror")
    download_mirror_no_fallback: bool = False

    save_release_files: bool = attrs.field(default=True, alias="release_files")
    save_json: bool = attrs.field(default=False, alias="json")

    # type-ignores on converters for the following enums b/c MyPy's plugin for attrs
    # doesn't handle using arbitrary functions as converters
    simple_format: SimpleFormat = attrs.field(
        default=SimpleFormat.ALL,
        converter=only_if_str(get_format_value),  # type: ignore
    )

    compare_method: ComparisonMethod = attrs.field(
        default=ComparisonMethod.HASH,
        converter=only_if_str(get_comparison_value),  # type: ignore
    )

    digest_name: SimpleDigest = attrs.field(
        default=SimpleDigest.SHA256,
        converter=only_if_str(get_digest_value),  # type: ignore
    )

    # this gets a non-empty default value in post-init if save_release_files is False
    root_uri: str = ""

    hash_index: bool = False

    keep_index_versions: int = attrs.field(default=0, validator=attrs.validators.ge(0))

    diff_file: PurePath | None = attrs.field(
        default=None, converter=attrs.converters.optional(PurePath)
    )
    diff_append_epoch: bool = False

    stop_on_error: bool = False
    timeout: float = attrs.field(default=10.0, validator=attrs.validators.gt(0))
    global_timeout: float = attrs.field(
        default=1800.0, validator=attrs.validators.gt(0)
    )

    workers: int = attrs.field(
        default=3, validator=[attrs.validators.gt(0), attrs.validators.le(10)]
    )

    verifiers: int = attrs.field(
        default=3, validator=[attrs.validators.gt(0), attrs.validators.le(10)]
    )

    log_config: PurePath | None = attrs.field(
        default=None, converter=attrs.converters.optional(PurePath)
    )

    cleanup: bool = attrs.field(default=False, metadata={"deprecated": True})

    # Called after the attrs class is constructed; doing cross-field validation here
    def __attrs_post_init__(self) -> None:
        # set default for root_uri if release-files is disabled
        if not self.save_release_files and not self.root_uri:
            logger.warning(
                (
                    "Inconsistent config: 'root_uri' should be set when "
                    "'release-files' is disabled. Please set 'root-uri' in the "
                    "[mirror] section of your config file. Using default value '%s'"
                ),
                _default_root_uri,
            )
            self.root_uri = _default_root_uri

    @classmethod
    def from_config_parser(cls, source: ConfigParser) -> "MirrorOptions":
        if "mirror" not in source:
            raise ConfigurationError("Config file missing required section '[mirror]'")

        model_kwargs: dict[str, Any] = {}

        for option in attrs.fields(cls):
            option_name, option_value = get_name_value_for_option(
                source, "mirror", option
            )

            if option_name == "diff_file" and isinstance(option_value, str):
                option_value = _check_legacy_reference(source, option_value)

            if option_value is not None:
                model_kwargs[option_name] = option_value

        try:
            instance = cls(**model_kwargs)
        except ValueError as err:
            raise InvalidValueError.for_section("mirror", str(err)) from err
        except TypeError as err:
            raise ConfigurationError.for_section("mirror", str(err)) from err

        return instance


def _check_legacy_reference(config: ConfigParser, value: str) -> str | None:
    if not has_legacy_config_ref(value):
        return value

    logger.warning(
        "Found section reference using '{{ }}' in 'diff-file' path. "
        "Use ConfigParser's built-in extended interpolation instead, "
        "for example '${mirror:directory}/new-files'"
    )
    try:
        return eval_legacy_config_ref(config, value)
    except (ValueError, NoSectionError, NoOptionError) as ref_err:
        # NOTE: raise here would be a breaking change; previous impl. logged and
        # fell back to a default. Create exception anyway for consistent error messages.
        exc = InvalidValueError.for_option("mirror", "diff-file", str(ref_err))
        logger.error(str(exc))
        return None
