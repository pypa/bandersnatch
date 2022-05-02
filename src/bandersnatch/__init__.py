#!/usr/bin/env python3

__copyright__ = "2010-Present, PyPA"

from typing import NamedTuple


class _VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int

    @property
    def version_str(self) -> str:
        release_level = f".{self.releaselevel}" if self.releaselevel else ""
        return f"{self.major}.{self.minor}.{self.micro}{release_level}"


__version_info__ = _VersionInfo(
    major=5,
    minor=2,
    micro=0,
    releaselevel="",
    serial=0,  # Not currently in use with Bandersnatch versioning
)
__version__ = __version_info__.version_str
