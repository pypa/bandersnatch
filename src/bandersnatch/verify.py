import asyncio
import concurrent.futures
import json
import logging
import os
import shutil
from argparse import Namespace
from asyncio.queues import Queue
from configparser import ConfigParser
from functools import partial
from pathlib import Path
from sys import stderr
from typing import List, Set  # noqa: F401
from urllib.parse import urlparse

import aiohttp

from bandersnatch.configuration import BandersnatchConfig
from bandersnatch.filter import filter_release_plugins

from bandersnatch.utils import (  # isort:skip
    USER_AGENT,
    convert_url_to_path,
    hash,
    recursive_find_files,
    unlink_parent_dir,
)

logger = logging.getLogger(__name__)


async def get_latest_json(
    json_path: Path,
    config: ConfigParser,
    executor: concurrent.futures.ThreadPoolExecutor,
    delete_removed_packages: bool = False,
) -> None:
    url_parts = urlparse(config.get("mirror", "master"))
    url = f"{url_parts.scheme}://{url_parts.netloc}/pypi/{json_path.name}/json"
    logger.debug(f"Updating {json_path.name} json from {url}")
    new_json_path = json_path.parent / f"{json_path.name}.new"
    await url_fetch(url, new_json_path, executor)
    if new_json_path.exists():
        shutil.move(new_json_path, json_path)
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
    packages_path = Path(mirror_base) / "web" / "packages"
    all_fs_files = set()  # type: Set[Path]
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
    config,
    json_file,
    mirror_base_path,
    all_package_files,
    args,
    executor,
    releases_key="releases",
):
    json_base = mirror_base_path / "web" / "json"
    json_full_path = json_base / json_file
    loop = asyncio.get_event_loop()
    logger.info(f"Parsing {json_file}")

    if args.json_update:
        if not args.dry_run:
            await get_latest_json(json_full_path, config, executor, args.delete)
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
    for plugin in filter_release_plugins() or []:
        plugin.filter(pkg["info"], pkg[releases_key])

    for release_version in pkg[releases_key]:
        for jpkg in pkg[releases_key][release_version]:
            pkg_file = mirror_base_path / "web" / convert_url_to_path(jpkg["url"])
            if not pkg_file.exists():
                if args.dry_run:
                    logger.info(f"{jpkg['url']} would be fetched")
                    all_package_files.append(pkg_file)
                    continue
                else:
                    await url_fetch(jpkg["url"], pkg_file, executor)

            calc_sha256 = await loop.run_in_executor(executor, hash, str(pkg_file))
            if calc_sha256 != jpkg["digests"]["sha256"]:
                if not args.dry_run:
                    await loop.run_in_executor(None, pkg_file.unlink)
                    await url_fetch(jpkg["url"], pkg_file, executor)
                else:
                    logger.info(
                        f"[DRY RUN] {jpkg['info']['name']} has a sha256 mismatch."
                    )

            all_package_files.append(pkg_file)

    logger.info(f"Finished validating {json_file}")


async def url_fetch(url, file_path, executor, chunk_size=65536, timeout=60):
    logger.info(f"Fetching {url}")
    loop = asyncio.get_event_loop()

    await loop.run_in_executor(
        executor, partial(file_path.parent.mkdir, parents=True, exist_ok=True)
    )

    custom_headers = {"User-Agent": USER_AGENT}
    skip_headers = {"User-Agent"}
    aiohttp_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(
        headers=custom_headers, skip_auto_headers=skip_headers, trust_env=True
    ) as session:
        async with session.get(url, timeout=aiohttp_timeout) as response:
            if response.status == 200:
                with file_path.open("wb") as fd:
                    while True:
                        chunk = await response.content.read(chunk_size)
                        if not chunk:
                            break
                        fd.write(chunk)
            else:
                logger.error(f"Invalid response from {url} ({response.status})")


async def async_verify(
    config, all_package_files, mirror_base_path, json_files, args, executor
) -> None:
    queue = asyncio.Queue()  # type: Queue
    for jf in json_files:
        queue.put_nowait(jf)

    async def consume(q: Queue):
        while not q.empty():
            json_file = q.get_nowait()
            await verify(
                config, json_file, mirror_base_path, all_package_files, args, executor
            )

    # TODO: See if we can use passed in config
    config = BandersnatchConfig().config
    verifiers = config.getint("mirror", "verifiers", fallback=3)
    consumers = [consume(queue)] * verifiers

    await asyncio.gather(*consumers)


async def metadata_verify(config: ConfigParser, args: Namespace) -> int:
    """ Crawl all saved JSON metadata or online to check we have all packages
        if delete - generate a diff of unowned files  """
    all_package_files = []  # type: List[Path]
    loop = asyncio.get_event_loop()
    mirror_base_path = Path(config.get("mirror", "directory"))
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
    await async_verify(
        config, all_package_files, mirror_base_path, json_files, args, executor
    )

    if not args.delete:
        return 0

    return await delete_unowned_files(
        mirror_base_path, executor, all_package_files, args.dry_run
    )
