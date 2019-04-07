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

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        self.keep = 0  # default, keep 'em all
        try:
            self.keep = int(self.configuration["latest_release"]["keep"])
        except KeyError:
            pass
        except ValueError:
            pass
        if self.keep > 0:
            logger.info(f"Initialized latest releases plugin with keep={self.keep}")

    def filter(self, releases):
        """
        Filter the dictionary {(release, files)}
        """
        keys = list(releases.keys())

        if self.keep == 0 or len(keys) <= self.keep:
            # return the unmodified releases list
            return releases

        # parse release tags with packaging.version.parse to order them
        versions = map(lambda v: (parse(v), v), keys)
        latest = sorted(versions)[-self.keep :]  # noqa: E203
        new_keys = list(map(itemgetter(1), latest))

        logger.debug(f"old {keys}")
        logger.debug(f"new {new_keys}")

        return {release: releases[release] for release in new_keys}
