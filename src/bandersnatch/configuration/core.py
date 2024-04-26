"""
Module containing classes to access the bandersnatch configuration file
"""

import importlib.resources
import logging
import shutil
from configparser import BasicInterpolation, ConfigParser
from pathlib import Path
from typing import Any

from .mirror_options import MirrorOptions, get_mirror_options

logger = logging.getLogger("bandersnatch")


class BandersnatchConfig(ConfigParser):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        params = {
            # "allow_no_value": True,
            "delimiters": ("=",),
            "strict": True,
            "interpolation": BasicInterpolation(),
        }
        params.update(kwargs)
        super().__init__(*args, **params)  # type: ignore
        self._validated_mirror_options: MirrorOptions | None = None

    # This allows writing option names in the config file with either '_' or '-' as word separators
    def optionxform(self, optionstr: str) -> str:
        return optionstr.lower().replace("-", "_")

    def read_defaults_file(self) -> None:
        defaults_resource = importlib.resources.files("bandersnatch") / "default.conf"
        with defaults_resource.open() as defaults_file:
            self.read_file(defaults_file)

    def read_path(self, file_path: Path | str) -> None:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        with file_path.open() as cfg_file:
            self.read_file(cfg_file)

    def validate_core_options(self) -> MirrorOptions:
        if self._validated_mirror_options is None:
            self._validated_mirror_options = get_mirror_options(self)
        return self._validated_mirror_options

    @classmethod
    def from_path(
        cls, config_path: Path | str, *, with_defaults: bool = True
    ) -> "BandersnatchConfig":
        config = cls()

        # load default values from an embedded config file unless explicitly
        # disabled with a keyword argument
        if with_defaults:
            config.read_defaults_file()

        # load values from the user config file, which will overwrite any default
        # values from above if the same option is present in both
        config.read_path(config_path)

        return config


def copy_example_config(dest_path: Path) -> None:
    with importlib.resources.path("bandersnatch", "example.conf") as example_file:
        try:
            shutil.copy(example_file, dest_path)
        except OSError as e:
            logger.error(f"Could not create config file: {e}")
