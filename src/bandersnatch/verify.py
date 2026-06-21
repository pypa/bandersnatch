import argparse
import asyncio
import concurrent.futures
import datetime
import json
import logging
import sys
from argparse import Namespace
from asyncio.queues import Queue
from collections.abc import Sequence
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from sys import stderr
from urllib.parse import urlparse

import aiohttp
from humanfriendly import format_size

from .filter import LoadedFilters
from .master import Master
from .mirror import fetch_and_store
from .package import Package
from .storage import PATH_TYPES, FileSpec, Storage, storage_backend_plugins
from .utils import convert_url_to_path

logger = logging.getLogger(__name__)


@dataclass
class DryRunDownloadStats:
    bad_count: int = 0
    bad_bytes: int = 0
    unknown_size_count: int = 0

    def __add__(self, other: "DryRunDownloadStats") -> "DryRunDownloadStats":
        return DryRunDownloadStats(
            self.bad_count + other.bad_count,
            self.bad_bytes + other.bad_bytes,
            self.unknown_size_count + other.unknown_size_count,
        )

    def record_bad(self, size: int) -> None:
        if size == 0:
            self.unknown_size_count += 1
        self.bad_count += 1
        self.bad_bytes += size


def _parse_release_file_size(jpkg: dict, json_file: str) -> int | None:
    """Return release file size in bytes, or None if the metadata value is invalid."""
    raw_size = jpkg.get("size")
    if raw_size is None:
        return 0
    try:
        size = int(raw_size)
    except (TypeError, ValueError):
        logger.error(
            f"Invalid size {raw_size!r} for {jpkg.get('filename', '?')} in {json_file} "
            "- skipping release file"
        )
        return None
    if size < 0:
        logger.error(
            f"Invalid size {raw_size!r} for {jpkg.get('filename', '?')} in {json_file} "
            "- skipping release file"
        )
        return None
    return size


def log_dry_run_download_summary(stats: DryRunDownloadStats) -> None:
    if stats.bad_count == 0:
        logger.info("[DRY RUN] No files would be downloaded")
        return
    formatted_size = format_size(stats.bad_bytes, binary=True)
    logger.info(f"[DRY RUN] Would download {stats.bad_count} files (~{formatted_size})")
    if stats.unknown_size_count:
        logger.warning(
            f"[DRY RUN] {stats.unknown_size_count} files had unknown sizes in metadata"
        )


def on_error(stop_on_error: bool, exception: BaseException, package: str) -> None:
    if isinstance(exception, KeyboardInterrupt):
        # Setting self.errors to True to ensure we don't save Serial
        # and thus save to disk that we've had a successful sync
        logger.info(
            "Cancelling, all downloads are forcibly stopped, data may be "
            + "corrupted."
        )
    elif isinstance(exception, TypeError) or isinstance(exception, ValueError):
        # This occurs for testing or when todolist is corrupt
        pass
    else:
        if package:
            logger.exception(f"Error syncing package: {package}")
        if stop_on_error:
            logger.error("Exiting early after error.")
            sys.exit(1)


async def get_latest_json(
    master: Master,
    json_path: Path,
    executor: concurrent.futures.ThreadPoolExecutor | None = None,
    delete_removed_packages: bool = False,
) -> None:
    url_parts = urlparse(master.url)
    url = f"{url_parts.scheme}://{url_parts.netloc}/pypi/{json_path.name}/json"
    logger.debug(f"Updating {json_path.name} json from {url}")
    new_json_path = json_path.parent / f"{json_path.name}.new"
    try:
        await master.url_fetch(url, new_json_path, executor)
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            # A 404 means that the package has been removed from PyPI.
            # Allow function to continue, and remove package files if applicable.
            # write a blank json file to make the deletion process go through
            pass
        else:
            raise
    if new_json_path.exists():
        json_path.write_bytes(new_json_path.read_bytes())
        new_json_path.unlink()
    else:
        logger.error(
            f"{str(new_json_path)} does not exist - Did not get new JSON metadata"
        )
        if delete_removed_packages and json_path.exists():
            logger.debug(f"Unlinking {json_path} - assuming it does not exist upstream")
            json_path.unlink()


async def delete_unowned_files(
    storage_backend: Storage,
    mirror_base: Path,
    executor: concurrent.futures.ThreadPoolExecutor,
    all_package_files: Sequence[PATH_TYPES],
    dry_run: bool,
) -> int:
    """
    Calculates difference in expected files and stored files. Deletes them using the storage backend implementation
    """
    loop = asyncio.get_running_loop()
    packages_path = storage_backend.PATH_BACKEND(str(mirror_base)) / "web" / "packages"

    all_stored_files: set[str] = set()

    def _collect() -> None:
        for f in storage_backend.iter_package_files(packages_path):
            all_stored_files.add(str(f))

    await loop.run_in_executor(executor, _collect)

    all_package_files_set = {str(f) for f in all_package_files}
    unowned_files = all_stored_files - all_package_files_set

    logger.info(
        f"We have {len(all_package_files_set)} files. "
        + f"{len(unowned_files)} unowned files"
    )
    if not unowned_files:
        logger.info(f"{mirror_base} has no files to delete")
        return 0

    if dry_run:
        print(f"[DRY RUN] {len(unowned_files)} unowned files:", file=stderr)
        for f in sorted(unowned_files):
            print(f)
    else:
        del_coros = [
            loop.run_in_executor(
                executor,
                storage_backend.delete_package_file,
                storage_backend.PATH_BACKEND(f),
            )
            for f in unowned_files
        ]
        await asyncio.gather(*del_coros)

    return 0


async def verify(
    master: Master,
    config: ConfigParser,
    storage_backend: Storage,
    json_file: str,
    mirror_base_path: Path,
    all_package_files: list[PATH_TYPES],
    args: argparse.Namespace,
    executor: concurrent.futures.ThreadPoolExecutor | None = None,
    releases_key: str = "releases",
    dry_run_stats: DryRunDownloadStats | None = None,
) -> None:
    """
    Verify a single package JSON file and remediate any missing/corrupt files.

    1. Caluclates expected release files from the JSON file
    2. Calls storage backend to verify the files and returns any missing or corrupt files
    3. Downloads those files and stores them using the storage backend
    """
    json_base = mirror_base_path / "web" / "json"
    json_full_path = json_base / json_file
    logger.info(f"Parsing {json_file}")
    stop_on_error = config.getboolean("mirror", "stop-on-error")
    digest_name = config.get("mirror", "digest_name", fallback="sha256")

    if args.json_update:
        if not args.dry_run:
            try:
                await get_latest_json(master, json_full_path, executor, args.delete)
            except Exception as e:
                on_error(stop_on_error, e, package=json_file)
        else:
            logger.info(f"[DRY RUN] Would of grabbed latest json for {json_file}")

    if not storage_backend.exists(json_full_path):
        logger.debug(f"Not trying to sync package as {json_full_path} does not exist")
        return

    try:
        with storage_backend.open_file(json_full_path, text=True) as jfp:
            metadata = json.load(jfp)
    except json.decoder.JSONDecodeError as jde:
        logger.error(f"Failed to load {json_full_path} metadata: {jde} - skipping ...")
        return

    try:
        pkg = Package.from_metadata(metadata)
    except ValueError as e:
        logger.error(
            f"Failed to load {json_full_path} into a Package: {e} - skipping ..."
        )
        return

    # apply releases filter plugins like class Package
    loaded_filters = LoadedFilters()
    pkg.filter_all_releases_files(loaded_filters.filter_release_file_plugins())
    pkg.filter_all_releases(loaded_filters.filter_release_plugins())

    # Build the expected FileSpec list for all release files in this package.
    specs: list[FileSpec] = []
    for release_version in pkg.releases:
        for jpkg in pkg.releases[release_version]:
            file_size = _parse_release_file_size(jpkg, json_file)
            if file_size is None:
                continue
            raw_time = jpkg.get("upload_time_iso_8601", "1970-01-01T00:00:00Z")
            upload_time = datetime.datetime.fromisoformat(
                raw_time.replace("Z", "+00:00")
            )
            spec = FileSpec(
                path=mirror_base_path / "web" / convert_url_to_path(jpkg["url"]),
                url=jpkg["url"],
                filename=jpkg["filename"],
                size=file_size,
                digests=jpkg.get("digests", {}),
                upload_time=upload_time,
            )
            specs.append(spec)
            all_package_files.append(spec.path)

    # Ask the storage backend which files are missing or corrupt.
    deferred_exception = None
    async for bad_spec in storage_backend.verify_files(specs, dry_run=args.dry_run):
        if args.dry_run:
            logger.info(f"[DRY RUN] {bad_spec.filename} would be fetched")
            if dry_run_stats is not None:
                dry_run_stats.record_bad(bad_spec.size)
        else:
            try:
                await fetch_and_store(
                    master,
                    storage_backend,
                    bad_spec.url,
                    bad_spec.path,
                    bad_spec.digests.get(digest_name, ""),
                    bad_spec.upload_time,
                    digest_name=digest_name,
                )
            except Exception as e:
                logger.exception(
                    f"Error downloading {bad_spec.filename} ({bad_spec.url})"
                )
                if not deferred_exception:
                    deferred_exception = e

    if deferred_exception:
        on_error(stop_on_error, deferred_exception, package=json_file)

    logger.info(f"Finished validating {json_file}")


async def verify_producer(
    master: Master,
    config: ConfigParser,
    storage_backend: Storage,
    all_package_files: list[PATH_TYPES],  # mutable: verify() appends to it
    mirror_base_path: Path,
    json_files: list[str],
    args: argparse.Namespace,
    executor: concurrent.futures.ThreadPoolExecutor | None = None,
) -> DryRunDownloadStats | None:
    queue: asyncio.Queue = asyncio.Queue()
    for jf in json_files:
        await queue.put(jf)

    async def consume(q: Queue) -> DryRunDownloadStats:
        local_stats = DryRunDownloadStats()
        while not q.empty():
            json_file = await q.get()
            await verify(
                master,
                config,
                storage_backend,
                json_file,
                mirror_base_path,
                all_package_files,
                args,
                executor,
                dry_run_stats=local_stats if args.dry_run else None,
            )
        return local_stats

    consumer_results = await asyncio.gather(
        *[consume(queue)] * config.getint("mirror", "verifiers", fallback=3)
    )
    if args.dry_run:
        return sum(consumer_results, DryRunDownloadStats())
    return None


async def metadata_verify(config: ConfigParser, args: Namespace) -> int:
    """Crawl all saved JSON metadata or online to check we have all packages.
    If ``--delete`` is given, also remove files not referenced by any package.
    """
    all_package_files: list[PATH_TYPES] = []

    storage_backend = next(
        iter(
            storage_backend_plugins(
                config=config,
                clear_cache=True,
                backend=config.get("mirror", "storage-backend"),
            )
        )
    )

    mirror_base_path = storage_backend.PATH_BACKEND(config.get("mirror", "directory"))
    json_base = mirror_base_path / "web" / "json"
    workers = args.workers or config.getint("mirror", "workers")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    logger.info(f"Starting verify for {mirror_base_path} with {workers} workers")
    try:
        json_files = list(x.name for x in json_base.iterdir())
    except FileExistsError as fee:
        logger.error(f"Metadata base dir {json_base} does not exist: {fee}")
        return 2
    if not json_files:
        logger.error("No JSON metadata files found. Can not verify")
        return 3

    logger.debug(f"Found {len(json_files)} objects in {json_base}")
    logger.debug(f"Using a {workers} thread ThreadPoolExecutor")
    async with Master(
        config.get("mirror", "master"),
        config.getfloat("mirror", "timeout"),
        config.getfloat("mirror", "global-timeout", fallback=None),
    ) as master:
        producer_results = await verify_producer(
            master,
            config,
            storage_backend,
            all_package_files,
            mirror_base_path,
            json_files,
            args,
            executor,
        )

    if producer_results is not None:
        log_dry_run_download_summary(producer_results)

    if not args.delete:
        return 0

    return await delete_unowned_files(
        storage_backend, mirror_base_path, executor, all_package_files, args.dry_run
    )
