"""
Blocklist management
"""
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List

import pkg_resources

from .configuration import BandersnatchConfig

if TYPE_CHECKING:
    from configparser import SectionProxy


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


class Filter:
    """
    Base Filter class
    """

    name = "filter"
    deprecated_name: str = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.configuration = BandersnatchConfig().config
        if (
            "plugins" not in self.configuration
            or "enabled" not in self.configuration["plugins"]
        ):
            return

        split_plugins = self.configuration["plugins"]["enabled"].split("\n")
        if (
            "all" not in split_plugins
            and self.name not in split_plugins
            # TODO: Remove after 5.0
            and not (self.deprecated_name and self.deprecated_name in split_plugins)
        ):
            return

        self.initialize_plugin()

    def initialize_plugin(self) -> None:
        """
        Code to initialize the plugin
        """
        # The initialize_plugin method is run once to initialize the plugin. This should
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

    @property
    def allowlist(self) -> "SectionProxy":
        return self.configuration["allowlist"]

    @property
    def blocklist(self) -> "SectionProxy":
        return self.configuration["blocklist"]


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
    Plugin that modifies the download of specific releases or dist files
    """

    name = "release_plugin"


class FilterReleaseFilePlugin(Filter):
    """
    Plugin that modify the download of specific release or dist files
    """

    name = "release_file_plugin"


class LoadedFilters:
    """
    A class to load all of the filters enabled
    """

    ENTRYPOINT_GROUPS = [
        PROJECT_PLUGIN_RESOURCE,
        METADATA_PLUGIN_RESOURCE,
        RELEASE_PLUGIN_RESOURCE,
        RELEASE_FILE_PLUGIN_RESOURCE,
    ]

    def __init__(self, load_all: bool = False) -> None:
        """
        Loads and stores all of specified filters from the config file
        """
        self.config = BandersnatchConfig().config
        self.loaded_filter_plugins: Dict[str, List["Filter"]] = defaultdict(list)
        self.enabled_plugins = self._load_enabled()
        if load_all:
            self._load_filters(self.ENTRYPOINT_GROUPS)

    def _load_enabled(self) -> List[str]:
        """
        Reads the config and returns all the enabled plugins
        """
        enabled_plugins: List[str] = []
        try:
            config_plugins = self.config["plugins"]["enabled"]
            split_plugins = config_plugins.split("\n")
            if "all" in split_plugins:
                enabled_plugins = ["all"]
            else:
                for plugin in split_plugins:
                    if not plugin:
                        continue
                    enabled_plugins.append(plugin)
        except KeyError:
            pass
        return enabled_plugins

    def _load_filters(self, groups: List[str]) -> None:
        """
        Loads filters from the entry-point groups specified in groups
        """
        for group in groups:
            plugins = set()
            for entry_point in pkg_resources.iter_entry_points(group=group):
                plugin_class = entry_point.load()
                plugin_instance = plugin_class()
                if (
                    "all" in self.enabled_plugins
                    or plugin_instance.name in self.enabled_plugins
                    or plugin_instance.deprecated_name in self.enabled_plugins
                ):
                    plugins.add(plugin_instance)

            self.loaded_filter_plugins[group] = list(plugins)

    def filter_project_plugins(self) -> List[Filter]:
        """
        Load and return the project filtering plugin objects

        Returns
        -------
        list of bandersnatch.filter.Filter:
            List of objects derived from the bandersnatch.filter.Filter class
        """
        if PROJECT_PLUGIN_RESOURCE not in self.loaded_filter_plugins:
            self._load_filters([PROJECT_PLUGIN_RESOURCE])
        return self.loaded_filter_plugins[PROJECT_PLUGIN_RESOURCE]

    def filter_metadata_plugins(self) -> List[Filter]:
        """
        Load and return the metadata filtering plugin objects

        Returns
        -------
        list of bandersnatch.filter.Filter:
            List of objects derived from the bandersnatch.filter.Filter class
        """
        if METADATA_PLUGIN_RESOURCE not in self.loaded_filter_plugins:
            self._load_filters([METADATA_PLUGIN_RESOURCE])
        return self.loaded_filter_plugins[METADATA_PLUGIN_RESOURCE]

    def filter_release_plugins(self) -> List[Filter]:
        """
        Load and return the release filtering plugin objects

        Returns
        -------
        list of bandersnatch.filter.Filter:
            List of objects derived from the bandersnatch.filter.Filter class
        """
        if RELEASE_PLUGIN_RESOURCE not in self.loaded_filter_plugins:
            self._load_filters([RELEASE_PLUGIN_RESOURCE])
        return self.loaded_filter_plugins[RELEASE_PLUGIN_RESOURCE]

    def filter_release_file_plugins(self) -> List[Filter]:
        """
        Load and return the release file filtering plugin objects

        Returns
        -------
        list of bandersnatch.filter.Filter:
            List of objects derived from the bandersnatch.filter.Filter class
        """
        if RELEASE_FILE_PLUGIN_RESOURCE not in self.loaded_filter_plugins:
            self._load_filters([RELEASE_FILE_PLUGIN_RESOURCE])
        return self.loaded_filter_plugins[RELEASE_FILE_PLUGIN_RESOURCE]
