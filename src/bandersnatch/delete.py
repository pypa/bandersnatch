#!/usr/bin/env python3

import asyncio
import concurrent.futures
import logging
from argparse import Namespace
from configparser import ConfigParser
from functools import partial
from json import JSONDecodeError, load
from pathlib import Path
from typing import Awaitable, List
from urllib.parse import urlparse

from packaging.utils import canonicalize_name

from .master import Master
from .storage import storage_backend_plugins
from .verify import get_latest_json

logger = logging.getLogger(__name__)


async def delete_path(blob_path: Path, dry_run: bool = False) -> int:
    storage_backend = next(iter(storage_backend_plugins()))
    if dry_run:
        logger.info(f" rm {blob_path}")
    blob_exists = await storage_backend.loop.run_in_executor(
        storage_backend.executor, storage_backend.exists, blob_path
    )
    if not blob_exists:
        logger.debug(f"{blob_path} does not exist. Skipping")
        return 0
    try:
        del_partial = partial(storage_backend.delete, blob_path, dry_run=dry_run)
        await storage_backend.loop.run_in_executor(
            storage_backend.executor, del_partial
        )
    except FileNotFoundError:
        # Due to using threads in executors we sometimes have a
        # race condition if canonicalize_name == passed in name
        pass
    except OSError:
        logger.exception(f"Unable to delete {blob_path}")
        return 1
    return 0


async def delete_packages(config: ConfigParser, args: Namespace, master: Master) -> int:
    workers = args.workers or config.getint("mirror", "workers")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    storage_backend = next(
        iter(storage_backend_plugins(config=config, clear_cache=True))
    )
    web_base_path = storage_backend.web_base_path
    json_base_path = storage_backend.json_base_path
    pypi_base_path = storage_backend.pypi_base_path
    simple_path = storage_backend.simple_base_path

    delete_coros: List[Awaitable] = []
    for package in args.pypi_packages:
        canon_name = canonicalize_name(package)
        need_nc_paths = canon_name != package
        json_full_path = json_base_path / canon_name
        json_full_path_nc = json_base_path / package if need_nc_paths else None
        legacy_json_path = pypi_base_path / canon_name
        logger.debug(f"Looking up {canon_name} metadata @ {json_full_path}")

        if not storage_backend.exists(json_full_path):
            if args.dry_run:
                logger.error(
                    f"Skipping {json_full_path} as dry run and no JSON file exists"
                )
                continue

            logger.error(f"{json_full_path} does not exist. Pulling from PyPI")
            await get_latest_json(master, json_full_path, config, executor, False)
            if not json_full_path.exists():
                logger.error(f"Unable to HTTP get JSON for {json_full_path}")
                continue

        with storage_backend.open_file(json_full_path, text=True) as jfp:
            try:
                package_data = load(jfp)
            except JSONDecodeError:
                logger.exception(f"Skipping {canon_name} @ {json_full_path}")
                continue

        for _release, blobs in package_data["releases"].items():
            for blob in blobs:
                url_parts = urlparse(blob["url"])
                blob_path = web_base_path / url_parts.path[1:]
                delete_coros.append(delete_path(blob_path, args.dry_run))

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

            delete_coros.append(delete_path(package_path, args.dry_run))

    if args.dry_run:
        logger.info("-- bandersnatch delete DRY RUN --")
    if delete_coros:
        logger.info(f"Attempting to remove {len(delete_coros)} files")
        return sum(await asyncio.gather(*delete_coros))
    return 0
