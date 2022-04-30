import contextlib
import hashlib
import logging
import os
import os.path
import platform
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Generator, List, Set, Union
from urllib.parse import urlparse

import aiohttp
from packaging.tags import INTERPRETER_SHORT_NAMES

from . import __version__

logger = logging.getLogger(__name__)


def user_agent() -> str:
    template = "bandersnatch/{version} ({python}, {system})"
    template += f" (aiohttp {aiohttp.__version__})"
    version = __version__
    python = sys.implementation.name
    python += " {}.{}.{}-{}{}".format(*sys.version_info)
    uname = platform.uname()
    system = " ".join([uname.system, uname.machine])
    return template.format(**locals())


SAFE_NAME_REGEX = re.compile(r"[^A-Za-z0-9.]+")
USER_AGENT = user_agent()
WINDOWS = bool(platform.system() == "Windows")


def make_time_stamp() -> str:
    """Helper function that returns a timestamp suitable for use
    in a filename on any OS"""
    return f"{datetime.utcnow().isoformat()}Z".replace(":", "")


def convert_url_to_path(url: str) -> str:
    return urlparse(url).path[1:]


def hash(path: Path, function: str = "sha256") -> str:
    h = getattr(hashlib, function)()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(128 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return str(h.hexdigest())


def find(root: Union[Path, str], dirs: bool = True) -> str:
    """A test helper simulating 'find'.

    Iterates over directories and filenames, given as relative paths to the
    root.

    """
    # TODO: account for alternative backends
    if isinstance(root, str):
        root = Path(root)

    results: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        names = filenames
        if dirs:
            names += dirnames
        for name in names:
            results.append(Path(dirpath) / name)
    results.sort()
    return "\n".join(str(result.relative_to(root)) for result in results)


@contextlib.contextmanager
def rewrite(
    filepath: Union[str, Path], mode: str = "w", **kw: Any
) -> Generator[IO, None, None]:
    """Rewrite an existing file atomically to avoid programs running in
    parallel to have race conditions while reading."""
    # TODO: Account for alternative backends
    if isinstance(filepath, str):
        base_dir = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
    else:
        base_dir = str(filepath.parent)
        filename = filepath.name

    # Change naming format to be more friendly with distributed POSIX
    # filesystems like GlusterFS that hash based on filename
    # GlusterFS ignore '.' at the start of filenames and this avoid rehashing
    with tempfile.NamedTemporaryFile(
        mode=mode, prefix=f".{filename}.", delete=False, dir=base_dir, **kw
    ) as f:
        filepath_tmp = f.name
        yield f

    if not os.path.exists(filepath_tmp):
        # Allow our clients to remove the file in case it doesn't want it to be
        # put in place actually but also doesn't want to error out.
        return
    os.chmod(filepath_tmp, 0o100644)
    shutil.move(filepath_tmp, filepath)


def recursive_find_files(files: Set[Path], base_dir: Path) -> None:
    dirs = [d for d in base_dir.iterdir() if d.is_dir()]
    files.update([x for x in base_dir.iterdir() if x.is_file()])
    for directory in dirs:
        recursive_find_files(files, directory)


def unlink_parent_dir(path: Path) -> None:
    """Remove a file and if the dir is empty remove it"""
    logger.info(f"unlink {str(path)}")
    path.unlink()

    parent_path = path.parent
    try:
        parent_path.rmdir()
        logger.info(f"rmdir {str(parent_path)}")
    except OSError as oe:
        logger.debug(f"Did not remove {str(parent_path)}: {str(oe)}")


def bandersnatch_safe_name(name: str) -> str:
    """Convert an arbitrary string to a standard distribution name
    Any runs of non-alphanumeric/. characters are replaced with a single '-'.

    - This was copied from `pkg_resources` (part of `setuptools`)

    bandersnatch also lower cases the returned name
    """
    return SAFE_NAME_REGEX.sub("-", name).lower()


# From https://peps.python.org/pep-0616/
def removeprefix(original: str, prefix: str) -> str:
    """Return a string with the given prefix string removed if present.
       If the string starts with the prefix string, return string[len(prefix):].
       Otherwise, return the original string.

    Args:
        original (str): string to remove the prefix (e.g. 'py3.6')
        prefix (str): the prefix to remove (e.g. 'py')

    Returns:
        str: either the modified or the original string (e.g. '3.6')
    """
    if original.startswith(prefix):
        prefix_len = len(prefix)
        mod_str = original[prefix_len:]
        return mod_str
    else:
        return original


# Python tags https://peps.python.org/pep-0425/#python-tag
def parse_version(version: str) -> List[str]:
    """Converts a version string to a list of strings to check the 1st part of build tags.
    See PEP 425 (https://peps.python.org/pep-0425/#python-tag) for details.

    Args:
        version (str): string in the form of '{major}.{minor}'
            e.g. '3.6'

    Returns:
        List[str]: list of 1st element strings from build tag tuples
            See https://peps.python.org/pep-0425/#python-tag for details.
            Some Windows binaries have only the 1st part before the file extension.
            e.g. ['-cp36-', '-pp36-', '-ip36-', '-jy36-', '-py3.6-', '-py3.6.']
    """
    _versions: List[str] = []

    _version_with_dot = removeprefix(version.lower(), "py")
    _version_without_dot = _version_with_dot.replace(".", "")

    interpreters = list(INTERPRETER_SHORT_NAMES.values())
    interpreters.remove("py")
    tag_separator1 = "-"
    tag_separator2 = "."

    _versions.extend(
        [
            tag_separator1 + i + _version_without_dot + tag_separator1
            for i in interpreters
        ]
    )
    _versions.extend(
        [
            tag_separator1
            + INTERPRETER_SHORT_NAMES.get("python")
            + _version_with_dot
            + tag_separator1
        ]
    )
    _versions.extend(
        [
            tag_separator1
            + INTERPRETER_SHORT_NAMES.get("python")
            + _version_with_dot
            + tag_separator2
        ]
    )

    return _versions
