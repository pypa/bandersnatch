"""
Module containing classes to access the bandersnatch configuration file
"""
import configparser
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Type

try:
    import importlib.resources
except ImportError:  # pragma: no cover
    # For <=3.6
    import importlib
    import importlib_resources

    importlib.resources = importlib_resources


logger = logging.getLogger("bandersnatch")


class SetConfigValues(NamedTuple):
    json_save: bool
    root_uri: str
    diff_file_path: str
    diff_append_epoch: bool
    digest_name: str
    storage_backend_name: str
    cleanup: bool


class Singleton(type):  # pragma: no cover
    _instances: Dict["Singleton", Type] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Type:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class BandersnatchConfig(metaclass=Singleton):
    # Ensure we only show the deprecations once
    SHOWN_DEPRECATIONS = False

    def __init__(self, config_file: Optional[str] = None) -> None:
        """
        Bandersnatch configuration class singleton

        This class is a singleton that parses the configuration once at the
        start time.

        Parameters
        ==========
        config_file: str, optional
            Path to the configuration file to use
        """
        self.found_deprecations: List[str] = []
        with importlib.resources.path(  # type: ignore
            "bandersnatch", "default.conf"
        ) as config_path:
            self.default_config_file = str(config_path)
        self.config_file = config_file
        self.load_configuration()
        self.check_for_deprecations()

    def check_for_deprecations(self) -> None:
        if self.SHOWN_DEPRECATIONS:
            return
        if self.config.has_section("whitelist") or self.config.has_section("blacklist"):
            err_msg = (
                "whitelist/blacklist filter plugins will be renamed to "
                "allowlist_*/blocklist_* in version 5.0 "
                " - Documentation @ https://bandersnatch.readthedocs.io/"
            )
            warnings.warn(err_msg, DeprecationWarning, stacklevel=2)
            logger.warning(err_msg)
        self.SHOWN_DEPRECATIONS = True

    def load_configuration(self) -> None:
        """
        Read the configuration from a configuration file
        """
        config_file = self.default_config_file
        if self.config_file:
            config_file = self.config_file
        self.config = configparser.ConfigParser(delimiters="=")
        self.config.optionxform = lambda option: option  # type: ignore
        self.config.read(config_file)


# 11-15, 84-89, 98-99, 117-118, 124-126, 144-149
def validate_config_values(config: configparser.ConfigParser) -> SetConfigValues:
    try:
        json_save = config.getboolean("mirror", "json")
    except configparser.NoOptionError:
        logger.error(
            "Please update your config to include a json "
            + "boolean in the [mirror] section. Setting to False"
        )
        json_save = False

    try:
        root_uri = config.get("mirror", "root_uri")
    except configparser.NoOptionError:
        root_uri = ""

    try:
        diff_file_path = config.get("mirror", "diff-file")
    except configparser.NoOptionError:
        diff_file_path = ""
    if "{{" in diff_file_path and "}}" in diff_file_path:
        diff_file_path = diff_file_path.replace("{{", "").replace("}}", "")
        diff_ref_section, _, diff_ref_key = diff_file_path.partition("_")
        try:
            diff_file_path = config.get(diff_ref_section, diff_ref_key)
        except (configparser.NoOptionError, configparser.NoSectionError):
            logger.error(
                "Invalid section reference in `diff-file` key. "
                "Please correct this error. Saving diff files in"
                " base mirror directory."
            )
            diff_file_path = str(
                Path(config.get("mirror", "directory")) / "mirrored-files"
            )

    try:
        diff_append_epoch = config.getboolean("mirror", "diff-append-epoch")
    except configparser.NoOptionError:
        diff_append_epoch = False

    try:
        logger.debug("Checking config for storage backend...")
        storage_backend_name = config.get("mirror", "storage-backend")
        logger.debug("Found storage backend in config!")
    except configparser.NoOptionError:
        storage_backend_name = "filesystem"
        logger.debug(
            "Failed to find storage backend in config, falling back to default!"
        )
    logger.info(f"Selected storage backend: {storage_backend_name}")

    try:
        digest_name = config.get("mirror", "digest_name")
    except configparser.NoOptionError:
        digest_name = "sha256"
    if digest_name not in ("md5", "sha256"):
        raise ValueError(
            f"Supplied digest_name {digest_name} is not supported! Please "
            + "update digest_name to one of ('sha256', 'md5') in the [mirror] "
            + "section."
        )

    try:
        cleanup = config.getboolean("mirror", "cleanup")
    except configparser.NoOptionError:
        logger.debug(
            "bandersnatch is not cleaning up non PEP 503 normalized Simple "
            + "API directories"
        )
        cleanup = False

    return SetConfigValues(
        json_save,
        root_uri,
        diff_file_path,
        diff_append_epoch,
        digest_name,
        storage_backend_name,
        cleanup,
    )
