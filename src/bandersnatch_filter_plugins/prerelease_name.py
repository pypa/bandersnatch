import logging
import re
from typing import Dict

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class PreReleaseFilter(FilterReleasePlugin):
    """
    Filters releases considered pre-releases.
    """

    name = "prerelease_release"
    PRERELEASE_PATTERNS = (
        r".+rc\d+$",
        r".+a(lpha)?\d+$",
        r".+b(eta)?\d+$",
        r".+dev\d+$",
    )
    patterns = None

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin reading patterns from the config.
        """
        if not self.patterns:
            self.patterns = [
                re.compile(pattern_string)
                for pattern_string in self.PRERELEASE_PATTERNS
            ]
            logger.info(f"Initialized prerelease plugin with {self.patterns}")

    def filter(self, metadata: Dict) -> bool:
        """
        Remove all release versions that match any of the specified patterns.
        """
        releases = metadata["releases"]
        for version in list(releases.keys()):
            if any(pattern.match(version) for pattern in self.patterns):  # type: ignore
                del releases[version]
        if not releases:
            return False
        else:
            return True
