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
        # TODO: should retrieving the plugin's config be part of the base class?
        try:
            self.keep = int(self.configuration["latest_release"]["keep"])
            if self.keep < 1:
                self.keep = 1
        except KeyError:
            self.keep = 3
        except ValueError:
            self.keep = 3

        logger.info(f"Initialized latest releases plugin with keep={self.keep}")

    def filter(self, releases):
        """
        Filter the dictionary {(release, files)}
        """
        versions = map(lambda v: (parse(v), v), releases.keys())
        latest = sorted(versions)[-self.keep :]  # noqa
        new_keys = list(map(itemgetter(1), latest))
        logger.debug(f"old {list(releases.keys())}")
        logger.debug(f"new {new_keys}")
        return {release: releases[release] for release in new_keys}
