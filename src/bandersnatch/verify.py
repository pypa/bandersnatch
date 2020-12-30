import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import shutil
import sys
from argparse import Namespace
from asyncio.queues import Queue
from configparser import ConfigParser
from pathlib import Path
from sys import stderr
from typing import List, Optional, Set
from urllib.parse import urlparse

import aiohttp

from .filter import LoadedFilters
from .master import Master
from .storage import storage_backend_plugins
from .utils import convert_url_to_path, hash, recursive_find_files, unlink_parent_dir

logger = logging.getLogger(__name__)


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
    config: ConfigParser,
    executor: Optional[concurrent.futures.ThreadPoolExecutor] = None,
    delete_removed_packages: bool = False,
) -> None:
    url_parts = urlparse(config.get("mirror", "master"))
    url = f"{url_parts.scheme}://{url_parts.netloc}/pypi/{json_path.name}/json"
    logger.debug(f"Updating {json_path.name} json from {url}")
    new_json_path = json_path.parent / f"{json_path.name}.new"
    try:
        await master.url_fetch(url, new_json_path, executor)
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            # A 404 means that the package has been removed from PyPI.
            # Allow function to continue, and remove package files if applicable.
            pass
        else:
            raise
    if new_json_path.exists():
        shutil.move(str(new_json_path), json_path)
    else:
        logger.error(
            f"{str(new_json_path)} does not exist - Did not get new JSON metadata"
        )
        if delete_removed_packages and json_path.exists():
            logger.debug(f"Unlinking {json_path} - assuming it does not exist upstream")
            json_path.unlink()


async def delete_unowned_files(
    mirror_base: Path,
    executor: concurrent.futures.ThreadPoolExecutor,
    all_package_files: List[Path],
    dry_run: bool,
) -> int:
    loop = asyncio.get_event_loop()
    packages_path = mirror_base / "web" / "packages"
    all_fs_files: Set[Path] = set()
    await loop.run_in_executor(
        executor, recursive_find_files, all_fs_files, packages_path
    )

    all_package_files_set = set(all_package_files)
    unowned_files = all_fs_files - all_package_files_set
    logger.info(
        f"We have {len(all_package_files_set)} files. "
        + f"{len(unowned_files)} unowned files"
    )
    if not unowned_files:
        logger.info(f"{mirror_base} has no files to delete")
        return 0

    if dry_run:
        print("[DRY RUN] Unowned file list:", file=stderr)
        for f in sorted(unowned_files):
            print(f)
    else:
        del_coros = []
        for file_path in unowned_files:
            del_coros.append(
                loop.run_in_executor(executor, unlink_parent_dir, file_path)
            )
        await asyncio.gather(*del_coros)

    return 0


async def verify(
    master: Master,
    config: ConfigParser,
    json_file: str,
    mirror_base_path: Path,
    all_package_files: List[Path],
    args: argparse.Namespace,
    executor: Optional[concurrent.futures.ThreadPoolExecutor] = None,
    releases_key: str = "releases",
) -> None:
    json_base = mirror_base_path / "web" / "json"
    json_full_path = json_base / json_file
    loop = asyncio.get_event_loop()
    logger.info(f"Parsing {json_file}")
    stop_on_error = config.getboolean("mirror", "stop-on-error")

    if args.json_update:
        if not args.dry_run:
            try:
                await get_latest_json(
                    master, json_full_path, config, executor, args.delete
                )
            except Exception as e:
                on_error(stop_on_error, e, package=json_file)
        else:
            logger.info(f"[DRY RUN] Would of grabbed latest json for {json_file}")

    if not json_full_path.exists():
        logger.debug(f"Not trying to sync package as {json_full_path} does not exist")
        return

    try:
        with json_full_path.open("r") as jfp:
            pkg = json.load(jfp)
    except json.decoder.JSONDecodeError as jde:
        logger.error(f"Failed to load {json_full_path}: {jde} - skipping ...")
        return

    # apply releases filter plugins like class Package
    for plugin in LoadedFilters().filter_release_plugins() or []:
        plugin.filter(pkg)

    deferred_exception = None
    for release_version in pkg[releases_key]:
        for jpkg in pkg[releases_key][release_version]:
            pkg_file = mirror_base_path / "web" / convert_url_to_path(jpkg["url"])
            if not pkg_file.exists():
                if args.dry_run:
                    logger.info(f"{jpkg['url']} would be fetched")
                    all_package_files.append(pkg_file)
                    continue
                else:
                    try:
                        await master.url_fetch(jpkg["url"], pkg_file, executor)
                    except Exception as e:
                        logger.exception(
                            "Continuing to next file after error downloading: "
                            f"{jpkg['url']}"
                        )
                        if not deferred_exception:  # keep first exception
                            deferred_exception = e
                        continue

            calc_sha256 = await loop.run_in_executor(executor, hash, str(pkg_file))
            if calc_sha256 != jpkg["digests"]["sha256"]:
                if not args.dry_run:
                    await loop.run_in_executor(None, pkg_file.unlink)
                    await master.url_fetch(jpkg["url"], pkg_file, executor)
                else:
                    logger.info(
                        f"[DRY RUN] {jpkg['info']['name']} has a sha256 mismatch."
                    )

            all_package_files.append(pkg_file)

    if deferred_exception:
        on_error(stop_on_error, deferred_exception, package=json_file)

    logger.info(f"Finished validating {json_file}")


async def verify_producer(
    master: Master,
    config: ConfigParser,
    all_package_files: List[Path],
    mirror_base_path: Path,
    json_files: List[str],
    args: argparse.Namespace,
    executor: Optional[concurrent.futures.ThreadPoolExecutor] = None,
) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    for jf in json_files:
        await queue.put(jf)

    async def consume(q: Queue) -> None:
        while not q.empty():
            json_file = await q.get()
            await verify(
                master,
                config,
                json_file,
                mirror_base_path,
                all_package_files,
                args,
                executor,
            )

    await asyncio.gather(
        *[consume(queue)] * config.getint("mirror", "verifiers", fallback=3)
    )


async def metadata_verify(config: ConfigParser, args: Namespace) -> int:
    """Crawl all saved JSON metadata or online to check we have all packages
    if delete - generate a diff of unowned files"""
    all_package_files: List[Path] = []
    loop = asyncio.get_event_loop()

    storage_backend = next(
        iter(storage_backend_plugins(config=config, clear_cache=True))
    )

    mirror_base_path = storage_backend.PATH_BACKEND(config.get("mirror", "directory"))
    json_base = mirror_base_path / "web" / "json"
    workers = args.workers or config.getint("mirror", "workers")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    logger.info(f"Starting verify for {mirror_base_path} with {workers} workers")
    try:
        json_files = await loop.run_in_executor(executor, os.listdir, json_base)
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
        await verify_producer(
            master,
            config,
            all_package_files,
            mirror_base_path,
            json_files,
            args,
            executor,
        )

    if not args.delete:
        return 0

    return await delete_unowned_files(
        mirror_base_path, executor, all_package_files, args.dry_run
    )
