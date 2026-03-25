import logging
import re
from re import Pattern

from packaging.utils import canonicalize_name

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
    patterns: list[Pattern] = []
    package_names: list[str] = []

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

        if not self.package_names:
            try:
                lines = self.configuration["filter_prerelease"]["packages"]
                self.package_names = [
                    canonicalize_name(package_line.strip())
                    for package_line in lines.split("\n")
                    if package_line.strip()
                ]
            except KeyError:
                pass
            logger.info(
                f"Initialized prerelease plugin {self.name}, filtering "
                + f"{self.package_names if self.package_names else 'all packages'}"
            )

    def filter(self, metadata: dict) -> bool:
        """
        Returns False if version fails the filter, i.e. follows a prerelease pattern
        """
        name = metadata["info"]["name"]
        version = metadata["version"]
        if self.package_names and name not in self.package_names:
            return True
        return not any(pattern.match(version) for pattern in self.patterns)
