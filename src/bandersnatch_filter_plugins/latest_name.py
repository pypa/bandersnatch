import logging
from operator import itemgetter
from typing import Dict, List, Optional, Set, Union

from packaging.version import parse

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

    def filter(self, metadata: Dict) -> Optional[bool]:  # type: ignore[override]
        """
        Keep the latest releases
        """
        latest: Union[List, Set]
        info = metadata["info"]
        releases = metadata["releases"]

        if self.keep == 0:
            return None

        versions = list(releases.keys())
        before = len(versions)

        if before <= self.keep:
            # not enough releases: do nothing
            return None

        versions_pair = map(lambda v: (parse(v), v), versions)
        latest = sorted(versions_pair)[-self.keep :]  # noqa: E203
        latest = list(map(itemgetter(1), latest))

        current_version = info.get("version")
        if current_version and (current_version not in latest):
            # never remove the stable/official version
            latest[0] = current_version

        logger.debug(f"old {versions}")
        logger.debug(f"new {latest}")

        after = len(latest)
        latest = set(latest)
        for version in list(releases.keys()):
            if version not in latest:
                del releases[version]

        logger.debug(f"{self.name}: releases removed: {before - after}")
        if not releases:
            return False
        else:
            return True
