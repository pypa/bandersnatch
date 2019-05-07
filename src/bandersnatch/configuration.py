"""
Module containing classes to access the bandersnatch configuration file
"""
import logging
import warnings
from configparser import ConfigParser
from typing import Any, Dict, NamedTuple, Optional, Type

import pkg_resources

logger = logging.getLogger("bandersnatch")


class DeprecatedKey(NamedTuple):
    old_section: str
    old_key: str
    new_section: str
    new_key: str
    deprecated_version: str


class Singleton(type):  # pragma: no cover
    _instances: Dict["Singleton", Type] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Type:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class BandersnatchConfig(metaclass=Singleton):
    # Ensure we only show the deprecations once
    SHOWN_DEPRECATIONS = False
    DEPRECATED_KEYS = {
        # "friendly_name": "DeprecatedKey",
        "Enabling Plugins": DeprecatedKey(
            "blacklist", "plugins", "plugins", "enabled", "4.0.0"
        )
    }

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
        self.default_config_file = pkg_resources.resource_filename(
            "bandersnatch", "default.conf"
        )
        self.config_file = config_file
        self.load_configuration()
        self.check_for_deprecations()

    def check_for_deprecations(self) -> None:
        if self.SHOWN_DEPRECATIONS:
            return

        for friendly_name, dk in self.DEPRECATED_KEYS.items():
            err_msg = (
                f"{friendly_name} keys will move from {dk.old_section}:{dk.old_key} "
                + f"to {dk.new_section}:{dk.new_key} in version {dk.deprecated_version}"
                + f" - Documentation @ https://bandersnatch.readthedocs.io/"
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
        self.config = ConfigParser()
        self.config.read(config_file)

        # Copy deprecated keys to the new keys if they exist
        if "blacklist" in self.config and "plugins" in self.config["blacklist"]:
            self.config["plugins"] = {}
            self.config["plugins"]["enabled"] = self.config["blacklist"]["plugins"]
