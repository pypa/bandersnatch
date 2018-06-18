import asyncio
import concurrent.futures
import hashlib
import json
import logging
import os
from functools import partial
from pathlib import Path
from sys import stderr
from urllib.parse import urlparse

import aiohttp

from bandersnatch.utils import user_agent

ASYNC_USER_AGENT = user_agent(f"aiohttp {aiohttp.__version__}")
logger = logging.getLogger(__name__)


def _convert_url_to_path(url):
    return urlparse(url).path[1:]


async def _get_latest_json(json_path, config):
    url_parts = urlparse(config.get("mirror", "master"))
    url = f"{url_parts.scheme}://{url_parts.netloc}/pypi/{json_path.name}/json"
    logger.debug(f"Updating {json_path.name} json from {url}")
    new_json_path = json_path.parent / f"{json_path.name}.new"
    await url_fetch(url, new_json_path)
    if new_json_path.exists():
        os.rename(new_json_path, json_path)
        return
    logger.error(
        f"{new_json_path.as_posix()} does not exist - Did not get new JSON metadata"
    )


def _sha256_checksum(filename, block_size=65536):
    sha256 = hashlib.sha256()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()


def _recursive_find_file(files, base_dir):
    dirs = [d for d in base_dir.iterdir() if d.is_dir()]
    files.update([x for x in base_dir.iterdir() if x.is_file()])
    for directory in dirs:
        _recursive_find_file(files, directory)


def _unlink_parent_dir(path):
    logger.info(f"unlink {path.as_posix()}")
    path.unlink()
    try:
        path.parent.rmdir()
        logger.info(f"rmdir {path.parent.as_posix()}")
    except OSError as oe:
        logger.debug(f"Did not remove {path.parent.as_posix()}: {str(oe)}")



async def verify(
    config,
    json_file,
    mirror_base,
    all_package_files,
    args,
    executor,
    releases_key="releases",
):
    json_base = Path(mirror_base) / "web/json"
    json_full_path = json_base / json_file
    loop = asyncio.get_event_loop()
    logger.info(f"Parsing {json_file}")

    if args.json_update:
        if not args.dry_run:
            await _get_latest_json(json_full_path, config)
        else:
            logger.info(f"[DRY RUN] Would of grabbed latest json for {json_file}")

    with json_full_path.open("r") as jfp:
        pkg = json.load(jfp)

    for release_version in pkg[releases_key]:
        for jpkg in pkg[releases_key][release_version]:
            pkg_file = Path(mirror_base) / "web" / _convert_url_to_path(jpkg["url"])
            if not pkg_file.exists():
                if not args.dry_run:
                    await url_fetch(jpkg["url"], pkg_file, executor)
                else:
                    logger.info(f"{jpkg['url']} would be fetched")

            calc_sha256 = await loop.run_in_executor(
                executor, _sha256_checksum, pkg_file.as_posix()
            )
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

    custom_headers = {"User-Agent": ASYNC_USER_AGENT}
    skip_headers = {"User-Agent"}

    async with aiohttp.ClientSession(
        headers=custom_headers, skip_auto_headers=skip_headers
    ) as session:
        async with session.get(url, timeout=timeout) as response:
            with file_path.open("wb") as fd:
                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break
                    fd.write(chunk)



async def async_verify(
    config, all_package_files, mirror_base, json_files, args, executor
) -> None:
    coros = []
    logger.debug("Loading JSON files to verify")
    for json_file in json_files:
        coros.append(
            verify(config, json_file, mirror_base, all_package_files, args, executor)
        )

    logger.debug("Gathering all the verify threads")
    await asyncio.gather(*coros)


async def metadata_verify(config, args):
    """ Crawl all saved JSON metadata or online to check we have all packages
        if delete - generate a diff of unowned files  """
    all_package_files = []
    loop = asyncio.get_event_loop()
    mirror_base = config.get("mirror", "directory")
    json_base = os.path.join(mirror_base, "web", "json")
    workers = args.workers or config.getint("mirror", "workers")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    logger.info(f"Starting verify for {mirror_base} with {workers} workers")
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
        config, all_package_files, mirror_base, json_files, args, executor
    )

    packages_path = Path(mirror_base) / "web/packages"
    all_fs_files = set()
    await loop.run_in_executor(
        executor, _recursive_find_file, all_fs_files, packages_path
    )

    all_package_files_set = set(all_package_files)
    unowned_files = all_fs_files - all_package_files_set
    logger.info(
        f"We have {len(all_package_files_set)} files. "
        + f"{len(unowned_files)} unowned files"
    )
    if args.dry_run and unowned_files:
        print("[DRY RUN] Unowned file list:", file=stderr)
        for f in sorted(unowned_files):
            print(f)
        return 0

    del_coros = []
    for file_path in unowned_files:
        del_coros.append(loop.run_in_executor(executor, _unlink_parent_dir, file_path))
    await asyncio.gather(*del_coros)
