import logging
import re
from typing import List, Pattern

from bandersnatch.filter import FilterProjectPlugin, FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class RegexReleaseFilter(FilterReleasePlugin):
    """
    Filters releases based on regex patters defined by the user.
    """

    name = "regex_release"
    # Has to be iterable to ensure it works with any()
    patterns: List[Pattern] = []

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        # TODO: should retrieving the plugin's config be part of the base class?
        try:
            config = self.configuration["filter_regex"]["releases"]
        except KeyError:
            return
        else:
            if not self.patterns:
                pattern_strings = [pattern for pattern in config.split("\n") if pattern]
                self.patterns = [
                    re.compile(pattern_string) for pattern_string in pattern_strings
                ]

                logger.info(f"Initialized regex release plugin with {self.patterns}")

    def filter(self, info, releases):
        """
        Remove all release versions that match any of the specificed patterns.
        """
        for version in list(releases.keys()):
            if any(pattern.match(version) for pattern in self.patterns):
                del releases[version]


class RegexProjectFilter(FilterProjectPlugin):
    """
    Filters projects based on regex patters defined by the user.
    """

    name = "regex_project"
    # Has to be iterable to ensure it works with any()
    patterns: List[Pattern] = []

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration["filter_regex"]["packages"]
        except KeyError:
            return
        else:
            if not self.patterns:
                pattern_strings = [pattern for pattern in config.split("\n") if pattern]
                self.patterns = [
                    re.compile(pattern_string) for pattern_string in pattern_strings
                ]

                logger.info(f"Initialized regex release plugin with {self.patterns}")

    def check_match(self, name):
        """
        Check if a release version matches any of the specificed patterns.

        Parameters
        ==========
        name: str
            Release name

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """
        return any(pattern.match(name) for pattern in self.patterns)
