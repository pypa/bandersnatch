"""
Module containing classes to access the bandersnatch configuration file
"""
import logging
from configparser import ConfigParser
from typing import Any, Dict, List, NamedTuple, Optional, Type

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
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class BandersnatchConfig(metaclass=Singleton):
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
        self.default_config_file = pkg_resources.resource_filename(
            "bandersnatch", "default.conf"
        )
        self.config_file = config_file
        self.load_configuration()

    def load_configuration(self) -> None:
        """
        Read the configuration from a configuration file
        """
        config_file = self.default_config_file
        if self.config_file:
            config_file = self.config_file
        self.config = ConfigParser(delimiters=("="))
        self.config.optionxform = lambda option: option  # type: ignore
        self.config.read(config_file)
