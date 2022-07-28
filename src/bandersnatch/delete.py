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
        return 0
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


async def delete_simple_page(
    simple_base_path: Path, package: str, hash_index: bool = False, dry_run: bool = True
) -> int:
    if dry_run:
        logger.info(f"[dry run]rm simple page of {package}")
        return 0
    simple_dir = simple_base_path / package
    simple_index = simple_dir / "index.html"
    hashed_simple_dir = simple_base_path / package[0] / package
    hashed_index = hashed_simple_dir / "index.html"
    folders_to_clean = [simple_dir]
    if hash_index:
        if hashed_index.exists():
            hashed_index.unlink()
        folders_to_clean.append(hashed_simple_dir)
    else:
        if simple_index.exists():
            simple_index.unlink()
    for f in folders_to_clean:
        # separate to 3 stages to avoid case like s3
        # (folder will be removed automatically if empty)
        if f.exists():
            for p in reversed(list(f.rglob("*"))):
                if p.is_file() or p.is_symlink():
                    p.unlink()
        if f.exists():
            for p in reversed(list(f.rglob("*"))):
                if p.is_dir():
                    p.rmdir()
        if f.exists() and f.is_dir():
            f.rmdir()
    return 0


async def delete_packages(config: ConfigParser, args: Namespace, master: Master) -> int:
    workers = args.workers or config.getint("mirror", "workers")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    storage_backend = next(
        iter(
            storage_backend_plugins(
                backend=config.get("mirror", "storage-backend"),
                config=config,
                clear_cache=True,
            )
        )
    )
    web_base_path = storage_backend.web_base_path
    json_base_path = storage_backend.json_base_path
    pypi_base_path = storage_backend.pypi_base_path
    simple_base_path = storage_backend.simple_base_path

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
            await get_latest_json(master, json_full_path, executor, False)
        if not json_full_path.exists():
            logger.info(
                f"No json file for {package} found, skipping blob file cleaning"
            )
        else:
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
        hash_index_enabled = config.getboolean("mirror", "hash-index")
        if need_nc_paths:
            delete_coros.append(
                delete_simple_page(
                    simple_base_path,
                    canon_name,
                    hash_index=hash_index_enabled,
                    dry_run=args.dry_run,
                )
            )
        delete_coros.append(
            delete_simple_page(
                simple_base_path,
                package,
                hash_index=hash_index_enabled,
                dry_run=args.dry_run,
            )
        )
        for package_path in (
            json_full_path,
            legacy_json_path,
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
