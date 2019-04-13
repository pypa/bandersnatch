import logging
from operator import itemgetter

from packaging.version import parse

from bandersnatch.filter import FilterReleasePlugin

logger = logging.getLogger("bandersnatch")


class LatestReleaseFilter(FilterReleasePlugin):
    """
    Plugin to download only latest releases
    """

    name = "latest_release"
    keep = 0  # default, keep 'em all

    def initialize_plugin(self):
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

    def filter_versions(self, versions, current_version):
        """
        Filter the list of versions
        """

        if self.keep == 0 or len(versions) <= self.keep:
            # return the unmodified versions list
            return versions

        # parse release tags with packaging.version.parse to order them
        old = map(lambda v: (parse(v), v), versions)
        latest = sorted(old)[-self.keep :]  # noqa: E203
        latest = list(map(itemgetter(1), latest))

        if current_version and (current_version not in latest):
            # never remove the stable/official version
            latest[0] = current_version

        logger.debug(f"old {versions}")
        logger.debug(f"new {latest}")

        return latest
