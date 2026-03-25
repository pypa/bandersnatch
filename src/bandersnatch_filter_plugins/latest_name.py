import logging
from collections.abc import Iterator
from operator import itemgetter

from packaging.version import Version, parse

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class LatestReleaseFilter(FilterReleasePlugin):
    """
    Plugin to download only latest releases
    """

    name = "latest_release"
    keep = 0  # by default, keep 'em all
    # by default, sort by parsed version string, time (of release) is the other option
    sort_by = "version"

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
        try:
            sort_by = self.configuration["latest_release"]["sort_by"]
            if sort_by in ["time", "version"]:
                self.sort_by = sort_by
            else:
                logger.debug(
                    "sort_by only allows 'time' and 'version', and not '{}'".format(
                        sort_by
                    )
                )
            logger.info(
                f"Initialized latest releases plugin with sort_by={self.sort_by}"
            )
        except KeyError:
            return

    def filter(self, metadata: dict) -> bool:
        """
        Returns False if version fails the filter, i.e. is not a latest/current release
        """

        info: dict = metadata["info"]
        releases: dict = metadata["releases"]
        version: str = metadata["version"]

        if self.keep == 0 or self.keep > len(releases):
            return True

        getter_index = 1
        if self.sort_by == "time":
            getter_index = 0
            versions_sorted = sorted(
                releases.items(),
                key=lambda x: x[1][0]["upload_time_iso_8601"],
                reverse=True,
            )
        else:
            versions_pair: Iterator[tuple[Version, str]] = map(
                lambda v: (parse(v), v), releases.keys()
            )
            # Sort all versions
            versions_sorted = sorted(versions_pair, reverse=True)
        # Select the first few (larger) items
        versions_allowed = versions_sorted[: self.keep]
        # Collect string versions back into a list
        version_names = list(map(itemgetter(getter_index), versions_allowed))

        # Add back latest version if necessary
        if info.get("version") not in version_names:
            version_names[-1] = info.get("version")

        return version in version_names
