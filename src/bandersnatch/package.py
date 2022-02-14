import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from packaging.utils import canonicalize_name

from .errors import ConnectionTimeout, PackageNotFound, StaleMetadata
from .master import StalePage

if TYPE_CHECKING:  # pragma: no cover
    from .filter import Filter
    from .master import Master


logger = logging.getLogger(__name__)


class Package:
    def __init__(self, name: str, serial: int = 0) -> None:
        self.name: str = canonicalize_name(name)
        self.raw_name = name
        self.serial = serial

        self._metadata: Optional[Dict] = None

    @property
    def metadata(self) -> Dict[str, Any]:
        assert self._metadata is not None, "Must fetch metadata before accessing it"
        return self._metadata

    @property
    def info(self) -> Any:
        return self.metadata["info"]

    @property
    def last_serial(self) -> int:
        return int(self.metadata["last_serial"])

    @property
    def releases(self) -> Any:
        return self.metadata["releases"]

    @property
    def release_files(self) -> List:
        release_files: List[Dict] = []

        for release in self.releases.values():
            release_files.extend(release)

        return release_files

    async def update_metadata(self, master: "Master", attempts: int = 3) -> None:
        tries = 0
        sleep_on_stale = 1

        while tries < attempts:
            try:
                logger.info(
                    f"Fetching metadata for package: {self.name} (serial {self.serial})"
                )
                self._metadata = await master.get_package_metadata(
                    self.name, serial=self.serial
                )
                return
            except PackageNotFound as e:
                logger.info(str(e))
                raise
            except (StalePage, asyncio.TimeoutError) as e:
                error_name, error_class = (
                    ("Stale serial", StaleMetadata)
                    if isinstance(e, StalePage)
                    else ("Timeout error", ConnectionTimeout)
                )

                tries += 1
                logger.error(f"{error_name} for package {self.name} - Attempt {tries}")
                if tries < attempts:
                    logger.debug(f"Sleeping {sleep_on_stale}s to give CDN a chance")
                    await asyncio.sleep(sleep_on_stale)
                    sleep_on_stale *= 2
                    continue
                logger.error(
                    f"{error_name} for {self.name} ({self.serial}) "
                    + "not updating. Giving up."
                )
                raise error_class(package_name=self.name, attempts=attempts)

    def filter_metadata(self, metadata_filters: List["Filter"]) -> bool:
        """
        Run the metadata filtering plugins
        """
        return all(plugin.filter(self.metadata) for plugin in metadata_filters)

    def filter_all_releases(self, release_filters: List["Filter"]) -> bool:
        """
        Filter releases and removes releases that fail the filters
        """
        releases = list(self.releases.keys())
        for version in releases:
            release_data = {
                "version": version,
                "releases": self.releases,
                "info": self.info,
            }
            if not all(plugin.filter(release_data) for plugin in release_filters):
                del self.releases[version]
        if releases:
            return True
        return False

    def filter_all_releases_files(self, release_file_filters: List["Filter"]) -> bool:
        """
        Filter release files and remove empty releases after doing so.
        """
        releases = list(self.releases.keys())
        for version in releases:
            release_files = list(self.releases[version])
            for rfindex in reversed(range(len(release_files))):
                metadata = {
                    "info": self.info,
                    "release": version,
                    "release_file": self.releases[version][rfindex],
                }
                if not all(plugin.filter(metadata) for plugin in release_file_filters):
                    del self.releases[version][rfindex]
            if not self.releases[version]:
                del self.releases[version]

        if releases:
            return True
        return False
