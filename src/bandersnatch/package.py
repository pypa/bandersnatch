import hashlib
import html
import logging
import os.path
import sys
import time
from datetime import datetime
from json import dump
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import unquote, urlparse

import pkg_resources
import requests
from packaging.utils import canonicalize_name

from . import utils
from .filter import filter_filename_plugins, filter_release_plugins
from .master import StalePage

# Bool to help us not spam the logs with certain log messages
display_filter_log = True
logger = logging.getLogger(__name__)


class Package:

    tries = 0
    sleep_on_stale = 1

    def __init__(self, name, serial, mirror):
        self.name = name
        self.serial = serial
        self.normalized_name = canonicalize_name(name)
        # This is really only useful for pip 8.0 -> 8.1.1
        self.normalized_name_legacy = pkg_resources.safe_name(name).lower()
        self.mirror = mirror

    @property
    def json_file(self) -> Path:
        return self.mirror.webdir / "json" / self.name

    @property
    def json_pypi_symlink(self) -> Path:
        return self.mirror.webdir / "pypi" / self.name / "json"

    @property
    def simple_directory(self) -> Path:
        if self.mirror.hash_index:
            return self.mirror.webdir / "simple" / self.name[0] / self.name
        return self.mirror.webdir / "simple" / self.name

    @property
    def normalized_simple_directory(self) -> Path:
        if self.mirror.hash_index:
            return (
                self.mirror.webdir
                / "simple"
                / self.normalized_name[0]
                / self.normalized_name
            )
        return self.mirror.webdir / "simple" / self.normalized_name

    @property
    def normalized_legacy_simple_directory(self) -> Path:
        if self.mirror.hash_index:
            return (
                self.mirror.webdir
                / "simple"
                / self.normalized_name[0]
                / self.normalized_name_legacy
            )
        return self.mirror.webdir / "simple" / self.normalized_name_legacy

    def save_json_metadata(self, package_info: Dict) -> bool:
        """
        Take the JSON metadata we just fetched and save to disk
        """

        try:
            with utils.rewrite(self.json_file) as jf:
                dump(package_info, jf, indent=4, sort_keys=True)
        except Exception as e:
            logger.error(
                "Unable to write json to {}: {}".format(self.json_file, str(e))
            )
            return False

        symlink_dir = self.json_pypi_symlink.parent
        if not symlink_dir.exists():
            symlink_dir.mkdir()
        try:
            # If symlink already exists throw a FileExistsError
            self.json_pypi_symlink.symlink_to(self.json_file)
        except FileExistsError:
            pass

        return True

    def sync(self, stop_on_error=False, attempts=3):
        self.tries = 0
        self.json_saved = False
        try:
            while self.tries < attempts:
                try:
                    logger.info(f"Syncing package: {self.name} (serial {self.serial})")
                    try:
                        package_info = self.mirror.master.get(
                            f"/pypi/{self.name}/json", self.serial
                        )
                    except requests.HTTPError as e:
                        if e.response.status_code == 404:
                            logger.info(f"{self.name} no longer exists on PyPI")
                            return
                        raise

                    self.releases = package_info.json()["releases"]

                    self._filter_releases()
                    self._filter_latest()
                    self._filter_filenames()

                    if self.mirror.json_save and not self.json_saved:
                        self.json_saved = self.save_json_metadata(package_info.json())

                    self.sync_release_files()
                    self.sync_simple_page()
                    self.mirror.record_finished_package(self.name)
                    break
                except StalePage:
                    self.tries += 1
                    logger.error(
                        "Stale serial for package {} - Attempt {}".format(
                            self.name, self.tries
                        )
                    )
                    # Give CDN a chance to update.
                    if self.tries < attempts:
                        time.sleep(self.sleep_on_stale)
                        self.sleep_on_stale *= 2
                        continue
                    logger.error(
                        "Stale serial for {} ({}) not updating. Giving up.".format(
                            self.name, self.serial
                        )
                    )
                    self.mirror.errors = True
        except Exception:
            logger.exception(f"Error syncing package: {self.name}@{self.serial}")
            self.mirror.errors = True

        if self.mirror.errors and stop_on_error:
            logger.error("Exiting early after error.")
            sys.exit(1)

    def _filter_releases(self):
        """
        Run the release filtering plugins and remove any releases from
        `releases` that match any filters.
        """
        global display_filter_log
        filter_plugins = filter_release_plugins()
        if not filter_plugins:
            if display_filter_log:
                logger.info("No package filters are enabled. Skipping filtering")
                display_filter_log = False
            return

        # Make a copy of self.releases keys
        # as we may delete packages during iteration
        versions = list(self.releases.keys())
        for version in versions:
            filter_ = False
            for plugin in filter_plugins:
                filter_ = filter_ or plugin.check_match(name=self.name, version=version)
            if filter_:
                del self.releases[version]

    def _filter_latest(self):
        """
        Run the 'keep the latest releases' plugin
        """
        filter_plugins = filter_release_plugins()
        if not filter_plugins:
            return

        before = len(self.releases.keys())
        for plugin in filter_plugins:
            if hasattr(plugin, "filter"):
                self.releases = plugin.filter(self.releases)
        after = len(self.releases.keys())
        logger.debug(f"{self.name}: removed (latest): {before - after}")

    def _filter_filenames(self):
        """
        Run the filename filtering plugins and remove any releases from
        `releases` that match any filters.
        """
        filter_plugins = filter_filename_plugins()
        if not filter_plugins:
            return

        # Make a copy of self.releases keys
        # as we may delete packages during iteration
        removed = 0
        versions = list(self.releases.keys())
        for version in versions:
            new_files = []
            for file_desc in self.releases[version]:
                if any(plugin.check_match(file_desc) for plugin in filter_plugins):
                    removed += 1
                else:
                    new_files.append(file_desc)
            if len(new_files) == 0:
                del self.releases[version]
            else:
                self.releases[version] = new_files
        logger.debug(f"{self.name}: removed (filename): {removed}")

    # TODO: async def once we go full asyncio - Have concurrency at the
    # release file level
    def sync_release_files(self):
        """ Purge + download files returning files removed + added """
        release_files = []

        for release in self.releases.values():
            release_files.extend(release)

        downloaded_files = set()
        deferred_exception = None
        for release_file in release_files:
            try:
                downloaded_file = self.download_file(
                    release_file["url"], release_file["digests"]["sha256"]
                )
                if downloaded_file:
                    downloaded_files.add(
                        str(downloaded_file.relative_to(self.mirror.homedir))
                    )
            except Exception as e:
                logger.exception(
                    f"Continuing to next file after error downloading: "
                    f"{release_file['url']}"
                )
                if not deferred_exception:  # keep first exception
                    deferred_exception = e
        if deferred_exception:
            raise deferred_exception  # raise the exception after trying all files

        self.mirror.altered_packages[self.name] = downloaded_files

    def gen_data_requires_python(self, release):
        if "requires_python" in release and release["requires_python"] is not None:
            return (
                ' data-requires-python="'
                + html.escape(release["requires_python"])
                + '"'
            )
        return ""

    def generate_simple_page(self):
        # Generate the header of our simple page.
        simple_page_content = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "  <head>\n"
            "    <title>Links for {0}</title>\n"
            "  </head>\n"
            "  <body>\n"
            "    <h1>Links for {0}</h1>\n"
        ).format(self.name)

        # Get a list of all of the files.
        release_files = []
        logger.debug(
            f"There are {len(self.releases.values())} releases for {self.name}"
        )
        for release in self.releases.values():
            release_files.extend(release)
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

        simple_page_content += "\n  </body>\n</html>"

        return simple_page_content

    def sync_simple_page(self):
        logger.info(f"Storing index page: {self.name}")

        # We need to generate the actual content that we're going to be saving
        # to disk for our index files.
        simple_page_content = self.generate_simple_page()

        # This exists for compatability with pip 1.5 which will not fallback
        # to /simple/ to determine what URL to get packages from, but will just
        # fail. Once pip 1.6 is old enough to be considered a "minimum" this
        # can be removed.
        if self.simple_directory != self.normalized_simple_directory:
            if not self.simple_directory.exists():
                self.simple_directory.mkdir(parents=True)
            simple_page = self.simple_directory / "index.html"
            with utils.rewrite(simple_page, "w", encoding="utf-8") as f:
                f.write(simple_page_content)

            # This exists for compatibility with pip 8.0 to 8.1.1 which did not
            # correctly implement PEP 503 wrt to normalization and so needs a
            # partially directory to get. Once pip 8.1.2 is old enough to be
            # considered "minimum" this can be removed.
            if (
                self.normalized_simple_directory
                != self.normalized_legacy_simple_directory
            ):
                if not self.normalized_legacy_simple_directory.exists():
                    self.normalized_legacy_simple_directory.mkdir()
                simple_page = self.normalized_legacy_simple_directory / "index.html"
                with utils.rewrite(simple_page, "w", encoding="utf-8") as f:
                    f.write(simple_page_content)

        if not self.normalized_simple_directory.exists():
            self.normalized_simple_directory.mkdir(parents=True)

        if self.mirror.keep_index_versions > 0:
            self._save_simple_page_version(simple_page_content)
        else:
            normalized_simple_page = self.normalized_simple_directory / "index.html"
            with utils.rewrite(normalized_simple_page, "w", encoding="utf-8") as f:
                f.write(simple_page_content)

    def _save_simple_page_version(self, simple_page_content):
        versions_path = self._prepare_versions_path()
        timestamp = datetime.utcnow().isoformat() + "Z"
        version_file_name = f"index_{self.serial}_{timestamp}.html"
        full_version_path = versions_path / version_file_name
        with utils.rewrite(full_version_path, "w", encoding="utf-8") as f:
            f.write(simple_page_content)

        symlink_path = self.normalized_legacy_simple_directory / "index.html"
        if symlink_path.exists():
            symlink_path.unlink()

        symlink_path.symlink_to(full_version_path)

    def _prepare_versions_path(self) -> Path:
        versions_path = Path(self.normalized_legacy_simple_directory) / "versions"
        if not versions_path.exists():
            versions_path.mkdir()
        else:
            version_files = sorted(os.listdir(versions_path))
            version_files_to_remove = (
                len(version_files) - self.mirror.keep_index_versions + 1
            )
            for i in range(version_files_to_remove):
                (versions_path / version_files[i]).unlink()

        return versions_path

    def _file_url_to_local_url(self, url) -> str:
        parsed = urlparse(url)
        if not parsed.path.startswith("/packages"):
            raise RuntimeError(f"Got invalid download URL: {url}")
        prefix = self.mirror.root_uri if self.mirror.root_uri else "../.."
        return prefix + parsed.path

    def _file_url_to_local_path(self, url) -> Path:
        path = urlparse(url).path
        path = unquote(path)
        if not path.startswith("/packages"):
            raise RuntimeError(f"Got invalid download URL: {url}")
        path = path[1:]
        return self.mirror.webdir / path

    def download_file(self, url: str, sha256sum: str) -> Optional[Path]:
        path = self._file_url_to_local_path(url)

        # Avoid downloading again if we have the file and it matches the hash.
        if path.exists():
            existing_hash = utils.hash(str(path))
            if existing_hash == sha256sum:
                return None
            else:
                logger.info(
                    "Checksum mismatch with local file {}: "
                    "expected {} got {}, will re-download.".format(
                        path, sha256sum, existing_hash
                    )
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
        # Py3 sometimes has requests lib return bytes. Need to handle that
        r = self.mirror.master.get(url, required_serial=None, stream=True)
        checksum = hashlib.sha256()
        with utils.rewrite(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                checksum.update(chunk)
                f.write(chunk)
            existing_hash = checksum.hexdigest()
            if existing_hash == sha256sum:
                # Good case: the file we got matches the checksum we expected
                pass
            else:
                # Bad case: the file we got does not match the expected
                # checksum. Even if this should be the rare case of a
                # re-upload this will fix itself in a later run.
                raise ValueError(
                    "Inconsistent file. {} has hash {} instead of {}.".format(
                        url, existing_hash, sha256sum
                    )
                )
        return path
