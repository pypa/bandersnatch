import logging
import re
from typing import Dict, List

from packaging.specifiers import SpecifierSet
from packaging.version import parse

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
    initilized = False
    patterns: Dict = {}

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration[self.name]
        except KeyError:
            return
        else:
            logger.info(f"Initializing {self.name} plugin")
            if not self.initilized:
                for k in config:
                    pattern_strings = [
                        pattern for pattern in config[k].split("\n") if pattern
                    ]
                    self.patterns[k] = [
                        re.compile(pattern_string) for pattern_string in pattern_strings
                    ]
                logger.info(f"Initialized {self.name} plugin with {self.patterns}")
                self.initilized = True

    def filter(self, metadata: Dict) -> bool:
        """
        Filter out all projects that don't match the specified metadata patterns.
        """
        # If no patterns set, always return true
        if not self.patterns:
            return True

        # Walk through keys of patterns dict and return True iff all match
        return all(self._match_node_at_path(k, metadata) for k in self.patterns)

    def _match_node_at_path(self, key: str, metadata):

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

    def _find_element_by_dotted_path(self, path, metadata):
        # Walk our metadata structure following dotted path.
        path = path.split(".")
        node = metadata
        for p in path:
            if p in node and node[p] is not None:
                node = node[p]
            else:
                return []
        if isinstance(node, list):
            return node
        else:
            return [node]

    def _match_any_patterns(self, key: str, values: List, nulls_match=True):
        results = []
        for pattern in self.patterns[key]:
            if nulls_match and not values:
                results.append(True)
                continue
            for value in values:
                results.append(pattern.match(value))
        return any(results)

    def _match_all_patterns(self, key: str, values: List, nulls_match=True):
        results = []
        for pattern in self.patterns[key]:
            if nulls_match and not values:
                results.append(True)
                continue
            results.append(any(pattern.match(v) for v in values))
        return all(results)

    def _match_none_patterns(self, key: str, values: List, nulls_match=True):
        return not self._match_any_patterns(key, values)


class RegexProjectMetadataFilter(FilterMetadataPlugin, RegexFilter):
    """
    Plugin to download only packages having metadata matching
    at least one of the  specified patterns.
    """

    name = "regex_project_metadata"
    match_patterns = "any"
    nulls_match = True
    initilized = False
    patterns: Dict = {}

    def initilize_plugin(self):
        RegexFilter.initialize_plugin(self)

    def filter(self, metadata: dict) -> bool:
        return RegexFilter.filter(self, metadata)


class RegexReleaseFileMetadataFilter(FilterReleaseFilePlugin, RegexFilter):
    """
    Plugin to download only release files having metadata
        matching at least one of the specified patterns.
    """

    name = "regex_release_file_metadata"
    match_patterns = "any"
    nulls_match = True
    initilized = False
    patterns: Dict = {}

    def initilize_plugin(self):
        RegexFilter.initialize_plugin(self)

    def filter(self, metadata: dict) -> bool:
        return RegexFilter.filter(self, metadata)


class VersionRangeFilter(Filter):
    """
    Plugin to download only items having metadata
        version ranges matching specified versions.
    """

    name = "version_range_filter"
    initilized = False
    specifiers: Dict = {}
    nulls_match = True

    def initialize_plugin(self):
        """
        Initialize the plugin reading version ranges from the config.
        """
        try:
            config = self.configuration["version_range_release_file_metadata"]
        except KeyError:
            return
        else:
            if not self.initilized:
                for k in config:
                    # self.specifiers[k] = SpecifierSet(config[k])
                    self.specifiers[k] = [
                        parse(ver) for ver in config[k].split("\n") if ver
                    ]
                logger.info(
                    f"Initialized version_range_release_file_metadata plugin with {self.specifiers}"  # noqa: E501
                )
                self.initilized = True

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

    def _find_element_by_dotted_path(self, path, metadata):
        # Walk our metadata structure following dotted path.
        path = path.split(".")
        node = metadata
        for p in path:
            if p in node and node[p] is not None:
                node = node[p]
            else:
                return None

        return node

    def _match_node_at_path(self, key: str, metadata):

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
        ospecs = SpecifierSet(node)
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
    initilized = False
    specifiers: Dict = {}
    nulls_match = True

    def initialize_plugin(self):
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
    initilized = False
    specifiers: Dict = {}
    nulls_match = True

    def initialize_plugin(self):
        VersionRangeFilter.initialize_plugin(self)

    def filter(self, metadata: dict) -> bool:
        return VersionRangeFilter.filter(self, metadata)
