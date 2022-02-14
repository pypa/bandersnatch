import logging
import re
from configparser import SectionProxy
from typing import Any, Dict, List

from humanfriendly import InvalidSize, parse_size
from packaging.specifiers import SpecifierSet
from packaging.version import parse

from bandersnatch_filter_plugins.allowlist_name import AllowListProject

from bandersnatch.filter import Filter  # isort:skip
from bandersnatch.filter import FilterMetadataPlugin  # isort:skip
from bandersnatch.filter import FilterReleaseFilePlugin  # isort:skip


logger = logging.getLogger("bandersnatch")


class RegexFilter(Filter):
    """
    Plugin to download only packages having metadata matching
    at least one of the  specified patterns.
    """

    name = "regex_filter"
    match_patterns = "any"
    nulls_match = True
    initialized = False
    patterns: Dict = {}

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config: SectionProxy = self.configuration[self.name]
        except KeyError:
            return
        else:
            logger.info(f"Initializing {self.name} plugin")
            if not self.initialized:
                for k in config:
                    pattern_strings = [
                        pattern for pattern in config[k].split("\n") if pattern
                    ]
                    self.patterns[k] = [
                        re.compile(pattern_string) for pattern_string in pattern_strings
                    ]
                logger.info(f"Initialized {self.name} plugin with {self.patterns}")
                self.initialized = True

    def filter(self, metadata: Dict) -> bool:
        """
        Filter out all projects that don't match the specified metadata patterns.
        """
        # If no patterns set, always return true
        if not self.patterns:
            return True

        # Walk through keys of patterns dict and return True iff all match
        return all(self._match_node_at_path(k, metadata) for k in self.patterns)

    def _match_node_at_path(self, key: str, metadata: Dict) -> bool:

        # Grab any tags prepended to key
        tags = key.split(":")

        # Take anything following the last semicolon as the path to the node
        path = tags.pop()

        # Set our default matching rules for each key
        match_patterns = self.match_patterns
        nulls_match = self.nulls_match

        # Interpret matching rules in tags
        if tags:
            for tag in tags:
                if tag == "not-null":
                    nulls_match = False
                if tag == "match-null":
                    nulls_match = True
                elif tag == "all":
                    match_patterns = "all"
                elif tag == "any":
                    match_patterns = "any"
                elif tag == "none":
                    match_patterns = "none"

        # Get value (List) of node using dotted path given by key
        node = self._find_element_by_dotted_path(path, metadata)

        # Use selected match mode, defaulting to "any"
        if match_patterns == "all":
            return self._match_all_patterns(key, node, nulls_match=nulls_match)
        elif match_patterns == "none":
            return self._match_none_patterns(key, node, nulls_match=nulls_match)
        else:
            return self._match_any_patterns(key, node, nulls_match=nulls_match)

    # TODO: Add unittest and cleanup code + fix typing
    def _find_element_by_dotted_path(self, path: str, metadata: Dict) -> List:
        # Walk our metadata structure following dotted path.
        split_path = path.split(".")
        node = metadata
        for p in split_path:
            if p in node and node[p] is not None:
                node = node[p]
            else:
                return []
        if isinstance(node, list):  # type: ignore
            return node  # type: ignore
        else:
            return [node]

    def _match_any_patterns(
        self, key: str, values: List[str], nulls_match: bool = True
    ) -> bool:
        results = []
        for pattern in self.patterns[key]:
            if nulls_match and not values:
                results.append(True)
                continue
            for value in values:
                results.append(pattern.match(value))
        return any(results)

    def _match_all_patterns(
        self, key: str, values: List[str], nulls_match: bool = True
    ) -> bool:
        results = []
        for pattern in self.patterns[key]:
            if nulls_match and not values:
                results.append(True)
                continue
            results.append(any(pattern.match(v) for v in values))
        return all(results)

    def _match_none_patterns(
        self, key: str, values: List[str], nulls_match: bool = True
    ) -> bool:
        return not self._match_any_patterns(key, values)


class RegexProjectMetadataFilter(FilterMetadataPlugin, RegexFilter):
    """
    Plugin to download only packages having metadata matching
    at least one of the specified patterns.
    """

    name = "regex_project_metadata"
    match_patterns = "any"
    nulls_match = True
    initialized = False
    patterns: Dict = {}

    def initilize_plugin(self) -> None:
        RegexFilter.initialize_plugin(self)

    def filter(self, metadata: Dict) -> bool:
        return RegexFilter.filter(self, metadata)


class RegexReleaseFileMetadataFilter(FilterReleaseFilePlugin, RegexFilter):
    """
    Plugin to download only release files having metadata
        matching at least one of the specified patterns.
    """

    name = "regex_release_file_metadata"
    match_patterns = "any"
    nulls_match = True
    initialized = False
    patterns: Dict = {}

    def initilize_plugin(self) -> None:
        RegexFilter.initialize_plugin(self)

    def filter(self, metadata: Dict) -> bool:
        return RegexFilter.filter(self, metadata)


class SizeProjectMetadataFilter(FilterMetadataPlugin, AllowListProject):
    """
    Plugin to download only packages having total file sizes less than
    a configurable threshold.
    """

    name = "size_project_metadata"
    initialized = False
    max_package_size: int = 0
    allowlist_package_names: List[str] = []

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin reading settings from the config.
        """
        if not self.initialized:
            try:
                human_package_size = self.configuration["size_project_metadata"][
                    "max_package_size"
                ]
            except KeyError:
                logger.warning(
                    f"Unable to initialise {self.name} plugin;"
                    f"must create max_package_size in configuration."
                )
                return
            try:
                self.max_package_size = parse_size(human_package_size, binary=True)
            except InvalidSize:
                logger.warning(
                    f"Unable to initialise {self.name} plugin;"
                    f'max_package_size of "{human_package_size}" is not valid.'
                )
                return
            if self.max_package_size > 0:
                if not self.allowlist_package_names:
                    self.allowlist_package_names = (
                        self._determine_unfiltered_package_names()
                    )

                log_msg = (
                    f"Initialized metadata plugin {self.name} to block projects "
                    + f"> {self.max_package_size} bytes"
                )
                if self.allowlist_package_names:
                    log_msg += (
                        "; except packages in the allowlist: "
                        + f"{self.allowlist_package_names}"
                    )
                logger.info(log_msg)

            self.initialized = True

    def filter(self, metadata: Dict) -> bool:
        """
        Return False for projects with metadata indicating
        total file sizes greater than threshold.
        """
        if self.max_package_size <= 0:
            return True

        if self.allowlist_package_names and not self.check_match(
            name=metadata["info"]["name"]
        ):
            return True

        total_size = 0
        for release in metadata["releases"].values():
            for file in release:
                total_size += file["size"]

        return total_size <= self.max_package_size


class VersionRangeFilter(Filter):
    """
    Plugin to download only items having metadata
        version ranges matching specified versions.
    """

    name = "version_range_filter"
    initialized = False
    specifiers: Dict = {}
    nulls_match = True

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin reading version ranges from the config.
        """
        try:
            config: SectionProxy = self.configuration[
                "version_range_release_file_metadata"
            ]
        except KeyError:
            return
        else:
            if not self.initialized:
                for k in config:
                    # self.specifiers[k] = SpecifierSet(config[k])
                    self.specifiers[k] = [
                        parse(ver) for ver in config[k].split("\n") if ver
                    ]
                logger.info(
                    f"Initialized version_range_release_file_metadata plugin with {self.specifiers}"  # noqa: E501
                )
                self.initialized = True

    def filter(self, metadata: Dict) -> bool:
        """
        Return False for input not having metadata
        entries matching the specified version specifier.
        """
        # If no specifiers set, always return true
        if not self.specifiers:
            return True
        # Walk through keys of patterns dict and return True iff all match

        return all(self._match_node_at_path(k, metadata) for k in self.specifiers)

    def _find_element_by_dotted_path(self, path: str, metadata: Dict) -> Any:
        # Walk our metadata structure following dotted path.
        split_path = path.split(".")
        node = metadata
        for p in split_path:
            if p in node and node[p] is not None:
                node = node[p]
            else:
                return None

        return node

    def _match_node_at_path(self, key: str, metadata: Dict) -> bool:

        # Grab any tags prepended to key
        tags = key.split(":")

        # Take anything following the last semicolon as the path to the node
        path = tags.pop()

        # Set our default matching rules for each key
        nulls_match = self.nulls_match

        # Interpret matching rules in tags
        if tags:
            for tag in tags:
                if tag == "not-null":
                    nulls_match = False
                if tag == "match-null":
                    nulls_match = True

        # Get value (List) of node using dotted path given by key
        node = self._find_element_by_dotted_path(path, metadata)

        # Check for null matching
        if nulls_match and not node:
            return True

        # Check if SpeciferSet matches target versions
        # TODO: Figure out proper intersection of SpecifierSets
        ospecs: SpecifierSet = SpecifierSet(node)
        ispecs = self.specifiers[key]
        if any(ospecs.contains(ispec, prereleases=True) for ispec in ispecs):
            return True
        # Otherwise, fail
        logger.info(
            f"Failed check for {key}='{ospecs}' against '{ispecs}'"  # noqa: E501
        )
        return False


class VersionRangeProjectMetadataFilter(FilterMetadataPlugin, VersionRangeFilter):
    """
    Plugin to download only projects having metadata
        entries matching specified version ranges.
    """

    name = "version_range_project_metadata"
    initialized = False
    specifiers: Dict = {}
    nulls_match = True

    def initialize_plugin(self) -> None:
        VersionRangeFilter.initialize_plugin(self)

    def filter(self, metadata: dict) -> bool:
        return VersionRangeFilter.filter(self, metadata)


class VersionRangeReleaseFileMetadataFilter(
    FilterReleaseFilePlugin, VersionRangeFilter
):
    """
    Plugin to download only release files having metadata
        entries matching specified version ranges.
    """

    name = "version_range_release_file_metadata"
    initialized = False
    specifiers: Dict = {}
    nulls_match = True

    def initialize_plugin(self) -> None:
        VersionRangeFilter.initialize_plugin(self)

    def filter(self, metadata: dict) -> bool:
        return VersionRangeFilter.filter(self, metadata)
