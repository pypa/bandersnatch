#!/usr/bin/env python3

"""
Quick tool to test xmlrpc queries from bandersnatch
"""

import asyncio

from bandersnatch.master import Master


async def main() -> int:
    async with Master("https://pypi.org") as master:
        all_packages = await master.all_packages()
    print(f"PyPI returned {len(all_packages)} PyPI packages via xmlrpc")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
