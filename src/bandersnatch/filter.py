"""
Blacklist management
"""
from collections import defaultdict
from typing import Any, Dict, Iterable, List

import pkg_resources

from .configuration import BandersnatchConfig

# The API_REVISION is incremented if the plugin class is modified in a
# backwards incompatible way.  In order to prevent loading older
# broken plugins that may be installed and will break due to changes to
# the methods of the classes.
PLUGIN_API_REVISION = 2
PROJECT_PLUGIN_RESOURCE = f"bandersnatch_filter_plugins.v{PLUGIN_API_REVISION}.project"
METADATA_PLUGIN_RESOURCE = (
    f"bandersnatch_filter_plugins.v{PLUGIN_API_REVISION}.metadata"
)
RELEASE_PLUGIN_RESOURCE = f"bandersnatch_filter_plugins.v{PLUGIN_API_REVISION}.release"
RELEASE_FILE_PLUGIN_RESOURCE = (
    f"bandersnatch_filter_plugins.v{PLUGIN_API_REVISION}.release_file"
)
loaded_filter_plugins: Dict[str, List["Filter"]] = defaultdict(list)


class Filter:
    """
    Base Filter class
    """

    name = "filter"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.configuration = BandersnatchConfig().config
        if (
            "plugins" not in self.configuration
            or "enabled" not in self.configuration["plugins"]
        ):
            return

        split_plugins = self.configuration["plugins"]["enabled"].split("\n")
        if "all" not in split_plugins and self.name not in split_plugins:
            return

        self.initialize_plugin()

    def initialize_plugin(self) -> None:
        """
        Code to initialize the plugin
        """
        # The intialize_plugin method is run once to initialize the plugin.  This should
        # contain all code to set up the plugin.
        # This method is not run in the fast path and should be used to do things like
        # indexing filter databases, etc that will speed the operation of the filter
        # and check_match methods that are called in the fast path.
        pass

    def filter(self, metadata: dict) -> bool:
        """
        Check if the plugin matches based on the package's metadata.

        Returns
        =======
        bool:
            True if the values match a filter rule, False otherwise
        """
        return False

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


class FilterMetadataPlugin(Filter):
    """
    Plugin that blocks sync operations for an entire project based on info fields.
    """

    name = "metadata_plugin"


class FilterReleasePlugin(Filter):
    """
    Plugin that modify  the download of specific release or dist files
    """

    name = "release_plugin"


class FilterReleaseFilePlugin(Filter):
    """
    Plugin that modify  the download of specific release or dist files
    """

    name = "release_file_plugin"


def load_filter_plugins(entrypoint_group: str) -> Iterable[Filter]:
    """
    Load all blacklist plugins that are registered with importlib.resources

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
        config_blacklist_plugins = config["plugins"]["enabled"]
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
    return load_filter_plugins(PROJECT_PLUGIN_RESOURCE)


def filter_metadata_plugins() -> Iterable[Filter]:
    """
    Load and return the release filtering plugin objects

    Returns
    -------
    list of bandersnatch.filter.Filter:
        List of objects derived from the bandersnatch.filter.Filter class
    """
    return load_filter_plugins(METADATA_PLUGIN_RESOURCE)


def filter_release_plugins() -> Iterable[Filter]:
    """
    Load and return the release filtering plugin objects

    Returns
    -------
    list of bandersnatch.filter.Filter:
        List of objects derived from the bandersnatch.filter.Filter class
    """
    return load_filter_plugins(RELEASE_PLUGIN_RESOURCE)


def filter_release_file_plugins() -> Iterable[Filter]:
    """
    Load and return the release file filtering plugin objects

    Returns
    -------
    list of bandersnatch.filter.Filter:
        List of objects derived from the bandersnatch.filter.Filter class
    """
    return load_filter_plugins(RELEASE_FILE_PLUGIN_RESOURCE)
