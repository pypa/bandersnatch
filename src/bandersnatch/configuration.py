"""
Module containing classes to access the bandersnatch configuration file
"""

import abc
import configparser
import importlib.resources
import logging
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Any, NamedTuple

from .config.diff_file_reference import eval_config_reference, has_config_reference
from .config.exceptions import ConfigError, ConfigFileNotFound
from .simple import SimpleDigest, SimpleFormat, get_digest_value, get_format_value

logger = logging.getLogger("bandersnatch")

# Filename of example configuration file inside the bandersnatch package
_example_conf_file = "example.conf"

# Filename of default values file inside the bandersnatch package
_defaults_conf_file = "defaults.conf"


class SetConfigValues(NamedTuple):
    json_save: bool
    root_uri: str
    diff_file_path: str
    diff_append_epoch: bool
    digest_name: SimpleDigest
    storage_backend_name: str
    cleanup: bool
    release_files_save: bool
    compare_method: str
    download_mirror: str
    download_mirror_no_fallback: bool
    simple_format: SimpleFormat
    api_method: str


class Singleton(type):  # pragma: no cover
    _instances: dict["Singleton", type] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> type:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


# ConfigParser's metaclass is abc.ABCMeta; we can't inherit from ConfigParser and
# also use the Singleton metaclass unless we "manually" combine the metaclasses.
class _SingletonABCMeta(Singleton, abc.ABCMeta):
    pass


class BandersnatchConfig(ConfigParser, metaclass=_SingletonABCMeta):
    """Configuration singleton. Provides global access to loaded configuration
    options as a ConfigParser subclass. Always reads default mirror options when
    initialized. If given a file path, that file is loaded second so its values
    overwrite corresponding defaults.
    """

    # Ensure we only show the deprecations once
    SHOWN_DEPRECATIONS = False

    def __init__(
        self, config_file: Path | None = None, load_defaults: bool = True
    ) -> None:
        """Create the singleton configuration object. Default configuration values are
        read from a configuration file inside the package. If a file path is given, that
        file is read after reading defaults such that it's values overwrite defaults.

        :param Path | None config_file: non-default configuration file to load, defaults to None
        """
        super(ConfigParser, self).__init__(delimiters="=")
        self.found_deprecations: list[str] = []

        # ConfigParser.read can process an iterable of file paths, but separate read
        # calls are used on purpose to add more information to error messages.
        if load_defaults:
            self._read_defaults_file()
        if config_file:
            self._read_user_config_file(config_file)

    def optionxform(self, optionstr: str) -> str:
        return optionstr

    def check_for_deprecations(self) -> None:
        if self.SHOWN_DEPRECATIONS:
            return
        self.SHOWN_DEPRECATIONS = True

    def _read_defaults_file(self) -> None:
        try:
            defaults_file = (
                importlib.resources.files("bandersnatch") / _defaults_conf_file
            )
            self.read(str(defaults_file))
            logger.debug("Read configuration defaults file.")
        except OSError as err:
            raise ConfigError("Error reading configuration defaults: %s", err) from err

    def _read_user_config_file(self, config_file: Path) -> None:
        # Check for this case explicitly instead of letting it fall under the OSError
        # case, so we can use the exception type for control flow:
        if not config_file.exists():
            raise ConfigFileNotFound(
                f"Specified configuration file doesn't exist: {config_file}"
            )

        # Standard configparser, but we want to add context information to an OSError
        try:
            self.read(config_file)
            logger.info("Read configuration file '%s'", config_file)
        except OSError as err:
            raise ConfigError(
                "Error reading configuration file '%s': %s", config_file, err
            ) from err


def create_example_config(dest: Path) -> None:
    """Create an example configuration file at the specified location.

    :param Path dest: destination path for the configuration file.
    """
    example_source = importlib.resources.files("bandersnatch") / _example_conf_file
    try:
        shutil.copy(str(example_source), dest)
    except OSError as err:
        logger.error("Could not create config file '%s': %s", dest, err)


def validate_config_values(  # noqa: C901
    config: configparser.ConfigParser,
) -> SetConfigValues:

    json_save = config.getboolean("mirror", "json")

    root_uri = config.get("mirror", "root_uri")

    release_files_save = config.getboolean("mirror", "release-files")

    if not release_files_save and not root_uri:
        root_uri = "https://files.pythonhosted.org"
        logger.warning(
            "Please update your config to include a root_uri in the [mirror] "
            + "section when disabling release file sync. Setting to "
            + root_uri
        )

    diff_file_path = config.get("mirror", "diff-file")

    if diff_file_path and has_config_reference(diff_file_path):
        try:
            diff_file_path = eval_config_reference(config, diff_file_path)
        except ValueError as err:
            logger.error(
                "Invalid section reference in `diff-file` key: %s. Saving diff files in base mirror directory.",
                str(err),
            )
            mirror_dir = config.get("mirror", "directory")
            diff_file_path = (Path(mirror_dir) / "mirrored-files").as_posix()

    diff_append_epoch = config.getboolean("mirror", "diff-append-epoch")

    storage_backend_name = config.get("mirror", "storage-backend")

    try:
        digest_name = get_digest_value(config.get("mirror", "digest_name"))
    except ValueError as e:
        logger.error(
            f"Supplied digest_name {config.get('mirror', 'digest_name')} is "
            + "not supported! Please update the digest_name in the [mirror] "
            + "section of your config to a supported digest value."
        )
        raise e

    try:
        simple_format_raw = config.get("mirror", "simple-format")
        simple_format = get_format_value(simple_format_raw)
    except ValueError as e:
        logger.error(
            f"Supplied simple-format {simple_format_raw} is not supported!"
            + " Please updare the simple-format in the [mirror] section of"
            + " your config to a supported value."
        )
        raise e

    compare_method = config.get("mirror", "compare-method")
    if compare_method not in ("hash", "stat"):
        raise ValueError(
            f"Supplied compare_method {compare_method} is not supported! Please "
            + "update compare_method to one of ('hash', 'stat') in the [mirror] "
            + "section."
        )

    download_mirror = config.get("mirror", "download-mirror")

    if download_mirror:

        logger.debug(
            "Checking config for only download from alternative download mirror"
        )
        download_mirror_no_fallback = config.getboolean(
            "mirror", "download-mirror-no-fallback"
        )
        if download_mirror_no_fallback:
            logger.info("Setting to download from mirror without fallback")
        else:
            logger.debug("Setting to fallback to original if download mirror fails")
    else:
        download_mirror_no_fallback = False
        logger.debug(
            "Skip checking download-mirror-no-fallback because dependent option"
            + "is not set in config."
        )

    cleanup = config.getboolean("mirror", "cleanup", fallback=False)

    api_method = config.get("mirror", "api-method", fallback="simple")
    if api_method not in ("simple", "xmlrpc"):
        raise ValueError(
            f"Supplied api-method {api_method} is not supported! Please "
            + "update api-method to one of ('simple', 'xmlrpc') in the [mirror] "
            + "section."
        )

    return SetConfigValues(
        json_save,
        root_uri,
        diff_file_path,
        diff_append_epoch,
        digest_name,
        storage_backend_name,
        cleanup,
        release_files_save,
        compare_method,
        download_mirror,
        download_mirror_no_fallback,
        simple_format,
        api_method,
    )
