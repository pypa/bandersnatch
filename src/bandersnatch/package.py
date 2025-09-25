import asyncio
import logging
from typing import TYPE_CHECKING, Any

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
        self._upstream_serial: int | None = None

        self._metadata: dict | None = None

    @property
    def metadata(self) -> dict[str, Any]:
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
    def release_files(self) -> list:
        release_files: list[dict] = []

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
            except (StalePage, TimeoutError) as e:
                # 如果是 StalePage 异常且启用了上游串行号兼容，尝试使用上游决定的串行号
                if isinstance(e, StalePage) and master.allow_upstream_serial_mismatch:
                    logger.warning(
                        f"Stale serial for package {self.name} (expected {self.serial}) - "
                        f"trying with upstream serial due to allow-upstream-serial-mismatch setting"
                    )
                    try:
                        # 不指定 serial，让上游决定
                        self._metadata = await master.get_package_metadata(self.name, serial=0)
                        # 更新本地 serial 为上游的 serial
                        if self._metadata and "last_serial" in self._metadata:
                            upstream_serial = int(self._metadata["last_serial"])
                            logger.info(
                                f"Package {self.name} serial updated from {self.serial} "
                                f"to upstream serial {upstream_serial}"
                            )
                            self.serial = upstream_serial
                            self._upstream_serial = upstream_serial
                        return
                    except Exception as retry_e:
                        logger.debug(f"Retry with upstream serial failed: {retry_e}")
                        # 继续原有的重试逻辑
                
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

    def filter_metadata(self, metadata_filters: list["Filter"]) -> bool:
        """
        Run the metadata filtering plugins
        """
        return all(plugin.filter(self.metadata) for plugin in metadata_filters)

    def filter_all_releases(self, release_filters: list["Filter"]) -> bool:
        """
        Filter releases and removes releases that fail the filters
        """
        releases = list(self.releases.keys())
        release_data = {
            "info": self.info,
        }
        pinned_version = False
        pinned_plugin = -1
        for plugin in release_filters:
            pinned_plugin += 1
            if plugin.name == "project_requirements_pinned":
                if plugin.pinned_version_exists(release_data):
                    pinned_version = True
                    break
        if pinned_version:
            pinned_filter = release_filters[pinned_plugin]
            for version in releases:
                release_data = {
                    "version": version,
                    "releases": self.releases,
                    "info": self.info,
                }
                if not pinned_filter.filter(release_data):
                    del self.releases[version]
        else:
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

    def filter_all_releases_files(self, release_file_filters: list["Filter"]) -> bool:
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
