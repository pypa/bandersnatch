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

ASYNC_USER_AGENT = user_agent("aiohttp {}".format(aiohttp.__version__))
logger = logging.getLogger(__name__)


def _convert_url_to_path(url):
    return urlparse(url).path[1:]


async def _get_latest_json(json_path, config):  # noqa: E999
    url_parts = urlparse(config.get("mirror", "master"))
    url = "{}://{}/pypi/{}/json".format(
        url_parts.scheme, url_parts.netloc, json_path.name
    )
    logger.debug("Updating {} json from {}".format(json_path.name, url))
    new_json_path = json_path.parent / "{}.new".format(json_path.name)
    await url_fetch(url, new_json_path)
    if new_json_path.exists():
        os.rename(new_json_path, json_path)
        return
    logger.error(
        "{} does not exist - Did not get new JSON metadata".format(
            new_json_path.as_posix()
        )
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
    logger.info("unlink {}".format(path.as_posix()))
    path.unlink()
    try:
        path.parent.rmdir()
        logger.info("rmdir {}".format(path.parent.as_posix()))
    except OSError as oe:
        logger.debug("Did not remove {}: {}".format(path.parent.as_posix(), str(oe)))


async def verify(  # noqa: E999
    config, json_file, mirror_base, all_package_files, args, releases_key="releases"
):
    json_base = Path(mirror_base) / "web/json"
    json_full_path = json_base / json_file
    loop = asyncio.get_event_loop()
    logger.info("Parsing {}".format(json_file))

    if args.json_update:
        if not args.dry_run:
            await _get_latest_json(json_full_path, config)
        else:
            logger.info(
                "[DRY RUN] Would of grabbed latest json for {}".format(json_file)
            )

    with json_full_path.open("r") as jfp:
        pkg = json.load(jfp)

    for release_version in pkg[releases_key]:
        for jpkg in pkg[releases_key][release_version]:
            pkg_file = Path(mirror_base) / "web" / _convert_url_to_path(jpkg["url"])
            if not pkg_file.exists():
                if not args.dry_run:
                    await url_fetch(jpkg["url"], pkg_file)
                else:
                    logger.info("{} would be fetched".format(jpkg["url"]))

            calc_sha256 = await loop.run_in_executor(
                None, _sha256_checksum, pkg_file.as_posix()
            )
            if calc_sha256 != jpkg["digests"]["sha256"]:
                if not args.dry_run:
                    await loop.run_in_executor(None, pkg_file.unlink)
                    await verify(json_file, mirror_base)
                else:
                    logger.info(
                        "[DRY RUN] {} has a sha256 mismatch. Would "
                        + "redownload recursively".format(jpkg["info"]["name"])
                    )

            all_package_files.append(pkg_file)

    logger.info("Finished validating {}".format(json_file))


async def url_fetch(url, file_path, chunk_size=65536, timeout=60):
    logger.info("Fetching {}".format(url))
    loop = asyncio.get_event_loop()

    await loop.run_in_executor(
        None, partial(file_path.parent.mkdir, parents=True, exist_ok=True)
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


async def async_verify(  # noqa: E999
    config, all_package_files, mirror_base, json_files, args
) -> int:
    coros = []
    logger.debug("Loading JSON files to verify")
    for json_file in json_files:
        coros.append(verify(config, json_file, mirror_base, all_package_files, args))

    logger.debug("Gathering all the verify threads")
    await asyncio.gather(*coros)

    return 0


def metadata_verify(config, args):
    """ Crawl all saved JSON metadata or online to check we have all packages
        if delete - generate a diff of unowned files  """
    mirror_base = config.get("mirror", "directory")
    json_base = os.path.join(mirror_base, "web", "json")
    workers = args.workers or config.getint("mirror", "workers")

    logger.info("Starting verify for {} with {} workers".format(mirror_base, workers))
    try:
        json_files = os.listdir(json_base)
    except FileExistsError as fee:  # noqa: F821
        logger.error("Metadata base dir {} does not exist: {}".format(json_base, fee))
        return 2
    if not json_files:
        logger.error("No JSON metadata files found. Can not verify")
        return 3
    logger.debug("Found {} objects in {}".format(len(json_files), json_base))

    all_package_files = []
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    loop.set_default_executor(executor)
    logger.debug("Using a {} thread ThreadPoolExecutor".format(workers))
    try:
        if loop.run_until_complete(
            async_verify(config, all_package_files, mirror_base, json_files, args)
        ):
            logger.error("Problem with the verification")

        packages_path = Path(mirror_base) / "web/packages"
        all_fs_files = set()
        _recursive_find_file(all_fs_files, packages_path)

        all_package_files_set = set(all_package_files)
        unowned_files = all_fs_files - all_package_files_set
        logger.info(
            "We have {} files. {} unowned files".format(
                len(all_package_files_set), len(unowned_files)
            )
        )
        if args.dry_run:
            print("[DRY RUN] Unowned file list:", file=stderr)
            for f in sorted(unowned_files):
                print(f)
            return 0

        del_coros = []
        for file_path in unowned_files:
            del_coros.append(loop.run_in_executor(None, _unlink_parent_dir, file_path))
        loop.run_until_complete(asyncio.gather(*del_coros))
    finally:
        loop.close()
