"""
Blacklist management
"""
from collections import defaultdict
from typing import Any, Dict, Iterable, List

import pkg_resources

from .configuration import BandersnatchConfig

loaded_filter_plugins: Dict[str, List["Filter"]] = defaultdict(list)


class Filter:
    """
    Base Filter class
    """

    name = "filter"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.configuration = BandersnatchConfig().config
        self.initialize_plugin()

    def initialize_plugin(self) -> None:
        """
        Code to initialize the plugin
        """
        pass

    def check_match(self, **kwargs: Any) -> bool:
        """
        Check if the plugin matches based on the arguments provides.

        Returns
        =======
        bool:
            True if the values match a filter rule, False otherwise
        """
        return False


class FilterProjectPlugin(Filter):
    """
    Plugin that blocks sync operations for an entire project
    """

    name = "project_plugin"


class FilterReleasePlugin(Filter):
    """
    Plugin that blocks the download of specific release files
    """

    name = "release_plugin"


class FilterFilenamePlugin(Filter):
    """
    Plugin that blocks the download of specific package types or platforms
    """

    name = "filename_plugin"


def load_filter_plugins(entrypoint_group: str) -> Iterable[Filter]:
    """
    Load all blacklist plugins that are registered with pkg_resources

    Parameters
    ==========
    entrypoint_group: str
        The entrypoint group name to load plugins from

    Returns
    =======
    List of Blacklist:
        A list of objects derived from the Blacklist class
    """
    global loaded_filter_plugins
    enabled_plugins: List[str] = []
    config = BandersnatchConfig().config
    try:
        config_blacklist_plugins = config["blacklist"]["plugins"]
        split_plugins = config_blacklist_plugins.split("\n")
        if "all" in split_plugins:
            enabled_plugins = ["all"]
        else:
            for plugin in split_plugins:
                if not plugin:
                    continue
                enabled_plugins.append(plugin)
    except KeyError:
        pass

    # If the plugins for the entrypoint_group have been loaded return them
    cached_plugins = loaded_filter_plugins.get(entrypoint_group)
    if cached_plugins:
        return cached_plugins

    plugins = set()
    for entry_point in pkg_resources.iter_entry_points(group=entrypoint_group):
        plugin_class = entry_point.load()
        plugin_instance = plugin_class()
        if "all" in enabled_plugins or plugin_instance.name in enabled_plugins:
            plugins.add(plugin_instance)

    loaded_filter_plugins[entrypoint_group] = list(plugins)

    return plugins


def filter_project_plugins() -> Iterable[Filter]:
    """
    Load and return the release filtering plugin objects

    Returns
    -------
    list of bandersnatch.filter.Filter:
        List of objects derived from the bandersnatch.filter.Filter class
    """
    return load_filter_plugins("bandersnatch_filter_plugins.project")


def filter_release_plugins() -> Iterable[Filter]:
    """
    Load and return the release filtering plugin objects

    Returns
    -------
    list of bandersnatch.filter.Filter:
        List of objects derived from the bandersnatch.filter.Filter class
    """
    return load_filter_plugins("bandersnatch_filter_plugins.release")


def filter_filename_plugins() -> Iterable[Filter]:
    """
    Load and return the filename filtering plugin objects

    Returns
    -------
    list of bandersnatch.filter.Filter:
        List of objects derived from the bandersnatch.filter.Filter class
    """
    return load_filter_plugins("bandersnatch_filter_plugins.filename")
