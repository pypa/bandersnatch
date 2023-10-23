"""
Module containing classes to access the bandersnatch configuration file
"""

import configparser
import importlib.resources
import logging
from pathlib import Path
from typing import Any, NamedTuple

from .simple import SimpleDigest, SimpleFormat, get_digest_value, get_format_value

logger = logging.getLogger("bandersnatch")


class SetConfigValues(NamedTuple):
    json_save: bool
    root_uri: str
    diff_file_path: str
    diff_append_epoch: bool
    digest_name: str
    storage_backend_name: str
    cleanup: bool
    release_files_save: bool
    compare_method: str
    download_mirror: str
    download_mirror_no_fallback: bool
    simple_format: SimpleFormat


class Singleton(type):  # pragma: no cover
    _instances: dict["Singleton", type] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> type:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class BandersnatchConfig(metaclass=Singleton):
    # Ensure we only show the deprecations once
    SHOWN_DEPRECATIONS = False

    def __init__(self, config_file: str | None = None) -> None:
        """
        Bandersnatch configuration class singleton

        This class is a singleton that parses the configuration once at the
        start time.

        Parameters
        ==========
        config_file: str, optional
            Path to the configuration file to use
        """
        self.found_deprecations: list[str] = []
        self.default_config_file = str(
            importlib.resources.files("bandersnatch") / "default.conf"
        )
        self.config_file = config_file
        self.load_configuration()
        # Keeping for future deprecations ... Commenting to save function call etc.
        # self.check_for_deprecations()

    def check_for_deprecations(self) -> None:
        if self.SHOWN_DEPRECATIONS:
            return
        self.SHOWN_DEPRECATIONS = True

    def load_configuration(self) -> None:
        """
        Read the configuration from a configuration file
        """
        config_file = self.default_config_file
        if self.config_file:
            config_file = self.config_file
        self.config = configparser.ConfigParser(delimiters="=")
        # mypy is unhappy with us assigning to a method - (monkeypatching?)
        self.config.optionxform = lambda option: option  # type: ignore
        self.config.read(config_file)


def validate_config_values(  # noqa: C901
    config: configparser.ConfigParser,
) -> SetConfigValues:
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
        digest_name = get_digest_value(config.get("mirror", "digest_name"))
    except configparser.NoOptionError:
        digest_name = SimpleDigest.SHA256
        logger.debug(f"Using digest {digest_name} by default ...")
    except ValueError as e:
        logger.error(
            f"Supplied digest_name {config.get('mirror', 'digest_name')} is "
            + "not supported! Please update the digest_name in the [mirror] "
            + "section of your config to a supported digest value."
        )
        raise e

    try:
        cleanup = config.getboolean("mirror", "cleanup")
    except configparser.NoOptionError:
        logger.debug(
            "bandersnatch is not cleaning up non PEP 503 normalized Simple "
            + "API directories"
        )
        cleanup = False

    release_files_save = config.getboolean("mirror", "release-files", fallback=True)
    if not release_files_save and not root_uri:
        root_uri = "https://files.pythonhosted.org"
        logger.error(
            "Please update your config to include a root_uri in the [mirror] "
            + "section when disabling release file sync. Setting to "
            + root_uri
        )

    try:
        logger.debug("Checking config for compare method...")
        compare_method = config.get("mirror", "compare-method")
        logger.debug("Found compare method in config!")
    except configparser.NoOptionError:
        compare_method = "hash"
        logger.debug(
            "Failed to find compare method in config, falling back to default!"
        )
    if compare_method not in ("hash", "stat"):
        raise ValueError(
            f"Supplied compare_method {compare_method} is not supported! Please "
            + "update compare_method to one of ('hash', 'stat') in the [mirror] "
            + "section."
        )
    logger.info(f"Selected compare method: {compare_method}")

    try:
        logger.debug("Checking config for alternative download mirror...")
        download_mirror = config.get("mirror", "download-mirror")
        logger.info(f"Selected alternative download mirror {download_mirror}")
    except configparser.NoOptionError:
        download_mirror = ""
        logger.debug("No alternative download mirror found in config.")

    if download_mirror:
        try:
            logger.debug(
                "Checking config for only download from alternative download"
                + "mirror..."
            )
            download_mirror_no_fallback = config.getboolean(
                "mirror", "download-mirror-no-fallback"
            )
            if download_mirror_no_fallback:
                logger.info("Setting to download from mirror without fallback")
            else:
                logger.debug("Setting to fallback to original if download mirror fails")
        except configparser.NoOptionError:
            download_mirror_no_fallback = False
            logger.debug("No download mirror fallback setting found in config.")
    else:
        download_mirror_no_fallback = False
        logger.debug(
            "Skip checking download-mirror-no-fallback because dependent option"
            + "is not set in config."
        )

    try:
        simple_format = get_format_value(config.get("mirror", "simple-format"))
    except configparser.NoOptionError:
        logger.debug("Storing all Simple Formats by default ...")
        simple_format = SimpleFormat.ALL

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
    )
