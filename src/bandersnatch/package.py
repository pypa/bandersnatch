import asyncio
import logging
import os
import sys
from json import dump
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from urllib.parse import unquote, urlparse

from packaging.utils import canonicalize_name

from .errors import PackageNotFound, StaleMetadata
from .master import StalePage

if TYPE_CHECKING:  # pragma: no cover
    from .filter import Filter
    from .master import Master

# Bool to help us not spam the logs with certain log messages
display_filter_log = True
logger = logging.getLogger(__name__)


class Package:
    def __init__(self, name: str, serial: int = 0) -> None:
        self.name = canonicalize_name(name)
        self.raw_name = name
        self.serial = serial

        self._metadata: Optional[Dict] = None

    @property
    def metadata(self) -> Dict[str, Any]:
        assert self._metadata is not None, "Must fetch metadata before accessing it"
        return self._metadata

    @property
    def info(self) -> Dict[str, Any]:
        return self.metadata["info"]  # type: ignore

    @property
    def last_serial(self) -> int:
        return self.metadata["last_serial"]  # type: ignore

    @property
    def releases(self) -> Dict[str, List]:
        return self.metadata["releases"]  # type: ignore

    @property
    def release_files(self) -> List:
        release_files: List[Dict] = []

        for release in self.releases.values():
            release_files.extend(release)

        return release_files

    @property
    def json_file(self) -> Path:
        return Path(self.mirror.webdir / "json" / self.name)

    @property
    def json_pypi_symlink(self) -> Path:
        return Path(self.mirror.webdir / "pypi" / self.name / "json")

    @property
    def simple_directory(self) -> Path:
        if self.mirror.hash_index:
            return Path(self.mirror.webdir / "simple" / self.name[0] / self.name)
        return Path(self.mirror.webdir / "simple" / self.name)

    def save_json_metadata(self, package_info: Dict) -> bool:
        """
        Take the JSON metadata we just fetched and save to disk
        """
        try:
            # TODO: Fix this so it works with swift
            with self.mirror.storage_backend.rewrite(self.json_file) as jf:
                dump(package_info, jf, indent=4, sort_keys=True)
            self.mirror.diff_file_list.append(self.json_file)
        except Exception as e:
            logger.error(
                f"Unable to write json to {self.json_file}: {str(e)} ({type(e)})"
            )
            return False

        symlink_dir = self.json_pypi_symlink.parent
        symlink_dir.mkdir(exist_ok=True)
        # Lets always ensure symlink is pointing to correct self.json_file
        # In 4.0 we move to normalized name only so want to overwrite older symlinks
        if self.json_pypi_symlink.exists():
            self.json_pypi_symlink.unlink()
        self.json_pypi_symlink.symlink_to(
            os.path.relpath(self.json_file, self.json_pypi_symlink.parent)
        )

        return True

    async def update_metadata(self, attempts: int = 3) -> None:
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
            except StalePage:
                tries += 1
                logger.error(f"Stale serial for package {self.name} - Attempt {tries}")
                if tries < attempts:
                    logger.debug(f"Sleeping {sleep_on_stale}s to give CDN a chance")
                    await asyncio.sleep(sleep_on_stale)
                    sleep_on_stale *= 2
                    continue
                logger.error(
                    f"Stale serial for {self.name} ({self.serial}) "
                    + "not updating. Giving up."
                )
                raise StaleMetadata(package_name=self.name, attempts=attempts)

    def _filter_metadata(self, metadata_filters: List["Filter"]) -> bool:
        """
        Run the metadata filtering plugins
        """
        global display_filter_log
        if not metadata_filters:
            if display_filter_log:
                logger.info(
                    "No metadata filters are enabled. Skipping metadata filtering"
                )
                display_filter_log = False
            return True

        return all(plugin.filter(self.metadata) for plugin in metadata_filters)

    def _filter_release(
        self, release_data: Dict, release_filters: List["Filter"]
    ) -> bool:
        """
        Run the release filtering plugins
        """
        global display_filter_log
        if not release_filters:
            if display_filter_log:
                logger.info(
                    "No release filters are enabled. Skipping release filtering"
                )
                display_filter_log = False
            return True

        return all(plugin.filter(release_data) for plugin in release_filters)

    def _filter_all_releases(self, release_filters: List["Filter"]) -> bool:
        """
        Filter releases and removes releases that fail the filters
        """
        releases = list(self.releases.keys())
        for version in releases:
            if not self._filter_release(
                {"version": version, "releases": self.releases, "info": self.info},
                release_filters,
            ):
                del self.releases[version]
        if releases:
            return True
        return False

    def _filter_release_file(
        self, metadata: Dict, release_file_filters: List["Filter"]
    ) -> bool:
        """
        Run the release file filtering plugins
        """
        global display_filter_log
        if not release_file_filters:
            if display_filter_log:
                logger.info(
                    "No release file filters are enabled. Skipping release file filtering"  # noqa: E501
                )
                display_filter_log = False
            return True

        return all(plugin.filter(metadata) for plugin in release_file_filters)

    def _filter_all_releases_files(self, release_file_filters: List["Filter"]) -> bool:
        """
        Filter release files and remove empty releases after doing so.
        """
        releases = list(self.releases.keys())
        for version in releases:
            release_files = list(self.releases[version])
            for rfindex in reversed(range(len(release_files))):
                if not self._filter_release_file(
                    {
                        "info": self.info,
                        "release": version,
                        "release_file": self.releases[version][rfindex],
                    },
                    release_file_filters,
                ):
                    del self.releases[version][rfindex]
            if not self.releases[version]:
                del self.releases[version]

        if releases:
            return True
        return False
