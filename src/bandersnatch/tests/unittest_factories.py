"""utilities for setting up test environments in older unittest-style tests"""

from pathlib import Path
from unittest import mock

from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.filter import LoadedFilters
from bandersnatch.master import Master
from bandersnatch.mirror import BandersnatchMirror
from bandersnatch_storage_plugins.filesystem import FilesystemStorage


def mock_config(contents: str, with_defaults: bool = True) -> BandersnatchConfig:
    """
    Creates a config instance and loads the given INI content into it
    """
    instance = BandersnatchConfig()
    if with_defaults:
        instance.read_defaults_file()
    instance.read_string(contents)
    return instance


def mock_mirror(
    config_txt: str = "", homedir: Path | None = None, master: Master | None = None
) -> BandersnatchMirror:
    homedir = homedir or Path(".")
    config = mock_config(config_txt)
    master = master or mock.Mock()
    storage = FilesystemStorage(config=config)
    filters = LoadedFilters(config=config)
    return BandersnatchMirror(homedir, mock.Mock(), storage, filters)
