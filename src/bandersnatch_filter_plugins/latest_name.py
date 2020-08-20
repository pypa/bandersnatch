import logging
from operator import itemgetter
from typing import Dict, Iterator, Tuple, Union

from packaging.version import LegacyVersion, Version, parse

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class LatestReleaseFilter(FilterReleasePlugin):
    """
    Plugin to download only latest releases
    """

    name = "latest_release"
    keep = 0  # by default, keep 'em all

    def initialize_plugin(self) -> None:
        """
        Initialize the plugin reading patterns from the config.
        """
        if self.keep:
            return

        try:
            self.keep = int(self.configuration["latest_release"]["keep"])
        except KeyError:
            return
        except ValueError:
            return
        if self.keep > 0:
            logger.info(f"Initialized latest releases plugin with keep={self.keep}")

    def filter(self, metadata: Dict) -> bool:
        """
        Returns False if version fails the filter, i.e. is not a latest/current release
        """

        info: Dict = metadata["info"]
        releases: Dict = metadata["releases"]
        version: str = metadata["version"]

        if self.keep == 0 or self.keep > len(releases):
            return True

        versions_pair: Iterator[Tuple[Union[LegacyVersion, Version], str]] = map(
            lambda v: (parse(v), v), releases.keys()
        )
        # Sort all versions
        versions_sorted = sorted(versions_pair, reverse=True)
        # Select the first few (larger) items
        versions_allowed = versions_sorted[: self.keep]
        # Collect string versions back into a list
        version_names = list(map(itemgetter(1), versions_allowed))

        # Add back latest version if necessary
        if info.get("version") not in version_names:
            version_names[-1] = info.get("version")

        return version in version_names
