import logging
from operator import itemgetter
from typing import Dict, Sequence, Tuple, Union

from packaging.version import LegacyVersion, Version, parse

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class LatestReleaseFilter(FilterReleasePlugin):
    """
    Plugin to download only latest releases
    """

    name = "latest_release"
    keep = 0  # by default, keep 'em all
    latest: Sequence[str] = []

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
        if self.keep == 0:
            return True

        if not self.latest:
            info = metadata["info"]
            releases = metadata["releases"]
            versions = list(releases.keys())
            before = len(versions)

            if before <= self.keep:
                # not enough releases: do nothing
                return True

            versions_pair = map(lambda v: (parse(v), v), versions)
            latest_sorted: Sequence[Tuple[Union[LegacyVersion, Version], str]] = sorted(
                versions_pair
            )[
                -self.keep :  # noqa: E203
            ]
            self.latest = list(map(itemgetter(1), latest_sorted))

            current_version = info.get("version")
            if current_version and (current_version not in self.latest):
                # never remove the stable/official version
                self.latest[0] = current_version

        version = metadata["version"]
        return version in self.latest
