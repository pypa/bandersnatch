import logging
import re
from typing import Dict, List, Pattern
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from bandersnatch.filter import FilterMetadataPlugin, FilterReleaseFilePlugin

logger = logging.getLogger("bandersnatch")


class RegexProjectMetadataFilter(FilterMetadataPlugin):
    """
    Plugin to download only packages having metadata matching at least one of the  specified patterns.
    """

    name = "regex_project_metadata"
    initilized = False
    patterns: Dict = {}

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration["regex_project_metadata"]
        except KeyError:
            return
        else:
            logger.info(f"Initializing regex_project_metadata plugin")
            if not self.initilized:
                for k in config:
                    pattern_strings = [
                        pattern for pattern in config[k].split("\n") if pattern
                    ]
                    self.patterns[k] = [
                        re.compile(pattern_string) for pattern_string in pattern_strings
                    ]
                logger.info(
                    f"Initialized regex_project_metadata plugin with {self.patterns}"
                )
                self.initilized = True

    def filter(self, metadata: Dict) -> bool:
        """
        Filter out all projects that don't match the specificed metadata patterns.
        """
        # If no patterns set, always return true
        if not self.patterns:
            return True

        # Walk through keys by dotted path
        for k in self.patterns:
            path = k.split(".")
            node = metadata
            for p in path:
                if p in node and node[p] is not None:
                    node = node[p]
                else:
                    return False
            if not isinstance(node, list):
                node = [node]
            found = False
            for d in node:
                if any(pattern.match(d) for pattern in self.patterns[k]):
                    found = True
            if found:
                continue
            return False
        return True


class RegexReleaseFileMetadataFilter(FilterReleaseFilePlugin):
    """
    Plugin to download only release files having metadata matching at least one of the specified patterns.
    """

    name = "regex_release_file_metadata"
    initilized = False
    patterns: Dict = {}

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration["regex_release_file_metadata"]
        except KeyError:
            return
        else:
            logger.info(f"Initializing regex_release_file_metadata plugin")
            if not self.initilized:
                for k in config:
                    pattern_strings = [
                        pattern for pattern in config[k].split("\n") if pattern
                    ]
                    self.patterns[k] = [
                        re.compile(pattern_string) for pattern_string in pattern_strings
                    ]
                logger.info(
                    f"Initialized regex_release_file_metadata plugin with {self.patterns}"
                )
                self.initilized = True

    def filter(self, release_file: Dict) -> bool:
        """
        Remove all release files that don't match any of the specificed metadata patterns.
        """
        # If no patterns set, always return true
        if not self.patterns:
            return True

        # Walk through keys by dotted path
        for k in self.patterns:
            path = k.split(".")
            node = release_file
            for p in path:
                if p in node and node[p] is not None:
                    node = node[p]
                else:
                    return False
            if not isinstance(node, list):
                node = [node]
            found = False
            for d in node:
                if any(pattern.match(d) for pattern in self.patterns[k]):
                    found = True
            if found:
                continue
            return False
        return True


class VersionRangeReleaseFileMetadataFilter(FilterReleaseFilePlugin):
    """
    Plugin to download only release files having metadata enries matching specified version ranges.
    """

    name = "version_range_release_file_metadata"
    initilized = False
    specifiers: Dict = {}

    def initialize_plugin(self):
        """
        Initialize the plugin reading version ranges from the config.
        """
        try:
            config = self.configuration["version_range_release_file_metadata"]
        except KeyError:
            return
        else:
            logger.info(f"Initializing version_range_release_file_metadata plugin")
            if not self.initilized:
                for k in config:
                    self.specifiers[k] = SpecifierSet(config[k])
                logger.info(
                    f"Initialized version_range_release_file_metadata plugin with {self.specifiers}"
                )
                self.initilized = True

    def filter(self, release_file: Dict) -> bool:
        """
        Remove all release files who's metadata don't match any of the specificed version specifier.
        """
        # If no specifiers set, always return true
        if not self.specifiers:
            return True

        # Walk through keys by dotted path
        for k in self.specifiers:
            path = k.split(".")
            node = release_file
            for p in path:
                if p in node and node[p] is not None:
                    node = node[p]
                else:
                    return False
            if not node or self.specifiers[k].__and__(SpecifierSet(node)) is not None:
                continue
            return False

        return True
