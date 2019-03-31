import logging
import re

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class PreReleaseFilter(FilterReleasePlugin):
    """
    Filters releases considered pre-releases.
    """

    name = "prerelease_release"
    PRERELEASE_PATTERNS = (r".+rc\d$", r".+a(lpha)?\d$", r".+b(eta)?\d$", r".+dev\d$")

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        self.patterns = [
            re.compile(pattern_string) for pattern_string in self.PRERELEASE_PATTERNS
        ]

        logger.info(f"Initialized prerelease plugin with {self.patterns}")

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
