#!/usr/bin/env python3

import asyncio
import concurrent.futures
import logging
from argparse import Namespace
from configparser import ConfigParser
from json import JSONDecodeError, load
from pathlib import Path
from shutil import rmtree
from typing import Awaitable, List
from urllib.parse import urlparse

from packaging.utils import canonicalize_name

from bandersnatch.verify import get_latest_json

logger = logging.getLogger(__name__)  # pylint: disable=C0103


def delete_path(blob_path: Path, dry_run: bool = False) -> int:
    if dry_run:
        logger.info(f" rm {blob_path}")
        return 0

    if not blob_path.exists():
        logger.debug(f"{blob_path} does not exist. Skipping")
        return 0

    try:
        if blob_path.is_dir():
            rmtree(blob_path)
        else:
            blob_path.unlink()
    except FileNotFoundError:
        # Due to using threads in executors we sometimes have a
        # race condition if canonicalize_name == passed in name
        pass
    except OSError:
        logger.exception(f"Unable to delete {blob_path}")
        return 1

    return 0


async def delete_packages(config: ConfigParser, args: Namespace) -> int:
    loop = asyncio.get_event_loop()
    workers = args.workers or config.getint("mirror", "workers")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    mirror_base_path = Path(config.get("mirror", "directory"))
    web_base_path = mirror_base_path / "web"
    json_base_path = web_base_path / "json"
    pypi_base_path = web_base_path / "pypi"
    simple_path = web_base_path / "simple"

    delete_coros: List[Awaitable] = []
    for package in args.pypi_packages:
        canon_name = canonicalize_name(package)
        need_nc_paths = canon_name != package
        json_full_path = json_base_path / canon_name
        json_full_path_nc = json_base_path / package if need_nc_paths else None
        legacy_json_path = pypi_base_path / canon_name
        logger.debug(f"Looking up {canon_name} metadata @ {json_full_path}")

        if not json_full_path.exists():
            if args.dry_run:
                logger.error(
                    f"Skipping {json_full_path} as dry run and no JSON file exists"
                )
                continue

            logger.error(f"{json_full_path} does not exist. Pulling from PyPI")
            await get_latest_json(json_full_path, config, executor, False)
            if not json_full_path.exists():
                logger.error(f"Unable to HTTP get JSON for {json_full_path}")
                continue

        with json_full_path.open("r") as jfp:
            try:
                package_data = load(jfp)
            except JSONDecodeError:
                logger.exception(f"Skipping {canon_name} @ {json_full_path}")
                continue

        for _release, blobs in package_data["releases"].items():
            for blob in blobs:
                url_parts = urlparse(blob["url"])
                blob_path = web_base_path / url_parts.path[1:]
                delete_coros.append(
                    loop.run_in_executor(executor, delete_path, blob_path, args.dry_run)
                )

        # Attempt to delete json, normal simple path + hash simple path
        package_simple_path = simple_path / canon_name
        package_simple_path_nc = simple_path / package if need_nc_paths else None
        package_hash_path = simple_path / canon_name[0] / canon_name
        package_hash_path_nc = (
            simple_path / canon_name[0] / package if need_nc_paths else None
        )
        # Try cleanup non canon name if they differ
        for package_path in (
            json_full_path,
            legacy_json_path,
            package_simple_path,
            package_simple_path_nc,
            package_hash_path,
            package_hash_path_nc,
            json_full_path_nc,
        ):
            if not package_path:
                continue

            delete_coros.append(
                loop.run_in_executor(executor, delete_path, package_path, args.dry_run)
            )

    if args.dry_run:
        logger.info("-- bandersnatch delete DRY RUN --")
    if delete_coros:
        logger.info(f"Attempting to remove {len(delete_coros)} files")
        return sum(await asyncio.gather(*delete_coros))
    return 0
