import asyncio
import hashlib
import html
import logging
import os
import sys
from json import dump
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from urllib.parse import unquote, urlparse

from packaging.utils import canonicalize_name

from . import utils
from .master import PackageNotFound, StalePage

if TYPE_CHECKING:  # pragma: no cover
    from .mirror import Mirror
    from .filter import Filter, LoadedFilters

# Bool to help us not spam the logs with certain log messages
display_filter_log = True
logger = logging.getLogger(__name__)


class StaleMetadata(Exception):
    """We attempted to retreive metadata from PyPI, but it was stale."""

    def __init__(self, package_name: str, attempts: int) -> None:
        super().__init__()
        self.package_name = package_name
        self.attempts = attempts

    def __str__(self) -> str:
        return f"Stale serial for {self.package_name} after {self.attempts} attempts"


class Package:
    def __init__(self, name: str, serial: Union[int, str], mirror: "Mirror") -> None:
        self.name = canonicalize_name(name)
        self.raw_name = name
        self.serial = serial
        self.mirror = mirror
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
                self._metadata = await self.mirror.master.get_package_metadata(
                    self.name, serial=int(self.serial)
                )
                return
            except PackageNotFound as e:
                logger.info(str(e))
                return
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

    async def sync(self, filters: "LoadedFilters", attempts: int = 3) -> None:
        self.json_saved = False

        try:
            await self.update_metadata(attempts=attempts)
            # Don't save anything if our metadata filters all fail.
            if not self.metadata or not self._filter_metadata(
                self.metadata, filters.filter_metadata_plugins()
            ):
                return None

            # save the metadata before filtering releases
            if self.mirror.json_save and not self.json_saved:
                loop = asyncio.get_event_loop()
                self.json_saved = await loop.run_in_executor(
                    None, self.save_json_metadata, self.metadata
                )

            self._filter_all_releases_files(filters.filter_release_file_plugins())
            self._filter_all_releases(filters.filter_release_plugins())

            await self.sync_release_files()
            self.sync_simple_page()
            # XMLRPC PyPI Endpoint stores raw_name so we need to provide it
            self.mirror.record_finished_package(self.raw_name)
        except Exception:
            logger.exception(f"Error syncing package: {self.name}@{self.serial}")
            self.mirror.errors = True

        if self.mirror.errors and self.mirror.stop_on_error:
            logger.error("Exiting early after error.")
            sys.exit(1)

    def _filter_metadata(
        self, metadata: Dict, metadata_filters: List["Filter"]
    ) -> bool:
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

        return all(plugin.filter(metadata) for plugin in metadata_filters)

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

    async def sync_release_files(self) -> None:
        """ Purge + download files returning files removed + added """
        downloaded_files = set()
        deferred_exception = None
        for release_file in self.release_files:
            try:
                downloaded_file = await self.download_file(
                    release_file["url"], release_file["digests"]["sha256"]
                )
                if downloaded_file:
                    downloaded_files.add(
                        str(downloaded_file.relative_to(self.mirror.homedir))
                    )
            except Exception as e:
                logger.exception(
                    "Continuing to next file after error downloading: "
                    f"{release_file['url']}"
                )
                if not deferred_exception:  # keep first exception
                    deferred_exception = e
        if deferred_exception:
            raise deferred_exception  # raise the exception after trying all files

        self.mirror.altered_packages[self.name] = downloaded_files

    def gen_data_requires_python(self, release: Dict) -> str:
        if "requires_python" in release and release["requires_python"] is not None:
            return f' data-requires-python="{html.escape(release["requires_python"])}"'
        return ""

    def generate_simple_page(self) -> str:
        # Generate the header of our simple page.
        simple_page_content = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "  <head>\n"
            "    <title>Links for {0}</title>\n"
            "  </head>\n"
            "  <body>\n"
            "    <h1>Links for {0}</h1>\n"
        ).format(self.raw_name)

        logger.debug(
            f"There are {len(self.releases.values())} releases for {self.name}"
        )
        release_files = self.release_files
        # Lets sort based on the filename rather than the whole URL
        release_files.sort(key=lambda x: x["filename"])

        digest_name = self.mirror.digest_name

        simple_page_content += "\n".join(
            [
                '    <a href="{}#{}={}"{}>{}</a><br/>'.format(
                    self._file_url_to_local_url(r["url"]),
                    digest_name,
                    r["digests"][digest_name],
                    self.gen_data_requires_python(r),
                    r["filename"],
                )
                for r in release_files
            ]
        )

        simple_page_content += f"\n  </body>\n</html>\n<!--SERIAL {self.last_serial}-->"

        return simple_page_content

    def sync_simple_page(self) -> None:
        logger.info(f"Storing index page: {self.name} - in {self.simple_directory}")
        simple_page_content = self.generate_simple_page()
        if not self.simple_directory.exists():
            self.simple_directory.mkdir(parents=True)

        if self.mirror.keep_index_versions > 0:
            self._save_simple_page_version(simple_page_content)
        else:
            simple_page = self.simple_directory / "index.html"
            with self.mirror.storage_backend.rewrite(
                simple_page, "w", encoding="utf-8"
            ) as f:
                f.write(simple_page_content)
            self.mirror.diff_file_list.append(simple_page)

    def _save_simple_page_version(self, simple_page_content: str) -> None:
        versions_path = self._prepare_versions_path()
        timestamp = utils.make_time_stamp()
        version_file_name = f"index_{self.serial}_{timestamp}.html"
        full_version_path = versions_path / version_file_name
        # TODO: Change based on storage backend
        with self.mirror.storage_backend.rewrite(
            full_version_path, "w", encoding="utf-8"
        ) as f:
            f.write(simple_page_content)
        self.mirror.diff_file_list.append(full_version_path)

        symlink_path = self.simple_directory / "index.html"
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()

        symlink_path.symlink_to(full_version_path)

    def _prepare_versions_path(self) -> Path:
        versions_path = (
            self.mirror.storage_backend.PATH_BACKEND(self.simple_directory) / "versions"
        )
        if not versions_path.exists():
            versions_path.mkdir()
        else:
            version_files = list(sorted(versions_path.iterdir()))
            version_files_to_remove = (
                len(version_files) - self.mirror.keep_index_versions + 1
            )
            for i in range(version_files_to_remove):
                version_files[i].unlink()

        return versions_path

    def _file_url_to_local_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.path.startswith("/packages"):
            raise RuntimeError(f"Got invalid download URL: {url}")
        prefix = self.mirror.root_uri if self.mirror.root_uri else "../.."
        return prefix + parsed.path

    # TODO: This can also return SwiftPath instances now...
    def _file_url_to_local_path(self, url: str) -> Path:
        path = urlparse(url).path
        path = unquote(path)
        if not path.startswith("/packages"):
            raise RuntimeError(f"Got invalid download URL: {url}")
        path = path[1:]
        return self.mirror.webdir / path

    # TODO: This can also return SwiftPath instances now...
    async def download_file(
        self, url: str, sha256sum: str, chunk_size: int = 64 * 1024
    ) -> Optional[Path]:
        path = self._file_url_to_local_path(url)

        # Avoid downloading again if we have the file and it matches the hash.
        if path.exists():
            existing_hash = self.mirror.storage_backend.get_hash(str(path))
            if existing_hash == sha256sum:
                return None
            else:
                logger.info(
                    f"Checksum mismatch with local file {path}: expected {sha256sum} "
                    + f"got {existing_hash}, will re-download."
                )
                path.unlink()

        logger.info(f"Downloading: {url}")

        dirname = path.parent
        if not dirname.exists():
            dirname.mkdir(parents=True)

        # Even more special handling for the serial of package files here:
        # We do not need to track a serial for package files
        # as PyPI generally only allows a file to be uploaded once
        # and then maybe deleted. Re-uploading (and thus changing the hash)
        # is only allowed in extremely rare cases with intervention from the
        # PyPI admins.
        r_generator = self.mirror.master.get(url, required_serial=None)
        response = await r_generator.asend(None)

        checksum = hashlib.sha256()

        with self.mirror.storage_backend.rewrite(path, "wb") as f:
            while True:
                chunk = await response.content.read(chunk_size)
                if not chunk:
                    break
                checksum.update(chunk)
                f.write(chunk)

            existing_hash = checksum.hexdigest()
            if existing_hash != sha256sum:
                # Bad case: the file we got does not match the expected
                # checksum. Even if this should be the rare case of a
                # re-upload this will fix itself in a later run.
                raise ValueError(
                    f"Inconsistent file. {url} has hash {existing_hash} "
                    + f"instead of {sha256sum}."
                )

        return path
