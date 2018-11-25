import logging
import re

from bandersnatch.filter import FilterProjectPlugin, FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class RegexReleaseFilter(FilterReleasePlugin):
    """
    Filters releases based on regex patters defined by the user.
    """

    name = "regex_release"

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        # TODO: should retrieving the plugin's config be part of the base class?
        try:
            config = self.configuration["filter_regex"]["releases"]
        except KeyError:
            self.patterns = []
        else:
            pattern_strings = [pattern for pattern in config.split("\n") if pattern]
            self.patterns = [
                re.compile(pattern_string) for pattern_string in pattern_strings
            ]

            logger.info(f"Initialized regex release plugin with {self.patterns}")

    def check_match(self, name, version):
        """
        Check if a release version matches any of the specificed patterns.

        Parameters
        ==========
        name: str
            Release name
        version: str
            Release version

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """
        return any(pattern.match(version) for pattern in self.patterns)


class RegexProjectFilter(FilterProjectPlugin):
    """
    Filters projects based on regex patters defined by the user.
    """

    name = "regex_project"

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        try:
            config = self.configuration["filter_regex"]["packages"]
        except KeyError:
            self.patterns = []
        else:
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
